"""
title: theHarvester OSINT Tool
author: openclaw-intel
version: 0.1.0
description: Runs theHarvester for email, subdomain, IP, and name harvesting from public sources. Passive reconnaissance only.
"""

import subprocess
import asyncio
from pydantic import BaseModel, Field
from typing import Optional


class Tools:
    class Valves(BaseModel):
        timeout: int = Field(
            default=120,
            description="Maximum execution time in seconds before killing the process.",
        )
        wsl_distro: str = Field(
            default="kali-linux",
            description="WSL distribution name where theHarvester is installed.",
        )
        default_sources: str = Field(
            default="google,bing,dnsdumpster,crtsh,urlscan",
            description="Comma-separated default data sources when none specified.",
        )
        max_output_lines: int = Field(
            default=500,
            description="Maximum output lines to return to prevent context overflow.",
        )

    def __init__(self):
        self.valves = self.Valves()

    async def run_theharvester(
        self,
        domain: str,
        sources: Optional[str] = None,
        limit: Optional[int] = 200,
        start: Optional[int] = 0,
        dns_lookup: Optional[bool] = False,
        __event_emitter__=None,
    ) -> str:
        """
        Run theHarvester to gather emails, subdomains, IPs, and names for a target domain.
        This is a PASSIVE reconnaissance tool — it queries public search engines and databases only.

        :param domain: Target domain to investigate (e.g., example.com).
        :param sources: Comma-separated data sources (e.g., google,bing,crtsh). Uses defaults if empty.
        :param limit: Maximum number of results to harvest per source.
        :param start: Result number to start from (for pagination).
        :param dns_lookup: If true, perform DNS resolution on discovered hosts.
        :return: Raw theHarvester output including discovered emails, hosts, and IPs.
        """
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Running theHarvester against {domain}...",
                        "done": False,
                    },
                }
            )

        src = sources if sources else self.valves.default_sources

        cmd_parts = [
            "theHarvester",
            "-d", domain,
            "-b", src,
            "-l", str(limit),
            "-S", str(start),
        ]

        if dns_lookup:
            cmd_parts.append("-n")

        cmd_str = " ".join(cmd_parts)
        wsl_cmd = f'wsl -d {self.valves.wsl_distro} -- bash -c "{cmd_str}"'

        try:
            process = await asyncio.create_subprocess_shell(
                wsl_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=self.valves.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return f"ERROR: theHarvester timed out after {self.valves.timeout}s. Try reducing the limit or narrowing sources.\nCommand: {cmd_str}"

            output = stdout.decode("utf-8", errors="replace")
            err_output = stderr.decode("utf-8", errors="replace")

            lines = output.strip().split("\n")
            if len(lines) > self.valves.max_output_lines:
                output = "\n".join(lines[: self.valves.max_output_lines])
                output += f"\n\n[OUTPUT TRUNCATED — {len(lines)} total lines, showing first {self.valves.max_output_lines}]"

            result = f"TOOL: theHarvester\nCOMMAND: {cmd_str}\nTARGET: {domain}\nSOURCES: {src}\n{'=' * 60}\n\n{output}"

            if err_output.strip() and process.returncode != 0:
                result += f"\n\nSTDERR:\n{err_output.strip()}"

            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": f"theHarvester scan complete for {domain}.",
                            "done": True,
                        },
                    }
                )

            return result

        except Exception as e:
            return f"ERROR: Failed to run theHarvester.\nCommand: {cmd_str}\nException: {str(e)}\n\nTroubleshooting:\n1. Verify WSL distro name: wsl -l -v\n2. Verify theHarvester is installed: wsl -d {self.valves.wsl_distro} -- which theHarvester\n3. Check network connectivity from WSL."
