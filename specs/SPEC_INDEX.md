# Spec Index

## Core

vault (committed) — конфигурация, сканирование, парсинг, индекс заметок
operations (committed) — CRUD, update, rename, search, links, frontmatter, batch
mcp_server (committed) — MCP сервер для Claude Desktop, оборачивает Operations в tools
validation (committed) — валидация markdown: tables, code blocks, English-only names/headings

## Dependencies

vault
validation
operations -> vault, validation
mcp_server -> operations, vault
