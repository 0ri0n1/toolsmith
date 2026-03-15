#!/usr/bin/env python3
"""
Nmap Tool API — lightweight HTTP endpoint for Open WebUI tool integration.

Runs on the Windows host, executes nmap inside WSL2 Kali Linux.
Register this in Open WebUI as an OpenAPI tool at http://localhost:8801/openapi.json

Usage:
    python tool-transport/nmap-api.py
    python tool-transport/nmap-api.py --backend docker   # use Docker container instead
"""

import argparse
import json
import re
import subprocess
import sys
import logging

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel, Field
    import uvicorn
except ImportError:
    print("Missing dependencies. Install with:")
    print("  pip install fastapi uvicorn pydantic")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("nmap-api")

HOST = "0.0.0.0"
PORT = 8801

# Backend config — set via command line
BACKEND = "wsl"  # "wsl" or "docker"
WSL_DISTRO = "kali-linux"
DOCKER_CONTAINER = "kali-mcp-pentest"

app = FastAPI(
    title="Nmap Scanner",
    description="Run nmap scans via Kali Linux (WSL2). For authorized penetration testing only.",
    version="1.0.0",
    servers=[{"url": f"http://localhost:{PORT}"}]
)


class ScanRequest(BaseModel):
    target: str = Field(..., description="IP address, hostname, or CIDR range to scan")
    scan_type: str = Field(
        default="-sS",
        description="Nmap scan type: -sS (SYN), -sT (TCP), -sU (UDP), -sV (version), -sn (ping), -A (aggressive), -sC (scripts), -O (OS detect)"
    )
    ports: str | None = Field(default=None, description="Ports to scan, e.g. '80', '22,80,443', '1-1000'. Omit for top 1000.")
    scripts: str | None = Field(default=None, description="NSE scripts, e.g. 'vuln', 'http-enum', 'ssl-enum-ciphers'")
    extra_args: str | None = Field(default=None, description="Extra nmap flags, e.g. '-T4 --open -Pn'")
    timeout: int = Field(default=300, ge=10, le=900, description="Max scan time in seconds")


class ScanResult(BaseModel):
    command: str
    output: str
    exit_code: int
    warnings: str | None = None
    error: bool = False
    message: str | None = None


VALID_SCAN_TYPES = ["-sS", "-sT", "-sU", "-sA", "-sF", "-sX", "-sN", "-sn", "-sV", "-O", "-A", "-sC"]


def _sanitize(value: str, pattern: str, name: str) -> str:
    value = value.strip()
    if not re.match(pattern, value):
        raise HTTPException(status_code=400, detail=f"Invalid {name}: {value}")
    return value


def _build_exec_cmd(nmap_cmd: str) -> list[str]:
    """Build the subprocess command based on backend."""
    if BACKEND == "wsl":
        # No sudo — WSL user typically doesn't have passwordless sudo.
        # Use -sT (TCP connect) instead of -sS (SYN) when not root.
        return ["wsl.exe", "-d", WSL_DISTRO, "--", "bash", "-c", nmap_cmd]
    else:
        return ["docker", "exec", DOCKER_CONTAINER, "bash", "-c", nmap_cmd]


@app.post("/nmap_scan", summary="Run an nmap scan", response_model=ScanResult)
async def nmap_scan(req: ScanRequest) -> ScanResult:
    """Execute an nmap scan against the specified target using Kali Linux."""

    target = _sanitize(req.target, r'^[a-zA-Z0-9\.\-\:\/\,\s\*]+$', "target")
    if len(target) > 500:
        raise HTTPException(status_code=400, detail="Target string too long")

    if req.scan_type not in VALID_SCAN_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid scan_type: {req.scan_type}")

    cmd_parts = ["nmap", req.scan_type]

    if req.ports:
        ports = _sanitize(req.ports, r'^[\d\-\,U:T:]+$', "ports")
        cmd_parts.extend(["-p", ports])

    if req.scripts:
        scripts = _sanitize(req.scripts, r'^[a-zA-Z0-9\-\_\,\*]+$', "scripts")
        cmd_parts.extend(["--script", scripts])

    if req.extra_args:
        forbidden = [";", "&&", "||", "|", "`", "$(", ">>", ">", "<"]
        for f in forbidden:
            if f in req.extra_args:
                raise HTTPException(status_code=400, detail=f"Forbidden character in extra_args: {f}")
        cmd_parts.extend(req.extra_args.strip().split())

    cmd_parts.append(target)
    nmap_cmd = " ".join(cmd_parts)

    logger.info(f"[{BACKEND}] Executing: {nmap_cmd}")

    exec_cmd = _build_exec_cmd(nmap_cmd)

    try:
        result = subprocess.run(
            exec_cmd,
            capture_output=True, text=True, timeout=req.timeout + 30
        )

        output = result.stdout.strip()
        stderr = result.stderr.strip()

        if not output and result.returncode != 0:
            return ScanResult(
                command=nmap_cmd, output="(no output)", exit_code=result.returncode,
                error=True, message=f"Scan failed (exit {result.returncode}): {stderr[:500]}"
            )

        return ScanResult(
            command=nmap_cmd,
            output=output if output else "(no output)",
            exit_code=result.returncode,
            warnings=stderr[:2000] if stderr and result.returncode != 0 else None
        )

    except subprocess.TimeoutExpired:
        return ScanResult(
            command=nmap_cmd, output="", exit_code=-1, error=True,
            message=f"Scan timed out after {req.timeout}s. Try: fewer ports, -T4, or narrower target range."
        )
    except FileNotFoundError:
        backend_name = "wsl.exe" if BACKEND == "wsl" else "docker"
        return ScanResult(
            command=nmap_cmd, output="", exit_code=-1, error=True,
            message=f"{backend_name} not found. Is it installed and running?"
        )
    except Exception as e:
        return ScanResult(
            command=nmap_cmd, output="", exit_code=-1, error=True,
            message=str(e)
        )


@app.get("/health")
async def health():
    """Check if the nmap API and Kali Linux are operational."""
    try:
        if BACKEND == "wsl":
            r = subprocess.run(
                ["wsl.exe", "-d", WSL_DISTRO, "--", "nmap", "--version"],
                capture_output=True, text=True, timeout=10
            )
        else:
            r = subprocess.run(
                ["docker", "exec", DOCKER_CONTAINER, "nmap", "--version"],
                capture_output=True, text=True, timeout=10
            )

        if r.returncode == 0:
            version = r.stdout.strip().split("\n")[0]
            return {"status": "healthy", "nmap": version, "backend": BACKEND,
                    "target": WSL_DISTRO if BACKEND == "wsl" else DOCKER_CONTAINER}
        else:
            return {"status": "degraded", "error": r.stderr.strip()[:200]}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nmap Tool API")
    parser.add_argument("--backend", choices=["wsl", "docker"], default="wsl",
                        help="Execution backend: 'wsl' (default) or 'docker'")
    parser.add_argument("--distro", default="kali-linux", help="WSL distro name (default: kali-linux)")
    parser.add_argument("--container", default="kali-mcp-pentest", help="Docker container name")
    parser.add_argument("--port", type=int, default=8801, help="API port (default: 8801)")
    args = parser.parse_args()

    BACKEND = args.backend
    WSL_DISTRO = args.distro
    DOCKER_CONTAINER = args.container
    PORT = args.port

    print(f"Nmap Tool API starting on http://localhost:{PORT}")
    print(f"Backend:      {BACKEND} ({'distro: ' + WSL_DISTRO if BACKEND == 'wsl' else 'container: ' + DOCKER_CONTAINER})")
    print(f"OpenAPI spec: http://localhost:{PORT}/openapi.json")
    print(f"Swagger UI:   http://localhost:{PORT}/docs")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
