# Obsidian MCP

MCP server for Obsidian vault management. Designed for AI agents (Claude Desktop, Claude Code).

## Features

- Full CRUD operations on notes
- Wikilink management (auto-update on rename/delete)
- Frontmatter manipulation
- Tag-based and content search
- Backlinks discovery
- Section-level operations

## Installation

```bash
poetry install
```

## Configuration

Set the vault path via environment variable:

```bash
export OBSIDIAN_VAULT_PATH="/path/to/your/obsidian/vault"

# WSL example (Windows vault accessed from WSL)
export OBSIDIAN_VAULT_PATH="/mnt/c/Users/username/Documents/Obsidian/my_vault"
```

## Claude Desktop Configuration

Add to `claude_desktop_config.json`:

**Linux/macOS:**

```json
{
  "mcpServers": {
    "obsidian": {
      "command": "bash",
      "args": ["-c", "cd /path/to/obsidian-mcp && poetry run obs-mcp"],
      "env": {
        "OBSIDIAN_VAULT_PATH": "/path/to/your/obsidian/vault"
      }
    }
  }
}
```

**Windows (via WSL):**

```json
{
  "mcpServers": {
    "obsidian": {
      "command": "wsl",
      "args": [
        "-e", "bash", "-c",
        "cd /path/to/obsidian-mcp && poetry run obs-mcp"
      ],
      "env": {
        "OBSIDIAN_VAULT_PATH": "/mnt/c/Users/username/Documents/Obsidian/my_vault"
      }
    }
  }
}
```

## Available Tools

| Tool | Description |
|------|-------------|
| `read_note(name)` | Read note content (frontmatter + body) |
| `create_note(name, content?, frontmatter?)` | Create note |
| `append_note(name, text)` | Append to note |
| `update_note(name, content)` | Replace body, preserve frontmatter |
| `delete_note(name, dry_run?)` | Delete (links updated to `[[name (deleted)]]`) |
| `rename_note(old_name, new_name, dry_run?)` | Rename + update wikilinks |
| `search_notes(query, mode?)` | Search (name, name_partial, content, tag) |
| `get_links(name, direction?)` | Get incoming/outgoing links |
| `get_note_metadata(name)` | Get frontmatter + links without body |
| `set_frontmatter(name, key, value)` | Set frontmatter key |
| `add_tag(name, tag)` | Add tag to note |
| `remove_tag(name, tag)` | Remove tag from note |
| `list_notes(limit?, offset?)` | List all notes (paginated) |
| `replace_text(name, old, new, replace_all?)` | Replace text in note |
| `insert_text(name, text, before?, after?)` | Insert text at position |
| `read_section(name, section)` | Read section by heading |
| `append_section(name, section, text)` | Append to section |
| `update_section(name, section, content)` | Replace section content |
| `delete_section(name, section)` | Delete section |
| `get_headings(name)` | Get all headings |
| `find_broken_links()` | Find broken wikilinks |
| `get_help()` | Get tool descriptions |

## Vault Structure

- Flat structure (all `.md` files in vault root)
- YAML frontmatter with `---` delimiters
- Wikilinks: `[[Note Name]]`
- Tags in frontmatter: `tags: [tag1, tag2]`
- `.trash/` for deleted notes
- `.obsidian/` ignored

## Development

```bash
# Run tests
poetry run pytest tests/spec/core/ -v

# Lint
poetry run ruff check src/
poetry run mypy src/
```

## License

MIT
