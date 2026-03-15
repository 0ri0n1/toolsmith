#!/usr/bin/env python3
"""
Model Forge — Nmap MCP Server
Exposes nmap scanning via the kali-mcp Docker container as an MCP tool.
Designed for MCPO bridge → Open WebUI integration.

Transport: stdio (for MCPO)
Runtime: Runs on Windows host, executes nmap inside kali-mcp-pentest container.
"""

import json
import logging
import subprocess
import sys
import re

from mcp.server.fastmcp import FastMCP

logging.basicConfig(
    level=logging.INFO, stream=sys.stderr,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("nmap-mcp")

CONTAINER = "kali-mcp-pentest"
DEFAULT_TIMEOUT = 300
MAX_TIMEOUT = 900

VALID_SCAN_TYPES = ["-sS", "-sT", "-sU", "-sA", "-sF", "-sX", "-sN", "-sn", "-sV", "-O", "-A", "-sC"]

mcp = FastMCP(
    "nmap",
    instructions=(
        "Nmap network scanner running inside a Kali Linux container. "
        "Use nmap_scan to discover hosts, scan ports, detect services, "
        "and run NSE vulnerability scripts against authorized targets."
    )
)


def _sanitize_target(target: str) -> str:
    """Basic input validation for scan targets."""
    target = target.strip()
    # Allow IPs, CIDR, hostnames, ranges
    if not re.match(r'^[a-zA-Z0-9\.\-\:\/\,\s\*]+$', target):
        raise ValueError(f"Invalid target format: {target}")
    if len(target) > 500:
        raise ValueError("Target string too long")
    return target


def _sanitize_args(args: str) -> str:
    """Reject dangerous shell metacharacters in extra_args."""
    forbidden = [";", "&&", "||", "|", "`", "$(", ">>", ">", "<", "\\n"]
    for f in forbidden:
        if f in args:
            raise ValueError(f"Forbidden character sequence in extra_args: {f}")
    return args.strip()


@mcp.tool()
def nmap_scan(
    target: str,
    scan_type: str = "-sS",
    ports: str | None = None,
    scripts: str | None = None,
    extra_args: str | None = None,
    timeout: int = 300
) -> str:
    """Run an nmap scan against a target from the Kali Linux container.

    Args:
        target: IP address, hostname, CIDR range, or space-separated list of targets
        scan_type: Nmap scan technique. One of: -sS, -sT, -sU, -sA, -sF, -sX, -sN, -sn, -sV, -O, -A, -sC
        ports: Port specification. Examples: '80', '1-1000', '22,80,443'. Omit for default top 1000.
        scripts: NSE scripts to run. Examples: 'vuln', 'http-enum', 'ssl-enum-ciphers,http-title'
        extra_args: Additional nmap flags. Examples: '-T4 --open', '-Pn', '-v --top-ports 100'
        timeout: Max scan time in seconds (10-900, default 300)
    """
    try:
        target = _sanitize_target(target)
    except ValueError as e:
        return json.dumps({"error": True, "message": str(e)})

    if scan_type not in VALID_SCAN_TYPES:
        return json.dumps({"error": True, "message": f"Invalid scan_type: {scan_type}. Valid: {VALID_SCAN_TYPES}"})

    timeout = max(10, min(timeout, MAX_TIMEOUT))

    # Build nmap command
    cmd_parts = ["nmap", scan_type]

    if ports:
        ports = ports.strip()
        if not re.match(r'^[\d\-\,U:T:]+$', ports):
            return json.dumps({"error": True, "message": f"Invalid port specification: {ports}"})
        cmd_parts.extend(["-p", ports])

    if scripts:
        scripts = scripts.strip()
        if not re.match(r'^[a-zA-Z0-9\-\_\,\*]+$', scripts):
            return json.dumps({"error": True, "message": f"Invalid script specification: {scripts}"})
        cmd_parts.extend(["--script", scripts])

    if extra_args:
        try:
            extra_args = _sanitize_args(extra_args)
        except ValueError as e:
            return json.dumps({"error": True, "message": str(e)})
        cmd_parts.extend(extra_args.split())

    cmd_parts.append(target)
    nmap_cmd = " ".join(cmd_parts)

    logger.info(f"Running: docker exec {CONTAINER} {nmap_cmd}")

    try:
        result = subprocess.run(
            ["docker", "exec", CONTAINER, "bash", "-c", nmap_cmd],
            capture_output=True, text=True, timeout=timeout + 30
        )

        output = result.stdout.strip()
        stderr = result.stderr.strip()

        if result.returncode != 0 and not output:
            return json.dumps({
                "error": True,
                "message": f"Nmap exited with code {result.returncode}",
                "stderr": stderr[:2000] if stderr else None,
                "command": nmap_cmd
            })

        # Return structured result
        response = {
            "command": nmap_cmd,
            "output": output[:15000] if output else "(no output)",
            "exit_code": result.returncode
        }
        if stderr and result.returncode != 0:
            response["warnings"] = stderr[:2000]

        return json.dumps(response, indent=2)

    except subprocess.TimeoutExpired:
        return json.dumps({
            "error": True,
            "message": f"Scan timed out after {timeout} seconds. Try narrowing the target or port range.",
            "command": nmap_cmd
        })
    except FileNotFoundError:
        return json.dumps({
            "error": True,
            "message": "Docker not found. Ensure Docker is running and the kali-mcp-pentest container is up."
        })
    except Exception as e:
        return json.dumps({"error": True, "message": str(e), "command": nmap_cmd})


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
