#!/usr/bin/env python3
"""
Nmap Tool API — lightweight HTTP endpoint for Open WebUI tool integration.

Runs on the Windows host, executes nmap inside the kali-mcp-pentest Docker container.
Register this in Open WebUI as an OpenAPI tool at http://localhost:8801/openapi.json

Usage:
    python tool-transport/nmap-api.py
    # or: uv run tool-transport/nmap-api.py
"""

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
    print("  # or: uv pip install fastapi uvicorn pydantic")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("nmap-api")

CONTAINER = "kali-mcp-pentest"
HOST = "0.0.0.0"
PORT = 8801

app = FastAPI(
    title="Nmap Scanner",
    description="Run nmap scans via Kali Linux container. For authorized penetration testing only.",
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


@app.post("/nmap_scan", summary="Run an nmap scan", response_model=ScanResult)
async def nmap_scan(req: ScanRequest) -> ScanResult:
    """Execute an nmap scan against the specified target using the Kali Linux container."""

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

    logger.info(f"Executing: {nmap_cmd}")

    try:
        result = subprocess.run(
            ["docker", "exec", CONTAINER, "bash", "-c", nmap_cmd],
            capture_output=True, text=True, timeout=req.timeout + 30
        )

        output = result.stdout.strip()
        stderr = result.stderr.strip()

        return ScanResult(
            command=nmap_cmd,
            output=output if output else "(no output)",
            exit_code=result.returncode,
            warnings=stderr[:2000] if stderr and result.returncode != 0 else None
        )

    except subprocess.TimeoutExpired:
        return ScanResult(
            command=nmap_cmd, output="", exit_code=-1, error=True,
            message=f"Scan timed out after {req.timeout}s. Narrow the target or port range."
        )
    except FileNotFoundError:
        return ScanResult(
            command=nmap_cmd, output="", exit_code=-1, error=True,
            message="Docker not found. Is Docker running?"
        )
    except Exception as e:
        return ScanResult(
            command=nmap_cmd, output="", exit_code=-1, error=True,
            message=str(e)
        )


@app.get("/health")
async def health():
    """Check if the nmap API and Kali container are operational."""
    try:
        r = subprocess.run(
            ["docker", "exec", CONTAINER, "nmap", "--version"],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode == 0:
            version = r.stdout.strip().split("\n")[0]
            return {"status": "healthy", "nmap": version, "container": CONTAINER}
        else:
            return {"status": "degraded", "error": r.stderr.strip()[:200]}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


if __name__ == "__main__":
    print(f"Nmap Tool API starting on http://localhost:{PORT}")
    print(f"OpenAPI spec: http://localhost:{PORT}/openapi.json")
    print(f"Swagger UI:   http://localhost:{PORT}/docs")
    print(f"Container:    {CONTAINER}")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
