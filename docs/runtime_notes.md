# Runtime Notes

## Environment Snapshot (captured during initial build)

| Component | Version | Location |
|-----------|---------|----------|
| Ollama | 0.17.7 | localhost:11434 (native Windows) |
| Open WebUI | 0.8.10 | localhost:3010 (Docker) |
| MCPO | latest | localhost:8800 (Docker) |
| Python | 3.14.0 | C:\Python314 |
| uv | 0.10.0 | Available for dependency management |
| Docker | 29.2.1 | Running with 40+ containers |
| OS | Windows 11 Pro | bash shell available via Git Bash |

## Ollama Models Available

Models already downloaded (relevant for model-forge base selection):

| Model | Size | Good For |
|-------|------|----------|
| qwen3:8b | 5.2 GB | General tool use, default choice |
| qwen3.5:9b | 6.6 GB | Newer, larger context variant |
| qwen3.5:9b-32k | 6.6 GB | Extended context window |
| llama3.2:3b | 2.0 GB | Cheapest/fastest, limited tool use |
| gemma3:12b | 8.1 GB | Higher quality, slower |
| gemma3:27b | 17 GB | Highest quality available locally |
| qwen2.5:14b | 9.0 GB | Good reasoning, base for mcp-builder |
| qwen2.5:7b-instruct | 4.7 GB | Smaller qwen option |

## Existing Custom Models

- `mcp-builder:latest` — qwen2.5:14b tuned for MCP server development
- `qwen3:8b-royal-sop-*` — Five variants with different system prompts

## Port Map (relevant services)

| Port | Service |
|------|---------|
| 3010 | Open WebUI |
| 8800 | MCPO bridge |
| 11434 | Ollama API |
| 8080 | Dozzle (logs) |
| 9000 | Portainer |

## Known Constraints

1. **Python 3.14** — Some packages may not have wheels yet. Use `uv` for dependency resolution.
2. **Windows paths** — Scripts use forward slashes in bash, backslashes in PowerShell.
3. **MCPO Docker** — Config changes require container restart or remount.
4. **Ollama VRAM** — Only one model loaded at a time on most GPUs. Use `ollama ps` to check.
5. **Open WebUI auth** — Requires login; API calls need auth token.

## MCPO Docker Container

The MCPO container (`paperless-mcpo`) is configured in the broader Docker Compose stack. To update its config:

1. Edit `tool-transport/mcpo-config.json`
2. Copy into the container or mount as volume
3. Restart the container

Current MCPO container maps port 8800:8000.
