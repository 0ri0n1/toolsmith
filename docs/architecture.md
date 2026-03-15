# Model Forge Architecture

## System Overview

Model Forge is a local-first system for building custom Ollama models with tool integration. It is operated through a Claude Code subagent that interviews the user, makes architecture decisions, generates configs, and validates the result.

```
┌──────────────────────────────────────────────────────────────────┐
│                        Claude Code                               │
│                  (model-forge subagent)                           │
│                                                                   │
│  Interview → Tool Gen → Architecture → Generate → Build → Test   │
│                  ↓                                                │
│          Generate MCP server                                      │
│          Register in MCPO                                         │
│          Validate via test_tool_server.py                         │
└──────────────┬───────────────────────────┬───────────────────────┘
               │ generates                 │ tests via
               ▼                           ▼
┌──────────────────┐           ┌──────────────────────┐
│  ollama/Modelfile │           │  tests/smoke_test.py  │
│  (model config)   │           │  evals/cases.json     │
└────────┬─────────┘           └──────────┬───────────┘
         │ ollama create                   │ HTTP API
         ▼                                 ▼
┌──────────────────┐           ┌──────────────────────┐
│     Ollama        │◄──────────│   Ollama HTTP API     │
│  (model runtime)  │           │  localhost:11434      │
└────────┬─────────┘           └──────────────────────┘
         │ serves model
         ▼
┌──────────────────┐     tool calls     ┌──────────────┐
│   Open WebUI      │────────────────────│  MCPO Bridge  │
│   localhost:3010   │                    │  localhost:8800│
└──────────────────┘     tool results   └──────┬───────┘
                                                │ stdio
                                                ▼
                                        ┌──────────────┐
                                        │  MCP Servers  │
                                        │  (per tool)   │
                                        └──────────────┘
```

## Layers

### 1. Model Runtime (Ollama)
- Runs the actual LLM inference
- Loads models defined by Modelfiles
- Exposes HTTP API for generation and chat
- Handles tool-call generation via template

### 2. Tool Transport (MCPO Bridge)
- Wraps stdio-based MCP servers as OpenAPI endpoints
- Open WebUI connects to these endpoints as "tool" providers
- Manages per-server environment variables and process lifecycle
- Already deployed at port 8800

### 3. Orchestration (Open WebUI)
- Provides the chat interface
- Connects to Ollama for model inference
- Connects to MCPO for tool execution
- Handles the tool_call → tool_response → final_answer loop

### 4. Verification (Test Suite)
- Smoke tests validate infrastructure and basic behavior
- Eval cases validate specific tool-use patterns
- Stack verification checks file completeness and coherence
- Results are written to JSON for tracking

### 5. Tool Generation (Model Forge Phase 2.5)
- When tools don't already exist, generates FastMCP stdio servers
- Follows the nmap-server.py pattern: sanitization, structured JSON, stderr logging
- Registers in MCPO config automatically
- Validates via `scripts/test_tool_server.py` before proceeding

### 6. Packaging (Model Forge Subagent)
- Generates all configuration files (including tool servers when needed)
- Builds the Ollama model
- Runs verification
- Reports results

## Decision Log

| Decision | Choice | Reason |
|----------|--------|--------|
| Base model | qwen3:8b | Proven tool-use in this env, good size/quality, already downloaded |
| Tool transport | MCPO bridge | Already deployed, proven with existing MCP servers, handles stdio |
| Template | Qwen ChatML with tool_call XML | Matches qwen3 training format, proven in mcp-builder |
| Temperature | 0.15 | Low for reliable tool selection, adjustable per use case |
| Context | 16384 | Adequate for most tool-use; increase for complex multi-tool chains |
| Test framework | Standalone Python (no deps) | Zero install, runs anywhere Python exists |
| Tool generation | Auto via Phase 2.5 | Subagent generates MCP servers from user description |
| Tool validation | scripts/test_tool_server.py | Validates MCP protocol handshake + tool listing |
| Failure retry | Classify + auto-fix, max 3 | Automated loop: classify failures, fix system prompt/params, rebuild, retest |
| Composite tools | CompositeToolBuilder framework | Small models can't orchestrate multi-tool chains; one composite tool is more reliable |

## File Layout

```
E:\toolsmith\
├── .claude/
│   ├── agents/
│   │   └── model-forge.md      # The builder subagent
│   └── settings.json           # Project settings + hooks
├── .mcp.json                   # MCP config (minimal)
├── ollama/
│   └── Modelfile               # Default model definition
├── tool-transport/
│   ├── mcpo-config.json        # MCPO bridge configuration
│   ├── composite.py            # Composite tool framework (multi-step chains)
│   └── TRANSPORT_DECISION.md   # Why MCPO was chosen
├── scripts/
│   ├── build_model.ps1/.sh     # Build Ollama model
│   ├── run_stack.ps1/.sh       # Start all services
│   ├── test_stack.ps1/.sh      # Run all tests
│   ├── verify_stack.ps1        # Verify completeness
│   └── test_tool_server.py     # MCP server protocol validator
├── tests/
│   ├── tool_smoke_test.py      # Smoke tests (+ --rerun-failed)
│   ├── run_evals.py            # Eval runner (+ --rerun-failed)
│   ├── classify_failures.py    # Failure classifier for retry loop
│   ├── composite_smoke_test.py # Composite framework unit tests
│   └── smoke_results.json      # Latest results
├── evals/
│   ├── tool_use_cases.json     # Eval cases (incl. composite tool cases)
│   └── eval_results.json       # Latest eval results
└── docs/
    ├── architecture.md          # This file
    ├── runtime_notes.md         # Environment details
    └── how_to_use_model_forge.md # User guide
```
