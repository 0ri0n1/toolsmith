"""
title: SpiderFoot OSINT Scanner
author: openclaw-intel
version: 0.1.0
description: Runs SpiderFoot automated OSINT scans — 200+ modules scanning a target across dozens of data sources in one run.
"""

import subprocess
import asyncio
from pydantic import BaseModel, Field
from typing import Optional


class Tools:
    class Valves(BaseModel):
        timeout: int = Field(
            default=300,
            description="Maximum execution time in seconds. SpiderFoot scans can be long.",
        )
        wsl_distro: str = Field(
            default="kali-linux",
            description="WSL distribution name where SpiderFoot is installed.",
        )
        max_output_lines: int = Field(
            default=800,
            description="Maximum output lines to return. SpiderFoot produces verbose output.",
        )
        spiderfoot_path: str = Field(
            default="spiderfoot",
            description="Path to SpiderFoot CLI binary (sfcli or spiderfoot).",
        )

    def __init__(self):
        self.valves = self.Valves()

    async def spiderfoot_scan(
        self,
        target: str,
        scan_types: Optional[str] = None,
        modules: Optional[str] = None,
        max_threads: Optional[int] = 10,
        __event_emitter__=None,
    ) -> str:
        """
        Run a SpiderFoot automated OSINT scan against a target.
        Scans across 200+ data sources for emails, domains, IPs, names, phone numbers, and more.

        :param target: The scan target — domain, IP, email, phone number, or person name.
        :param scan_types: Comma-separated entity types to scan for (e.g., INTERNET_NAME,EMAILADDR,PHONE_NUMBER,IP_ADDRESS). Defaults to all.
        :param modules: Comma-separated specific modules to use. Leave empty for auto-selection based on target type.
        :param max_threads: Maximum concurrent scanning threads.
        :return: SpiderFoot scan results.
        """
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Starting SpiderFoot scan on {target}... This may take several minutes.",
                        "done": False,
                    },
                }
            )

        cmd_parts = [
            self.valves.spiderfoot_path,
            "-s", f'"{target}"',
            "-q",
            "-max-threads", str(max_threads),
        ]

        if scan_types:
            cmd_parts.extend(["-t", scan_types])

        if modules:
            cmd_parts.extend(["-m", modules])

        cmd_str = " ".join(cmd_parts)
        wsl_cmd = f'wsl -d {self.valves.wsl_distro} -- bash -c \'{cmd_str}\''

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
                return f"ERROR: SpiderFoot timed out after {self.valves.timeout}s. SpiderFoot scans can be lengthy.\nTarget: {target}\nCommand: {cmd_str}\n\nSuggestions:\n1. Increase timeout in Valves settings\n2. Narrow scan with -t flag (specific entity types)\n3. Use specific modules with -m flag"

            output = stdout.decode("utf-8", errors="replace")
            err_output = stderr.decode("utf-8", errors="replace")

            lines = output.strip().split("\n")
            if len(lines) > self.valves.max_output_lines:
                output = "\n".join(lines[: self.valves.max_output_lines])
                output += f"\n\n[TRUNCATED — {len(lines)} total lines]"

            result = f"TOOL: SpiderFoot\nTARGET: {target}\nSCAN TYPES: {scan_types or 'ALL'}\n{'=' * 60}\n\n{output}"

            if err_output.strip() and process.returncode != 0:
                result += f"\n\nSTDERR:\n{err_output.strip()}"

            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": f"SpiderFoot scan complete for {target}.",
                            "done": True,
                        },
                    }
                )

            return result

        except Exception as e:
            return f"ERROR: Failed to run SpiderFoot.\nTarget: {target}\nCommand: {cmd_str}\nException: {str(e)}"
