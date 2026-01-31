# Project-specific instructions

## Vault

Path configured via env var `OBSIDIAN_VAULT_PATH`.
See `.env.example` for setup.

## Tech Stack

- Python 3.12+, Poetry
- Pydantic v2 (models)
- PyYAML (frontmatter parsing)
- MCP (Model Context Protocol)
- pytest, ruff, mypy

## Module Naming

```text
Папка:  src/obsidian_mcp/
Файл:   <сущность>.py
Класс:  <Сущность>
```

## Package

- Entry point: `obs-mcp` → `obsidian_mcp.mcp_server:main`
- Package: `src/obsidian_mcp/`

## Git

- Работаем в main
- Pre-commit hook: sdd_validator.py
