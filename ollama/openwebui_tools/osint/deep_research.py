"""
title: Deep Research Analytical Engine
author: openclaw-intel
version: 0.1.0
description: Structures and executes deep analytical research on collected OSINT data. Correlates findings, identifies patterns, assesses confidence, and produces intelligence reports.
"""

import json
import asyncio
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class Tools:
    class Valves(BaseModel):
        report_classification: str = Field(
            default="OPEN SOURCE",
            description="Classification label for generated reports.",
        )
        analyst_name: str = Field(
            default="OPENCLAW-INTEL",
            description="Analyst identifier for report headers.",
        )

    def __init__(self):
        self.valves = self.Valves()

    async def deep_research_analyze(
        self,
        raw_data: str,
        target_identifier: str,
        target_type: str,
        investigation_objective: Optional[str] = None,
        __event_emitter__=None,
    ) -> str:
        """
        Perform deep analysis on collected OSINT data. Feed this tool the raw output from other tools
        (theHarvester, Sherlock, Shodan, SpiderFoot, etc.) and it will correlate findings,
        identify patterns, assess confidence levels, and structure the intelligence.

        Use this as the FINAL PHASE after data collection to produce the intelligence report.

        :param raw_data: Combined raw output from OSINT tools. Paste all tool results here.
        :param target_identifier: The primary target (name, domain, IP, phone, etc.).
        :param target_type: Target classification (PERSON, ORGANIZATION, DOMAIN, IP, PHONE, TOPIC, EVENT, LOCATION).
        :param investigation_objective: What the operator wants to find out. Guides the analysis focus.
        :return: Structured analysis framework for the model to complete with its reasoning.
        """
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Analyzing collected intelligence on {target_identifier}...",
                        "done": False,
                    },
                }
            )

        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        data_lines = raw_data.strip().split("\n")
        data_size = len(data_lines)

        # Detect which tools contributed data
        tools_detected = []
        tool_markers = {
            "TOOL: theHarvester": "theHarvester",
            "TOOL: Sherlock": "Sherlock",
            "TOOL: Shodan": "Shodan",
            "TOOL: SpiderFoot": "SpiderFoot",
            "TOOL: PhoneInfoga": "PhoneInfoga",
            "TOOL: ExifTool": "ExifTool",
            "TOOL: Maltego": "Maltego CE",
            "TOOL: Recon-ng": "Recon-ng",
        }
        for marker, tool_name in tool_markers.items():
            if marker in raw_data:
                tools_detected.append(tool_name)

        tools_list = ", ".join(tools_detected) if tools_detected else "Unknown/Manual Input"

        report_template = f"""
{'=' * 70}
INTELLIGENCE ANALYSIS FRAMEWORK
{'=' * 70}
ANALYST: {self.valves.analyst_name}
TIMESTAMP: {timestamp}
CLASSIFICATION: {self.valves.report_classification}
TARGET: {target_identifier}
TYPE: {target_type}
OBJECTIVE: {investigation_objective or 'General intelligence gathering'}
DATA SOURCES: {tools_list}
RAW DATA VOLUME: {data_size} lines from {len(tools_detected)} tool(s)
{'=' * 70}

INSTRUCTIONS FOR MODEL:
You have received raw OSINT data below. Perform the following analysis:

1. EXECUTIVE SUMMARY
   - 2-3 sentences on the most significant findings.
   - What is the single most important thing the operator should know?

2. KEY FINDINGS
   - List each distinct finding.
   - Tag each: CONFIRMED (multi-source) / PROBABLE (single strong source) / POSSIBLE (weak signal) / UNVERIFIED (needs validation).
   - Cite which tool produced each finding.

3. ENTITY MAP
   - Show relationships between discovered entities.
   - Format: [Entity A] --[relationship]--> [Entity B]
   - Include: emails, domains, IPs, usernames, phone numbers, organizations, people, locations.

4. PATTERN ANALYSIS
   - What patterns emerge from the data?
   - Naming conventions, infrastructure patterns, temporal patterns, geographic clustering.
   - What does the target's digital footprint reveal about behaviour or operations?

5. INTELLIGENCE GAPS
   - What could NOT be determined from available data?
   - What additional tools or data sources would fill these gaps?
   - Recommended follow-up commands (specific tool + syntax).

6. THREAT/RISK ASSESSMENT (if applicable)
   - Security posture observations.
   - Exposed attack surface.
   - Data exposure risks.

7. RECOMMENDED NEXT STEPS
   - Prioritized list of follow-up actions.
   - Specific tool commands to execute next.
   - Additional investigation paths.

8. CONFIDENCE ASSESSMENT
   - Overall reliability: HIGH / MODERATE / LOW
   - Source diversity score: how many independent sources corroborate findings
   - Data freshness: estimated age of the intelligence

{'=' * 70}
RAW COLLECTED DATA:
{'=' * 70}

{raw_data}

{'=' * 70}
END RAW DATA — BEGIN ANALYSIS
{'=' * 70}
"""

        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Analysis framework ready — {len(tools_detected)} source(s), {data_size} lines of data.",
                        "done": True,
                    },
                }
            )

        return report_template

    async def deep_research_plan(
        self,
        target_identifier: str,
        target_type: str,
        known_information: Optional[str] = None,
        investigation_objective: Optional[str] = None,
        __event_emitter__=None,
    ) -> str:
        """
        Generate an investigation plan BEFORE running any tools. Use this at the START of an investigation
        to determine which tools to run, in what order, and what to look for.

        :param target_identifier: The primary target (name, domain, IP, phone, etc.).
        :param target_type: Target classification (PERSON, ORGANIZATION, DOMAIN, IP, PHONE, TOPIC, EVENT, LOCATION).
        :param known_information: Any information already known about the target. Helps focus the plan.
        :param investigation_objective: What the operator wants to find out.
        :return: Structured investigation plan with tool recommendations and command sequences.
        """
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Generating investigation plan for {target_type}: {target_identifier}...",
                        "done": False,
                    },
                }
            )

        tool_matrix = {
            "PERSON": {
                "primary": ["Sherlock (username enumeration)", "SpiderFoot (automated multi-source scan)"],
                "secondary": ["theHarvester (if email/domain known)", "PhoneInfoga (if phone known)", "ExifTool (if images available)"],
                "link_analysis": ["Maltego CE (relationship mapping)"],
            },
            "ORGANIZATION": {
                "primary": ["theHarvester (email/subdomain harvesting)", "SpiderFoot (full org scan)", "Shodan (infrastructure)"],
                "secondary": ["Recon-ng (modular deep dive)", "Sherlock (key personnel usernames)"],
                "link_analysis": ["Maltego CE (org relationship mapping)"],
            },
            "DOMAIN": {
                "primary": ["theHarvester (email/host discovery)", "Shodan (domain + IP intel)", "Recon-ng (DNS/WHOIS)"],
                "secondary": ["SpiderFoot (full domain scan)", "Sherlock (admin usernames if found)"],
                "link_analysis": ["Maltego CE (domain to infrastructure mapping)"],
            },
            "IP": {
                "primary": ["Shodan (port/service/vuln scan)", "Recon-ng (reverse DNS, WHOIS)"],
                "secondary": ["theHarvester (if domain resolves)", "SpiderFoot (IP scan)"],
                "link_analysis": ["Maltego CE (IP to org/domain mapping)"],
            },
            "PHONE": {
                "primary": ["PhoneInfoga (carrier/location/type)"],
                "secondary": ["SpiderFoot (phone number scan)", "Sherlock (if username found)"],
                "link_analysis": ["Maltego CE (phone to person mapping)"],
            },
            "TOPIC": {
                "primary": ["SpiderFoot (broad topic scan)"],
                "secondary": ["theHarvester (related domains)", "Shodan (related infrastructure)"],
                "link_analysis": ["Deep Research (analytical synthesis)"],
            },
            "EVENT": {
                "primary": ["SpiderFoot (event-related entities)"],
                "secondary": ["ExifTool (event photos/documents)", "Sherlock (participant usernames)"],
                "link_analysis": ["Deep Research (timeline reconstruction)"],
            },
            "LOCATION": {
                "primary": ["Shodan (geo-filtered infrastructure)", "SpiderFoot (location-based scan)"],
                "secondary": ["ExifTool (geotagged media)", "theHarvester (local organizations)"],
                "link_analysis": ["Maltego CE (location entity mapping)"],
            },
        }

        tools = tool_matrix.get(target_type, tool_matrix["TOPIC"])

        primary_list = "\n".join(f"    [{i+1}] {t}" for i, t in enumerate(tools["primary"]))
        secondary_list = "\n".join(f"    [{i+1}] {t}" for i, t in enumerate(tools["secondary"]))
        link_list = "\n".join(f"    [{i+1}] {t}" for i, t in enumerate(tools["link_analysis"]))

        plan = f"""
{'=' * 70}
INVESTIGATION PLAN
{'=' * 70}
TARGET: {target_identifier}
TYPE: {target_type}
OBJECTIVE: {investigation_objective or 'General intelligence gathering'}
KNOWN INFO: {known_information or 'None provided'}
{'=' * 70}

PHASE 1 — PRIMARY RECONNAISSANCE
{primary_list}

PHASE 2 — SECONDARY DEEP DIVE
{secondary_list}

PHASE 3 — LINK ANALYSIS & CORRELATION
{link_list}

PHASE 4 — DEEP RESEARCH (this model)
    [1] Correlate all findings across tools
    [2] Identify patterns and relationships
    [3] Assess confidence levels
    [4] Produce final intelligence report

{'=' * 70}
INSTRUCTIONS FOR MODEL:
Using the tool matrix above, generate SPECIFIC COMMANDS for each phase.
Include exact syntax the operator can copy-paste.
Order matters — explain WHY each tool runs in this sequence.
Identify what output from Phase 1 feeds into Phase 2 commands.
{'=' * 70}
"""

        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": "Investigation plan generated.",
                        "done": True,
                    },
                }
            )

        return plan
