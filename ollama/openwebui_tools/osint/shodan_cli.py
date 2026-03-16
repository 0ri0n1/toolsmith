"""
title: Shodan CLI OSINT Tool
author: openclaw-intel
version: 0.1.0
description: Runs Shodan CLI for internet-connected device intelligence — open ports, services, vulnerabilities, banners, and org data.
"""

import subprocess
import asyncio
from pydantic import BaseModel, Field
from typing import Optional


class Tools:
    class Valves(BaseModel):
        timeout: int = Field(
            default=60,
            description="Maximum execution time in seconds.",
        )
        wsl_distro: str = Field(
            default="kali-linux",
            description="WSL distribution name where Shodan CLI is installed.",
        )
        max_output_lines: int = Field(
            default=500,
            description="Maximum output lines to return.",
        )
        api_key_env: str = Field(
            default="SHODAN_API_KEY",
            description="Environment variable name holding the Shodan API key. Must be set in WSL environment.",
        )

    def __init__(self):
        self.valves = self.Valves()

    async def _run_shodan(self, cmd_str: str, __event_emitter__=None) -> str:
        wsl_cmd = f'wsl -d {self.valves.wsl_distro} -- bash -c \'{cmd_str}\''

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
            return f"ERROR: Shodan timed out after {self.valves.timeout}s.\nCommand: {cmd_str}"

        output = stdout.decode("utf-8", errors="replace")
        err_output = stderr.decode("utf-8", errors="replace")

        lines = output.strip().split("\n")
        if len(lines) > self.valves.max_output_lines:
            output = "\n".join(lines[: self.valves.max_output_lines])
            output += f"\n\n[TRUNCATED — {len(lines)} total lines]"

        result = f"TOOL: Shodan\nCOMMAND: {cmd_str}\n{'=' * 60}\n\n{output}"

        if err_output.strip() and process.returncode != 0:
            result += f"\n\nSTDERR:\n{err_output.strip()}"

        return result

    async def shodan_host(
        self,
        ip_address: str,
        __event_emitter__=None,
    ) -> str:
        """
        Look up a specific IP address in Shodan to see open ports, running services, banners, and known vulnerabilities.

        :param ip_address: Target IP address to look up (e.g., 1.2.3.4).
        :return: Host details including open ports, services, banners, OS, organization, and CVEs.
        """
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Querying Shodan for host {ip_address}...",
                        "done": False,
                    },
                }
            )

        cmd_str = f"shodan host {ip_address}"
        result = await self._run_shodan(cmd_str)

        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Shodan host lookup complete for {ip_address}.",
                        "done": True,
                    },
                }
            )

        return result

    async def shodan_search(
        self,
        query: str,
        limit: Optional[int] = 20,
        __event_emitter__=None,
    ) -> str:
        """
        Search Shodan for internet-connected devices matching a query.
        Supports Shodan query syntax (org, port, country, product, vuln, etc.).

        :param query: Shodan search query (e.g., 'org:"Target Corp"', 'port:22 country:CA', 'apache city:"Edmonton"').
        :param limit: Maximum number of results to return.
        :return: Matching hosts with IPs, ports, services, and banners.
        """
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Searching Shodan: {query}...",
                        "done": False,
                    },
                }
            )

        cmd_str = f'shodan search --limit {limit} "{query}"'
        result = await self._run_shodan(cmd_str)

        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": "Shodan search complete.",
                        "done": True,
                    },
                }
            )

        return result

    async def shodan_domain(
        self,
        domain: str,
        __event_emitter__=None,
    ) -> str:
        """
        Get DNS and subdomain information for a domain from Shodan.

        :param domain: Target domain (e.g., example.com).
        :return: DNS records, subdomains, and associated IPs.
        """
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Querying Shodan DNS for {domain}...",
                        "done": False,
                    },
                }
            )

        cmd_str = f"shodan domain {domain}"
        result = await self._run_shodan(cmd_str)

        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Shodan domain lookup complete for {domain}.",
                        "done": True,
                    },
                }
            )

        return result
