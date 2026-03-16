"""
title: Sherlock Username OSINT
author: openclaw-intel
version: 0.1.0
description: Runs Sherlock to enumerate usernames across 400+ social platforms. Finds accounts linked to a username.
"""

import subprocess
import asyncio
from pydantic import BaseModel, Field
from typing import Optional


class Tools:
    class Valves(BaseModel):
        timeout: int = Field(
            default=120,
            description="Maximum execution time in seconds.",
        )
        wsl_distro: str = Field(
            default="kali-linux",
            description="WSL distribution name where Sherlock is installed.",
        )
        max_output_lines: int = Field(
            default=500,
            description="Maximum output lines to return.",
        )

    def __init__(self):
        self.valves = self.Valves()

    async def sherlock_lookup(
        self,
        username: str,
        sites: Optional[str] = None,
        request_timeout: Optional[int] = 10,
        print_found_only: Optional[bool] = True,
        __event_emitter__=None,
    ) -> str:
        """
        Search for a username across 400+ social media platforms and websites.
        Returns URLs where the username was found active.

        :param username: The username to search for across platforms.
        :param sites: Comma-separated specific sites to check (e.g., twitter,github,instagram). Leave empty to check all.
        :param request_timeout: Timeout per site request in seconds.
        :param print_found_only: If true, only show sites where the username was found.
        :return: List of platforms where the username exists with profile URLs.
        """
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Running Sherlock lookup for username '{username}'...",
                        "done": False,
                    },
                }
            )

        cmd_parts = [
            "sherlock",
            f'"{username}"',
            "--timeout", str(request_timeout),
        ]

        if print_found_only:
            cmd_parts.append("--print-found")

        if sites:
            for site in sites.split(","):
                cmd_parts.extend(["--site", site.strip()])

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
                return f"ERROR: Sherlock timed out after {self.valves.timeout}s.\nUsername: {username}\n\nSuggestions:\n1. Increase timeout in Valves\n2. Narrow search with --site flag\n3. Check WSL network connectivity"

            output = stdout.decode("utf-8", errors="replace")
            err_output = stderr.decode("utf-8", errors="replace")

            lines = output.strip().split("\n")
            found_count = sum(1 for line in lines if "http" in line.lower())

            if len(lines) > self.valves.max_output_lines:
                output = "\n".join(lines[: self.valves.max_output_lines])
                output += f"\n\n[TRUNCATED — {len(lines)} total lines]"

            result = f"TOOL: Sherlock\nUSERNAME: {username}\nPLATFORMS FOUND: {found_count}\n{'=' * 60}\n\n{output}"

            if err_output.strip() and process.returncode != 0:
                result += f"\n\nSTDERR:\n{err_output.strip()}"

            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": f"Sherlock complete — found {found_count} profiles for '{username}'.",
                            "done": True,
                        },
                    }
                )

            return result

        except Exception as e:
            return f"ERROR: Failed to run Sherlock.\nUsername: {username}\nException: {str(e)}"
