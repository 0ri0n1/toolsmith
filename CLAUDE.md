# Toolsmith — Project Rules

## Workspace Hygiene

### Directory Structure (enforced)
```
E:\toolsmith\
├── .claude/          # Claude Code config only — agents, settings
├── ollama/           # Modelfiles only — one per model, named <model-name>.Modelfile
│                     # Default model uses "Modelfile" (no prefix)
├── tool-transport/   # Transport configs and MCP server source files
├── scripts/          # Build, run, test, verify scripts
├── tests/            # Test source files (.py)
├── evals/            # Eval case definitions (.json) — NOT results
├── docs/             # Architecture, runtime notes, guides
```

### File Rules
1. **No orphan files in root.** Only CLAUDE.md, .mcp.json, .gitignore belong at root level.
2. **No generated output committed.** Test results, eval results, logs, and build artifacts stay in .gitignore.
3. **One Modelfile per model.** Name variants as `ollama/<name>.Modelfile`. The default is `ollama/Modelfile`.
4. **No temp files.** If a build step creates temp files, clean them up in the same script.
5. **No empty directories.** Every directory must contain at least one functional file.
6. **No duplicate functionality.** Before creating a new script or test, check if one already covers it.

### Naming Conventions
- Modelfiles: `ollama/<model-name>.Modelfile` (lowercase, hyphens)
- Scripts: `scripts/<verb>_<noun>.ps1` and `.sh` (snake_case)
- Tests: `tests/<scope>_smoke_test.py` or `tests/<scope>_test.py`
- Evals: `evals/<scope>_use_cases.json`
- Docs: `docs/<topic>.md` (lowercase, underscores)

### Commit Rules
- Commit working states only. Don't commit broken builds.
- Keep commits atomic: one logical change per commit.
- Exclude generated results (already in .gitignore).
- Stage specific files, not `git add .`.

### Cleanup Triggers
Before any commit, verify:
- [ ] No stale temp files in any directory
- [ ] No results files staged (they're gitignored)
- [ ] No duplicate Modelfiles doing the same thing
- [ ] No scripts that reference deleted files
- [ ] .gitignore covers all generated output patterns

### Working Outside This Folder
All work stays in `E:\toolsmith`. If an operation requires accessing files outside this folder, ask first. The one exception: copying Modelfiles to system temp for `ollama create` (Windows colon-in-path workaround) — the script handles cleanup automatically.
