# Tool Transport Decision

## Chosen: MCPO Bridge (stdio → OpenAPI)

### Why MCPO

1. **Already deployed**: MCPO container running at port 8800 in this environment
2. **Proven pattern**: The existing `mcp-builder` model and Paperless MCP server use this exact path
3. **Open WebUI compatibility**: Open WebUI v0.8.10 supports OpenAPI tool endpoints natively — MCPO converts any stdio MCP server into one
4. **Reliability**: stdio transport is the most reliable MCP transport; MCPO adds HTTP without changing the underlying protocol

### When to Switch to Native MCP

Open WebUI v0.8.10+ supports native MCP for **Streamable HTTP** servers. Use native MCP when:
- The MCP server already exposes Streamable HTTP (not stdio, not SSE)
- You want to eliminate the MCPO middleware layer
- The server is stable and doesn't need the OpenAPI documentation layer

### When NOT to Switch

Keep MCPO when:
- The MCP server uses stdio transport (most Python MCP servers do)
- The MCP server uses SSE transport
- You need the OpenAPI/Swagger documentation for debugging
- You want consistent tooling across multiple servers

### Architecture

```
User → Open WebUI (3010) → Ollama (11434) → model generates tool_call
                         ↓
              MCPO (8800) → stdio MCP server → tool result
                         ↓
              Open WebUI feeds result back to model
```

### Config Location

- MCPO config: `tool-transport/mcpo-config.json`
- To add a new tool: add an entry to the `mcpServers` object
- To deploy: mount the config into the MCPO container or restart with updated config
