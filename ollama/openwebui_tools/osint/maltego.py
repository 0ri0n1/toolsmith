"""
title: Maltego CE Link Analysis
author: openclaw-intel
version: 0.1.0
description: Runs Maltego CE transforms via CLI for visual link analysis — connects people, emails, domains, IPs, and organizations into relationship graphs.
"""

import subprocess
import asyncio
import json
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
            description="WSL distribution name where Maltego is installed.",
        )
        max_output_lines: int = Field(
            default=500,
            description="Maximum output lines to return.",
        )
        maltego_path: str = Field(
            default="maltego",
            description="Path to Maltego binary. Some installs use /usr/bin/maltego or /opt/maltego/bin/maltego.",
        )

    def __init__(self):
        self.valves = self.Valves()

    async def maltego_transform(
        self,
        entity_type: str,
        entity_value: str,
        transform: Optional[str] = None,
        __event_emitter__=None,
    ) -> str:
        """
        Run a Maltego transform on an entity to discover relationships and linked data.
        Maltego connects entities (people, emails, domains, IPs, orgs) into relationship graphs.

        NOTE: Maltego CE has limited CLI automation. This tool runs transforms via maltego-trx
        or casefile export. For full GUI transforms, the operator should use Maltego directly
        and paste results back for analysis.

        :param entity_type: Entity type (e.g., Domain, EmailAddress, Person, PhoneNumber, IPAddress, Company, URL).
        :param entity_value: The entity value to investigate (e.g., example.com, john@example.com, 1.2.3.4).
        :param transform: Specific transform to run. Leave empty for recommended transforms based on entity type.
        :return: Transform results showing discovered linked entities and relationships.
        """
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Running Maltego transform on {entity_type}: {entity_value}...",
                        "done": False,
                    },
                }
            )

        entity_map = {
            "Domain": "maltego.Domain",
            "EmailAddress": "maltego.EmailAddress",
            "Person": "maltego.Person",
            "PhoneNumber": "maltego.PhoneNumber",
            "IPAddress": "maltego.IPv4Address",
            "Company": "maltego.Company",
            "URL": "maltego.URL",
        }

        maltego_entity = entity_map.get(entity_type, f"maltego.{entity_type}")

        # Maltego CE CLI is limited — use casefile/transform runner if available
        # Fall back to structured guidance if CLI transforms aren't available
        if transform:
            cmd_str = f'{self.valves.maltego_path} -run-transform {transform} -entity "{maltego_entity}={entity_value}"'
        else:
            cmd_str = f'{self.valves.maltego_path} -entity "{maltego_entity}={entity_value}" -auto-transforms'

        wsl_cmd = f'wsl -d {self.valves.wsl_distro} -- bash -c \'{cmd_str}\' 2>&1 || echo "MALTEGO_CLI_FALLBACK"'

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
                return self._manual_guidance(entity_type, entity_value, transform)

            output = stdout.decode("utf-8", errors="replace")

            if "MALTEGO_CLI_FALLBACK" in output or process.returncode != 0:
                return self._manual_guidance(entity_type, entity_value, transform)

            lines = output.strip().split("\n")
            if len(lines) > self.valves.max_output_lines:
                output = "\n".join(lines[: self.valves.max_output_lines])
                output += f"\n\n[TRUNCATED — {len(lines)} total lines]"

            result = f"TOOL: Maltego CE\nENTITY: {maltego_entity} = {entity_value}\n{'=' * 60}\n\n{output}"

            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": f"Maltego transform complete for {entity_value}.",
                            "done": True,
                        },
                    }
                )

            return result

        except Exception as e:
            return self._manual_guidance(entity_type, entity_value, transform)

    def _manual_guidance(self, entity_type: str, entity_value: str, transform: str = None) -> str:
        transform_suggestions = {
            "Domain": [
                "To DNS Name - Find subdomains",
                "To Email Address - Harvest emails",
                "To IP Address - Resolve domain",
                "To Website - Find hosted sites",
                "To WHOIS - Registration info",
            ],
            "EmailAddress": [
                "To Person - Find owner",
                "To Domain - Extract domain",
                "To Social Media - Find linked accounts",
                "To Breach Data - Check breaches",
            ],
            "Person": [
                "To Email Address - Find associated emails",
                "To Phone Number - Find numbers",
                "To Social Media Profile - Find accounts",
                "To Company - Find employment",
            ],
            "PhoneNumber": [
                "To Person - Find owner",
                "To Location - Carrier/region data",
            ],
            "IPAddress": [
                "To DNS Name - Reverse DNS",
                "To Netblock - Find IP range",
                "To Location - Geolocation",
                "To AS Number - Find ASN",
            ],
            "Company": [
                "To Domain - Find company domains",
                "To Email Address - Find company emails",
                "To Person - Find employees",
                "To Phone Number - Find company numbers",
            ],
        }

        suggestions = transform_suggestions.get(entity_type, ["Run all transforms"])
        suggestion_text = "\n".join(f"  - {s}" for s in suggestions)

        return f"""TOOL: Maltego CE (Manual Guidance Mode)
ENTITY: {entity_type} = {entity_value}
{'=' * 60}

Maltego CE CLI automation is limited. Open Maltego GUI and follow these steps:

1. Create new graph (File > New)
2. Drag '{entity_type}' entity onto canvas
3. Set value to: {entity_value}
4. Right-click > Run Transforms:

RECOMMENDED TRANSFORMS:
{suggestion_text}

5. After transforms complete, export results:
   - File > Export > CSV or
   - File > Export > GraphML
6. Paste the exported data back here for analysis.

ALTERNATIVE: Use other tools in this toolkit for automated results:
  - theHarvester for domain/email harvesting
  - Shodan for IP intelligence
  - Sherlock for username/social media
  - SpiderFoot for automated multi-source scanning"""
