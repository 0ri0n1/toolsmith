# How to Use Model Forge

## Quick Start

### 1. Build the default model

```powershell
.\scripts\build_model.ps1
```

This creates `toolsmith` — a general-purpose tool-use model based on qwen3:8b.

### 2. Test it

```powershell
.\scripts\test_stack.ps1
```

### 3. Use it in Open WebUI

Open http://localhost:3010, log in, and select `toolsmith` from the model dropdown.

---

## Using the Model Forge Subagent

The model-forge subagent is a Claude Code agent that builds custom models through conversation. Invoke it in Claude Code:

```
@model-forge Build me a model for bookkeeping tasks
```

Or describe what you want naturally:

```
@model-forge I need a small model that can reliably call two tools:
one for looking up invoices and one for categorizing expenses.
It should be fast and cheap.
```

### What the subagent does

1. **Inspects** your current environment (Ollama models, configs, test results)
2. **Asks** 1-2 clarifying questions if needed
3. **Generates tools** — if the tools don't exist yet, creates MCP servers, registers them in MCPO, and validates them
4. **Decides** base model, parameters, system prompt, tool transport
5. **Generates** Modelfile, configs, tests
6. **Builds** the model via `ollama create`
7. **Tests** with smoke tests and evals
8. **Reports** what passed and failed

### Example conversations

**Model with auto-generated tools:**
> "Build me a model that can query my QuickBooks invoices"

The subagent will:
- Ask what operations (lookup, search, list unpaid, etc.)
- Generate `tool-transport/quickbooks-server.py` (a real MCP server)
- Register it in `tool-transport/mcpo-config.json`
- Validate the server with `python scripts/test_tool_server.py`
- Build a custom Ollama model tuned for that tool
- Test the full pipeline

**Simple model request:**
> "Make a model for code review with git tools"

The subagent will:
- Pick qwen3:8b (good balance)
- Craft a system prompt for code review
- Set up git-related tool schemas
- Build and test

**Optimization request:**
> "The model keeps calling the wrong tool. Fix it."

The subagent will:
- Read recent test results
- Identify the failure pattern
- Adjust system prompt or temperature
- Rebuild and retest

**Model swap:**
> "This model is too slow. Switch to llama3.2:3b"

The subagent will:
- Update the Modelfile FROM line
- Adjust parameters for the smaller model
- Rebuild and retest
- Report quality differences

---

## Manual Operations

### Build a custom model

1. Edit `ollama/Modelfile` (or create a new `ollama/<name>.Modelfile`)
2. Run:
```powershell
.\scripts\build_model.ps1 -ModelName my-model -ModelFile ollama/my-model.Modelfile
```

### Add a tool via MCPO

**Automatic (recommended):** Tell the model-forge subagent what tool you need. It will generate the MCP server, register it, and validate it.

**Manual:**

1. Create an MCP server in `tool-transport/<name>-server.py` following the nmap-server.py pattern (see `tool-transport/nmap-server.py` for the gold standard)

2. Add to `tool-transport/mcpo-config.json`:
```json
{
  "mcpServers": {
    "my-tool": {
      "command": "python",
      "args": ["/app/tool-transport/my-tool-server.py"],
      "env": {}
    }
  }
}
```

3. Validate the server:
```bash
python scripts/test_tool_server.py tool-transport/my-tool-server.py
```

4. Restart MCPO container

5. Configure in Open WebUI: Admin → Settings → Tools → Add OpenAPI tool → `http://mcpo:8000/my-tool`

### Validate any MCP server

The tool server validator tests that an MCP server starts, responds to the protocol handshake, and lists its tools correctly:

```bash
# Basic validation
python scripts/test_tool_server.py tool-transport/my-server.py

# Validate and invoke a specific tool
python scripts/test_tool_server.py tool-transport/nmap-server.py --invoke nmap_scan '{"target": "127.0.0.1"}'
```

### Run specific tests

```powershell
# Smoke tests only
python tests/tool_smoke_test.py --model my-model

# Evals only
python tests/run_evals.py --model my-model

# Full verification
.\scripts\verify_stack.ps1 -ModelName my-model
```

### Swap base models

Edit `ollama/Modelfile`, change the `FROM` line:
```
FROM llama3.2:3b     # Fast and cheap
FROM qwen3:8b        # Balanced (default)
FROM qwen3.5:9b-32k  # Extended context
FROM gemma3:12b      # Higher quality
FROM qwen2.5:14b     # Best reasoning
```

Then rebuild: `.\scripts\build_model.ps1`

---

## Creating Your Next Custom Model

The whole point of Model Forge is repeatability. To create another model:

1. **Tell the subagent** what you need: `@model-forge Build me a model for X`
2. **Or copy the default**: `cp ollama/Modelfile ollama/my-new.Modelfile`, edit, build
3. **Or ask for a variant**: `@model-forge Make a variant of toolsmith optimized for speed`

Each model gets its own Modelfile. Tests and evals are shared but can be extended per model.

---

## Optimization Ladder

When a model doesn't perform well enough, improve in this order:

1. **System prompt** — Most impact, easiest to change
2. **Temperature/parameters** — Lower temp = more deterministic tool calls
3. **Tool schema quality** — Better descriptions = better selection
4. **Context window** — Increase if tool responses are getting truncated
5. **Model swap** — Bigger model if quality is insufficient
6. **Adapter/fine-tune** — Only with eval evidence showing the above aren't enough
