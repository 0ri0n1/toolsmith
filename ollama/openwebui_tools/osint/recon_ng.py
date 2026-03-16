"""
title: Recon-ng OSINT Tool
author: openclaw-intel
version: 0.1.0
description: Runs Recon-ng modules for modular web reconnaissance — WHOIS, DNS, host discovery, contact harvesting.
"""

import subprocess
import asyncio
from pydantic import BaseModel, Field
from typing import Optional


class Tools:
    class Valves(BaseModel):
        timeout: int = Field(
            default=180,
            description="Maximum execution time in seconds.",
        )
        wsl_distro: str = Field(
            default="kali-linux",
            description="WSL distribution name where Recon-ng is installed.",
        )
        workspace: str = Field(
            default="osint_default",
            description="Recon-ng workspace name for this session.",
        )
        max_output_lines: int = Field(
            default=500,
            description="Maximum output lines to return.",
        )

    def __init__(self):
        self.valves = self.Valves()

    async def recon_ng_run_module(
        self,
        module: str,
        source: str,
        options: Optional[str] = None,
        __event_emitter__=None,
    ) -> str:
        """
        Run a specific Recon-ng module against a target source.
        Automates OSINT workflows with API-backed modules for WHOIS, DNS, host discovery, and more.

        :param module: Full Recon-ng module path (e.g., recon/domains-hosts/hackertarget, recon/hosts-hosts/resolve).
        :param source: Target input for the module (domain, IP, email, etc.).
        :param options: Optional extra SET commands as semicolon-separated pairs (e.g., "NAMESERVER=8.8.8.8;TIMEOUT=30").
        :return: Recon-ng module output.
        """
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Running Recon-ng module {module}...",
                        "done": False,
                    },
                }
            )

        rc_commands = [
            f"workspaces create {self.valves.workspace}",
            f"modules load {module}",
            f"options set SOURCE {source}",
        ]

        if options:
            for pair in options.split(";"):
                pair = pair.strip()
                if "=" in pair:
                    key, val = pair.split("=", 1)
                    rc_commands.append(f"options set {key.strip()} {val.strip()}")

        rc_commands.append("run")
        rc_commands.append("exit")

        rc_script = "\\n".join(rc_commands)
        cmd_str = f'echo -e "{rc_script}" | recon-ng'
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
                return f"ERROR: Recon-ng timed out after {self.valves.timeout}s.\nModule: {module}\nSource: {source}"

            output = stdout.decode("utf-8", errors="replace")
            err_output = stderr.decode("utf-8", errors="replace")

            lines = output.strip().split("\n")
            if len(lines) > self.valves.max_output_lines:
                output = "\n".join(lines[: self.valves.max_output_lines])
                output += f"\n\n[TRUNCATED — {len(lines)} total lines]"

            result = f"TOOL: Recon-ng\nMODULE: {module}\nSOURCE: {source}\n{'=' * 60}\n\n{output}"

            if err_output.strip() and process.returncode != 0:
                result += f"\n\nSTDERR:\n{err_output.strip()}"

            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": f"Recon-ng module {module} complete.",
                            "done": True,
                        },
                    }
                )

            return result

        except Exception as e:
            return f"ERROR: Failed to run Recon-ng.\nModule: {module}\nException: {str(e)}"

    async def recon_ng_search_modules(
        self,
        keyword: str,
        __event_emitter__=None,
    ) -> str:
        """
        Search available Recon-ng modules by keyword. Use this to find the right module before running it.

        :param keyword: Keyword to search for in the module marketplace (e.g., whois, dns, email, hosts).
        :return: List of matching modules with descriptions.
        """
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Searching Recon-ng modules for '{keyword}'...",
                        "done": False,
                    },
                }
            )

        rc_commands = [
            f"marketplace search {keyword}",
            "exit",
        ]
        rc_script = "\\n".join(rc_commands)
        cmd_str = f'echo -e "{rc_script}" | recon-ng'
        wsl_cmd = f'wsl -d {self.valves.wsl_distro} -- bash -c \'{cmd_str}\''

        try:
            process = await asyncio.create_subprocess_shell(
                wsl_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=60
            )

            output = stdout.decode("utf-8", errors="replace")

            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": "Module search complete.",
                            "done": True,
                        },
                    }
                )

            return f"TOOL: Recon-ng Module Search\nKEYWORD: {keyword}\n{'=' * 60}\n\n{output}"

        except Exception as e:
            return f"ERROR: Failed to search Recon-ng modules.\nException: {str(e)}"
