# Prompt for Antigravity Opus 4.6 — Build OSINT Tools in Open WebUI

Copy everything below the line into your IDE session with Antigravity Opus 4.6 Thinking.

---

## CONTEXT

I am building an OSINT intelligence model called **OPENCLAW-INTEL** in Open WebUI. The model is already created (base model: qwen3:8b, model ID: intelligence-gathering-expert). The system prompt and model configuration are done.

What I need now is **9 custom Tools** created in Open WebUI so I can check them on in the model's Tools section. These tools wrap CLI OSINT tools running in WSL (Kali Linux) and execute them via subprocess. Each tool must be created in Open WebUI by navigating to **Workspace > Tools > "+" (Create)** — paste the Python code, give it a name, and save.

## WHAT YOU NEED TO DO

For each of the 9 tools below, go to Open WebUI (http://localhost:3000 or whatever the local instance is), navigate to **Workspace > Tools**, click the **"+"** button to create a new tool, paste the Python source code, and save it. After all 9 are created, they should appear as checkboxes in the model editor under "Tools" so I can enable them on the OPENCLAW-INTEL model.

## THE 9 TOOLS TO CREATE

Each tool is a standalone Python file following Open WebUI's tool format: a metadata docstring at the top, a `Tools` class with a `Valves` inner class (Pydantic BaseModel), and async public methods with full type hints and Sphinx-style `:param` docstrings. All tools execute commands in WSL via `asyncio.create_subprocess_exec("wsl", "-d", valves.wsl_distro, ...)`.

### Tool 1: theHarvester
- **Name**: theHarvester OSINT
- **Description**: Email, subdomain, IP, and name harvesting from public search engines and databases
- **Method**: `run_theharvester(domain, sources, limit, start, dns_resolve)` → runs `theHarvester -d <domain> -b <sources> -l <limit>`
- **Valves**: `timeout` (120s), `wsl_distro` ("kali-linux"), `default_sources` ("google,bing,dnsdumpster,crtsh,urlscan"), `max_output_lines` (500)

### Tool 2: Recon-ng
- **Name**: Recon-ng Framework
- **Description**: Modular web reconnaissance with API-backed modules for WHOIS, DNS, host discovery, contact harvesting
- **Methods**:
  - `recon_ng_run_module(target, module_path, options)` → runs a specific Recon-ng module against a target
  - `recon_ng_search_modules(keyword)` → searches available modules by keyword
- **Valves**: `timeout` (180s), `wsl_distro` ("kali-linux"), `workspace` ("osint_default"), `max_output_lines` (500)

### Tool 3: SpiderFoot
- **Name**: SpiderFoot Scanner
- **Description**: Automated OSINT scanner with 200+ modules for broad target reconnaissance
- **Method**: `spiderfoot_scan(target, scan_types, modules, max_threads)` → runs `spiderfoot -s <target> -t <types>`
- **Valves**: `timeout` (300s), `wsl_distro` ("kali-linux"), `max_output_lines` (800), `spiderfoot_path` ("spiderfoot")

### Tool 4: Sherlock
- **Name**: Sherlock Username Finder
- **Description**: Username enumeration across 400+ social media platforms
- **Method**: `sherlock_lookup(username, sites, timeout_per_site, found_only)` → runs `sherlock <username>`
- **Valves**: `timeout` (120s), `wsl_distro` ("kali-linux"), `max_output_lines` (500)

### Tool 5: PhoneInfoga
- **Name**: PhoneInfoga
- **Description**: Phone number intelligence — carrier info, location data, line type, linked accounts
- **Method**: `phoneinfoga_scan(phone_number, scanners)` → runs `phoneinfoga scan -n <number>`
- **Valves**: `timeout` (90s), `wsl_distro` ("kali-linux"), `max_output_lines` (300)

### Tool 6: Shodan CLI
- **Name**: Shodan Intelligence
- **Description**: Internet-connected device intelligence — open ports, services, banners, CVEs, infrastructure mapping
- **Methods**:
  - `shodan_host(ip_address)` → runs `shodan host <ip>`
  - `shodan_search(query, limit)` → runs `shodan search <query>`
  - `shodan_domain(domain)` → runs `shodan domain <domain>`
- **Valves**: `timeout` (60s), `wsl_distro` ("kali-linux"), `max_output_lines` (500), `api_key_env` ("SHODAN_API_KEY")

### Tool 7: ExifTool
- **Name**: ExifTool Metadata Extractor
- **Description**: Image and document metadata extraction — GPS, camera info, software, timestamps, author data
- **Methods**:
  - `exiftool_extract(file_path, gps_only)` → runs `exiftool <file>`
  - `exiftool_batch(directory, file_type)` → runs `exiftool -csv -r -ext <type> <dir>`
- **Valves**: `timeout` (30s), `wsl_distro` ("kali-linux"), `max_output_lines` (300)

### Tool 8: Maltego CE
- **Name**: Maltego Link Analysis
- **Description**: Visual link analysis and relationship mapping for connecting entities into relationship graphs
- **Method**: `maltego_transform(entity_value, entity_type, transform_name)` → attempts CLI transform, falls back to manual GUI guidance
- **Valves**: `timeout` (120s), `wsl_distro` ("kali-linux"), `max_output_lines` (500), `maltego_path` ("maltego")

### Tool 9: Deep Research Analytical Engine
- **Name**: Deep Research
- **Description**: Correlates raw OSINT data from other tools into structured intelligence reports
- **Methods**:
  - `deep_research_analyze(raw_data, target_identifier, target_type, investigation_objective)` → structures collected data into an intelligence analysis framework
  - `deep_research_plan(target_identifier, target_type, known_information, investigation_objective)` → generates investigation plans with tool recommendations and sequencing
- **Valves**: `report_classification` ("OPEN SOURCE"), `analyst_name` ("OPENCLAW-INTEL")

## TECHNICAL REQUIREMENTS FOR EACH TOOL

Every tool MUST follow this exact pattern:

```python
"""
title: Tool Display Name
author: openclaw-intel
version: 0.1.0
description: What this tool does in one sentence
"""

import asyncio
from pydantic import BaseModel, Field
from typing import Optional

class Tools:
    class Valves(BaseModel):
        # Admin-configurable settings
        timeout: int = Field(default=120, description="Max execution time in seconds")
        wsl_distro: str = Field(default="kali-linux", description="WSL distro name")
        max_output_lines: int = Field(default=500, description="Max output lines")

    def __init__(self):
        self.valves = self.Valves()

    async def tool_method(
        self,
        param1: str,
        param2: Optional[str] = None,
        __event_emitter__=None,
    ) -> str:
        """
        Description the LLM reads to decide when to call this tool.
        :param param1: What this parameter is.
        :param param2: What this optional parameter is.
        :return: What this tool returns.
        """
        if __event_emitter__:
            await __event_emitter__({"type": "status", "data": {"description": "Running...", "done": False}})

        # Build command
        cmd = ["wsl", "-d", self.valves.wsl_distro, "--", "tool_binary", param1]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.valves.timeout)
            output = stdout.decode(errors="replace")
            # Truncate if needed
            lines = output.strip().split("\n")
            if len(lines) > self.valves.max_output_lines:
                lines = lines[:self.valves.max_output_lines]
                lines.append(f"\n[TRUNCATED — showing {self.valves.max_output_lines} of {len(lines)} lines]")
            result = "\n".join(lines)
        except asyncio.TimeoutError:
            result = f"[ERROR] Command timed out after {self.valves.timeout}s"
        except Exception as e:
            result = f"[ERROR] {str(e)}"

        if __event_emitter__:
            await __event_emitter__({"type": "status", "data": {"description": "Done", "done": True}})

        return result
```

## KEY RULES

1. **Every public method needs type hints on ALL parameters** — Open WebUI generates JSON schema from them
2. **Every public method needs a Sphinx-style docstring** with `:param name: description` for each param — the LLM reads these to understand tool usage. Missing docstrings cause "list index out of range" errors
3. **Methods must be async** — needed for `__event_emitter__` and `asyncio.create_subprocess_exec`
4. **Dunder params (`__event_emitter__`, `__user__`, etc.) are auto-injected** — they get stripped from the generated spec, don't include them in docstrings
5. **The class must be named `Tools`** (capital T) — this is hardcoded in Open WebUI
6. **All CLI execution goes through WSL**: `["wsl", "-d", self.valves.wsl_distro, "--", "command", "args"]`
7. **Use `asyncio.create_subprocess_exec`** not `subprocess.run` — async is required
8. The Deep Research tool (Tool 9) does NOT execute CLI commands — it's a pure analytical framework that structures data for the LLM to reason over

## AFTER CREATING ALL TOOLS

Once all 9 tools are saved in Open WebUI:
1. Go to **Workspace > Models > Intelligence Gathering Expert**
2. In the **Tools** section, check all 9 new tools
3. Click **Save & Update**

The tools already visible in the screenshot (like "Deep Research", "SearXNG", "Web Search And Crawl", etc.) are existing tools — the 9 above are NEW tools that need to be created.

## SOURCE CODE

The complete Python source code for all 9 tools is available in the repository at:
```
ollama_models/openwebui_tools/osint/
├── theharvester.py
├── recon_ng.py
├── spiderfoot.py
├── sherlock.py
├── phoneinfoga.py
├── shodan_cli.py
├── exiftool.py
├── maltego.py
└── deep_research.py
```

You can read these files directly and paste their contents into Open WebUI when creating each tool. If you cannot access the filesystem, build each tool from the specifications above — they contain all the information needed.
