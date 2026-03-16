"""
title: PhoneInfoga Phone Number OSINT
author: openclaw-intel
version: 0.1.0
description: Runs PhoneInfoga for phone number intelligence — carrier, location, line type, linked accounts, and reputation.
"""

import subprocess
import asyncio
from pydantic import BaseModel, Field
from typing import Optional


class Tools:
    class Valves(BaseModel):
        timeout: int = Field(
            default=90,
            description="Maximum execution time in seconds.",
        )
        wsl_distro: str = Field(
            default="kali-linux",
            description="WSL distribution name where PhoneInfoga is installed.",
        )
        max_output_lines: int = Field(
            default=300,
            description="Maximum output lines to return.",
        )

    def __init__(self):
        self.valves = self.Valves()

    async def phoneinfoga_scan(
        self,
        phone_number: str,
        scanners: Optional[str] = None,
        __event_emitter__=None,
    ) -> str:
        """
        Scan a phone number using PhoneInfoga to gather carrier info, location data, line type, and linked accounts.
        Input the number in international format with country code (e.g., +14035551234).

        :param phone_number: Phone number in international format (e.g., +14035551234 or +441234567890).
        :param scanners: Comma-separated specific scanners to use (e.g., local,numverify,googlecse). Leave empty for all.
        :return: Phone number intelligence including carrier, location, line type, and linked account data.
        """
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Scanning phone number {phone_number}...",
                        "done": False,
                    },
                }
            )

        cmd_parts = [
            "phoneinfoga",
            "scan",
            "-n", f'"{phone_number}"',
        ]

        if scanners:
            cmd_parts.extend(["-s", scanners])

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
                return f"ERROR: PhoneInfoga timed out after {self.valves.timeout}s.\nNumber: {phone_number}"

            output = stdout.decode("utf-8", errors="replace")
            err_output = stderr.decode("utf-8", errors="replace")

            lines = output.strip().split("\n")
            if len(lines) > self.valves.max_output_lines:
                output = "\n".join(lines[: self.valves.max_output_lines])
                output += f"\n\n[TRUNCATED — {len(lines)} total lines]"

            result = f"TOOL: PhoneInfoga\nNUMBER: {phone_number}\n{'=' * 60}\n\n{output}"

            if err_output.strip() and process.returncode != 0:
                result += f"\n\nSTDERR:\n{err_output.strip()}"

            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": f"PhoneInfoga scan complete for {phone_number}.",
                            "done": True,
                        },
                    }
                )

            return result

        except Exception as e:
            return f"ERROR: Failed to run PhoneInfoga.\nNumber: {phone_number}\nException: {str(e)}"
