"""MCP server for ClaudeDesktop. Wraps Operations into MCP tools."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from mcp.server.fastmcp import FastMCP

from obsidian_mcp.errors import VaultError
from obsidian_mcp.operations import (
    LinkDirection,
    Operations,
    SearchMode,
    SearchResult,
)
from obsidian_mcp.vault import Vault

_AUTOCONTEXT_TAG = "claude"
_MISSING_DESCRIPTION = (
    "⚠️ No description. Claude, please add a 'description' field "
    "to this note's frontmatter explaining when to read it."
)

_TAG_RULES: dict[str, dict[str, Any]] = {
    "Person": {
        "check": lambda name, fm: name.startswith("@"),
        "error": (
            "Tag 'Person' is for people notes only. "
            "Note name must start with '@' (e.g. '@John Doe')."
        ),
    },
    "claude": {
        "check": lambda name, fm: "description" in fm and fm["description"],
        "error": (
            "Tag 'claude' marks instructions for Claude AI. "
            "Requires 'description' field in frontmatter explaining when to read the note."
        ),
    },
}

_BASE_INSTRUCTIONS = """\
You have access to an Obsidian vault through MCP tools. \
The vault is a flat collection of markdown notes with YAML frontmatter and [[wikilinks]].

## Key rules

- Note names are WITHOUT .md extension: use read_note("My Note"), not read_note("My Note.md").
- Always read_note() before update_note() or append_note().
- update_note replaces body (frontmatter preserved). append_note adds text to the end.
- Use dry_run=true before delete/rename to preview changes.
- Wikilinks: [[Note Name]]. They are updated automatically on rename/delete.
- Frontmatter: top-level keys only. Tags are a list of strings: ["vc", "vc/project"].
- search_notes modes: name (exact), name_partial (default, case-insensitive), content (body text), tag (hierarchical: "vc" matches "vc/project").
- get_links directions: out (outgoing), in (incoming/backlinks), both (default).
- create_note frontmatter param is a JSON string: '{"tags": ["project"], "status": "draft"}'.
- Start with list_notes() to see what's in the vault.\
"""


def _build_autocontext(vault: Vault) -> str:
    """Build auto-context section from notes tagged with 'claude'."""
    claude_notes = [n for n in vault.list_notes() if _AUTOCONTEXT_TAG in n.tags]
    if not claude_notes:
        return (
            "Your personal notes:\n"
            "No personal notes found. "
            "Create notes with tag 'claude' to use auto-context."
        )
    lines = ["Your personal notes:"]
    for note in claude_notes:
        description = note.frontmatter.get("description", _MISSING_DESCRIPTION)
        lines.append(f'- "{note.name}" — {description}')
    lines.append("")
    lines.append("Use read_note() to access full content when needed.")
    return "\n".join(lines)


def _collect_tags(vault: Vault) -> set[str]:
    """Collect valid tags from vault (non-empty strings only)."""
    return {
        tag
        for note in vault.list_notes()
        for tag in note.tags
        if isinstance(tag, str) and tag.strip()
    }


def _build_tag_policy(vault: Vault) -> str:
    """Build tag policy section from all unique tags in vault."""
    all_tags = sorted(_collect_tags(vault))
    if not all_tags:
        return "Allowed tags: No tags in vault yet."
    return "Allowed tags: " + ", ".join(all_tags)


def _build_context_block(vault: Vault) -> str:
    """Build context block for injection into first tool result."""
    return _build_autocontext(vault) + "\n\n" + _build_tag_policy(vault)


def _build_instructions() -> str:
    """Return base instructions only. No vault-specific content."""
    return _BASE_INSTRUCTIONS


def _validate_tags(tags: list[str], vault: Vault) -> None:
    """Validate tags against allowed list (all unique tags in vault)."""
    allowed = _collect_tags(vault)
    invalid = [t for t in tags if t not in allowed]
    if invalid:
        raise ValueError(
            f"Tags not in allowed list: {invalid}. "
            f"Allowed: {sorted(allowed)}. "
            f"Ask user before creating new tags."
        )


def _validate_tag_rules(
    tags: list[str],
    note_name: str,
    frontmatter: dict[str, Any],
) -> None:
    """Validate tag-specific rules. Called after _validate_tags."""
    for tag in tags:
        if tag in _TAG_RULES:
            rule = _TAG_RULES[tag]
            if not rule["check"](note_name, frontmatter):
                raise ValueError(rule["error"])


def _tag_matches(note_tags: list[str], query_tag: str) -> bool:
    """Check if any note tag matches query (hierarchical)."""
    return any(t == query_tag or t.startswith(query_tag + "/") for t in note_tags)


def _search_multi_tag(
    query: str,
    tag_logic: str,
    vault: Vault,
) -> list[SearchResult]:
    """Search notes by multiple tags with AND/OR logic."""
    if tag_logic not in ("and", "or"):
        raise ValueError(f"Invalid tag_logic: {tag_logic}. Valid: and, or")
    tags = [t.strip() for t in query.split(",") if t.strip()]
    results = []
    for note in vault.list_notes():
        if tag_logic == "or":
            match = any(_tag_matches(note.tags, t) for t in tags)
        else:  # and
            match = all(_tag_matches(note.tags, t) for t in tags)
        if match:
            results.append(SearchResult(name=note.name, path=str(note.path)))
    return results


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)


def _create_server(vault_path_str: str) -> FastMCP:
    """Create FastMCP server with instructions and tools."""
    vault = Vault(Path(vault_path_str))
    instructions = _build_instructions()
    context_state = {"injected": False}

    def inject_context(result: str) -> str:
        if context_state["injected"]:
            return result
        context_state["injected"] = True
        context_block = _build_context_block(vault)
        return (
            result
            + "\n\n<!-- CLAUDE CONTEXT (do not copy to notes):\n"
            + context_block
            + "\n-->"
        )

    server = FastMCP("obsidian-cli", instructions=instructions)
    ops = Operations(vault)
    _register_tools(server, ops, inject_context)
    return server


def _register_tools(
    server: FastMCP,
    ops: Operations,
    inject_context: Callable[[str], str],
) -> None:
    """Register all MCP tools on the server."""

    @server.tool()
    def read_note(name: str) -> str:
        """Read full note content (frontmatter + body)."""
        try:
            return inject_context(ops.read(name))
        except VaultError as e:
            raise ValueError(str(e)) from e

    @server.tool()
    def create_note(
        name: str,
        content: str = "",
        frontmatter: str = "",
    ) -> str:
        """Create new note. frontmatter is optional JSON string, e.g. '{"tags": ["vc"]}'. Tags are validated against allowed list."""
        try:
            fm: dict[str, Any] | None = None
            if frontmatter:
                try:
                    fm = json.loads(frontmatter)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid frontmatter JSON: {e}") from e
            if fm and "tags" in fm:
                _validate_tags(fm["tags"], ops.vault)
                _validate_tag_rules(fm["tags"], name, fm)
            path = ops.create(name, content=content, frontmatter=fm)
            return inject_context(_json({"name": name, "path": str(path)}))
        except VaultError as e:
            raise ValueError(str(e)) from e

    @server.tool()
    def append_note(name: str, text: str) -> str:
        """Append text to end of note. Adds \\n\\n before text."""
        try:
            ops.append(name, text)
            return inject_context(_json({"name": name, "status": "appended"}))
        except VaultError as e:
            raise ValueError(str(e)) from e

    @server.tool()
    def update_note(name: str, content: str) -> str:
        """Replace body of note, preserving frontmatter."""
        try:
            ops.update(name, content)
            return inject_context(_json({"name": name, "status": "updated"}))
        except VaultError as e:
            raise ValueError(str(e)) from e

    @server.tool()
    def delete_note(name: str, dry_run: bool = False) -> str:
        """Delete note. Updates [[links]] to [[name (deleted)]], moves to .trash/."""
        try:
            result = ops.delete(name, dry_run=dry_run)
            return inject_context(_json(asdict(result)))
        except VaultError as e:
            raise ValueError(str(e)) from e

    @server.tool()
    def rename_note(old_name: str, new_name: str, dry_run: bool = False) -> str:
        """Rename note and update all [[wikilinks]]."""
        try:
            result = ops.rename(old_name, new_name, dry_run=dry_run)
            return inject_context(_json(asdict(result)))
        except VaultError as e:
            raise ValueError(str(e)) from e

    @server.tool()
    def search_notes(
        query: str,
        mode: str = "name_partial",
        tag_logic: str = "or",
    ) -> str:
        """Search notes. mode: name|name_partial|content|tag. When mode=tag, query is comma-separated tags, tag_logic: and|or."""
        try:
            try:
                search_mode = SearchMode(mode)
            except ValueError:
                raise ValueError(
                    f"Invalid search mode: {mode}. "
                    f"Valid: name, name_partial, content, tag"
                )
            if search_mode == SearchMode.TAG:
                results = _search_multi_tag(query, tag_logic, ops.vault)
            else:
                results = ops.search(query, search_mode)
            return inject_context(_json([asdict(r) for r in results]))
        except VaultError as e:
            raise ValueError(str(e)) from e

    @server.tool()
    def get_links(name: str, direction: str = "both") -> str:
        """Get linked notes. direction: in|out|both."""
        try:
            try:
                link_dir = LinkDirection(direction)
            except ValueError:
                raise ValueError(
                    f"Invalid direction: {direction}. Valid: in, out, both"
                )
            result = ops.links(name, link_dir)
            return inject_context(_json(asdict(result)))
        except VaultError as e:
            raise ValueError(str(e)) from e

    @server.tool()
    def get_note_metadata(name: str) -> str:
        """Get note metadata without body: frontmatter + links."""
        try:
            fm = ops.frontmatter_get(name)
            links = ops.links(name, LinkDirection.BOTH)
            return inject_context(
                _json(
                    {
                        "name": name,
                        "frontmatter": fm,
                        "outgoing": links.outgoing,
                        "incoming": links.incoming,
                    }
                )
            )
        except VaultError as e:
            raise ValueError(str(e)) from e

    @server.tool()
    def set_frontmatter(name: str, key: str, value: str) -> str:
        """Set top-level frontmatter key. Tags are validated against allowed list. Value is parsed as JSON if valid (list/dict/bool/null), otherwise stored as string."""
        try:
            parsed_value: Any = value
            try:
                parsed = json.loads(value)
                if isinstance(parsed, (list, dict, bool)) or parsed is None:
                    parsed_value = parsed
            except json.JSONDecodeError:
                pass
            if key == "tags":
                if not isinstance(parsed_value, list):
                    raise ValueError(
                        'tags must be a JSON list, e.g. \'["tag1", "tag2"]\''
                    )
                _validate_tags(parsed_value, ops.vault)
            ops.frontmatter_set(name, key, parsed_value)
            return inject_context(
                _json({"name": name, "key": key, "value": parsed_value})
            )
        except VaultError as e:
            raise ValueError(str(e)) from e

    @server.tool()
    def add_tag(name: str, tag: str) -> str:
        """Add tag to note. Validates against allowed list and tag rules."""
        try:
            fm = ops.frontmatter_get(name)
            current_tags: list[str] = fm.get("tags", [])
            if tag not in current_tags:
                new_tags = current_tags + [tag]
                _validate_tags([tag], ops.vault)
                _validate_tag_rules([tag], name, fm)
                ops.frontmatter_set(name, "tags", new_tags)
            else:
                new_tags = current_tags
            return inject_context(_json({"name": name, "tags": new_tags}))
        except VaultError as e:
            raise ValueError(str(e)) from e

    @server.tool()
    def remove_tag(name: str, tag: str) -> str:
        """Remove tag from note."""
        try:
            fm = ops.frontmatter_get(name)
            current_tags: list[str] = fm.get("tags", [])
            removed = tag in current_tags
            new_tags = [t for t in current_tags if t != tag]
            if removed:
                ops.frontmatter_set(name, "tags", new_tags)
            return inject_context(
                _json({"name": name, "tags": new_tags, "removed": removed})
            )
        except VaultError as e:
            raise ValueError(str(e)) from e

    @server.tool()
    def list_notes(limit: int = 100, offset: int = 0) -> str:
        """List note names in vault (names only, no paths). Paginated: limit (default 100), offset (default 0)."""
        all_names = sorted(n.name for n in ops.vault.list_notes())
        page = all_names[offset : offset + limit]
        return inject_context(
            _json(
                {
                    "names": page,
                    "total": len(all_names),
                    "limit": limit,
                    "offset": offset,
                }
            )
        )

    @server.tool()
    def replace_text(
        name: str,
        old_text: str,
        new_text: str,
        replace_all: bool = False,
    ) -> str:
        """Replace text in note body. Frontmatter preserved. Returns JSON with replacement count."""
        try:
            result = ops.replace(name, old_text, new_text, replace_all=replace_all)
            return inject_context(
                _json({"name": result.name, "replaced": result.replacements})
            )
        except VaultError as e:
            raise ValueError(str(e)) from e

    @server.tool()
    def insert_text(
        name: str,
        text: str,
        before: str = "",
        after: str = "",
    ) -> str:
        """Insert text before/after a pattern line in note body. Exactly one of before/after must be non-empty."""
        if (not before and not after) or (before and after):
            raise ValueError("Exactly one of 'before' or 'after' must be provided")
        try:
            result = ops.insert(
                name,
                text,
                before=before or None,
                after=after or None,
            )
            return inject_context(
                _json(
                    {
                        "name": result.name,
                        "position": result.position,
                        "pattern": result.pattern,
                    }
                )
            )
        except VaultError as e:
            raise ValueError(str(e)) from e

    @server.tool()
    def read_section(name: str, section: str) -> str:
        """Read section content by heading. Section can be '## Heading' or plain 'Heading'. Returns plain text (without the heading line)."""
        try:
            return inject_context(ops.read_section(name, section))
        except VaultError as e:
            raise ValueError(str(e)) from e

    @server.tool()
    def append_section(name: str, section: str, text: str) -> str:
        """Append text to end of section. Section can be '## Heading' or plain 'Heading'. Returns JSON confirmation."""
        try:
            ops.append_section(name, section, text)
            return inject_context(
                _json({"name": name, "section": section, "status": "appended"})
            )
        except VaultError as e:
            raise ValueError(str(e)) from e

    @server.tool()
    def get_headings(name: str) -> str:
        """Get all headings from note. Returns JSON list of {level, text}."""
        try:
            headings = ops.get_headings(name)
            return inject_context(
                _json([{"level": h.level, "text": h.text} for h in headings])
            )
        except VaultError as e:
            raise ValueError(str(e)) from e

    @server.tool()
    def update_section(name: str, section: str, content: str) -> str:
        """Replace section content (heading preserved). Section can be '## Heading' or plain 'Heading'."""
        try:
            ops.update_section(name, section, content)
            return inject_context(
                _json({"name": name, "section": section, "status": "updated"})
            )
        except VaultError as e:
            raise ValueError(str(e)) from e

    @server.tool()
    def delete_section(name: str, section: str) -> str:
        """Delete section including its heading. Section can be '## Heading' or plain 'Heading'."""
        try:
            ops.delete_section(name, section)
            return inject_context(
                _json({"name": name, "section": section, "status": "deleted"})
            )
        except VaultError as e:
            raise ValueError(str(e)) from e

    @server.tool()
    def find_broken_links() -> str:
        """Find all broken links (links to non-existent notes). Returns JSON list of {source, target}."""
        broken = ops.find_broken_links()
        return inject_context(
            _json([{"source": b.source, "target": b.target} for b in broken])
        )

    @server.tool()
    def get_help() -> str:
        """Get list of all available tools with descriptions and parameters."""
        tools_info = [
            {
                "name": "read_note",
                "params": "name: str",
                "description": "Read full note content (frontmatter + body)",
            },
            {
                "name": "create_note",
                "params": "name: str, content: str = '', frontmatter: str = ''",
                "description": "Create new note. frontmatter is JSON string",
            },
            {
                "name": "update_note",
                "params": "name: str, content: str",
                "description": "Replace body of note (frontmatter preserved)",
            },
            {
                "name": "append_note",
                "params": "name: str, text: str",
                "description": "Append text to end of note",
            },
            {
                "name": "delete_note",
                "params": "name: str, dry_run: bool = False",
                "description": "Delete note, move to .trash/, update wikilinks",
            },
            {
                "name": "rename_note",
                "params": "old_name: str, new_name: str, dry_run: bool = False",
                "description": "Rename note and update all wikilinks",
            },
            {
                "name": "search_notes",
                "params": "query: str, mode: str = 'name_partial', tag_logic: str = 'or'",
                "description": "Search notes. mode: name|name_partial|content|tag",
            },
            {
                "name": "get_links",
                "params": "name: str, direction: str = 'both'",
                "description": "Get linked notes. direction: in|out|both",
            },
            {
                "name": "get_note_metadata",
                "params": "name: str",
                "description": "Get frontmatter + links without body (fast scan)",
            },
            {
                "name": "set_frontmatter",
                "params": "name: str, key: str, value: str",
                "description": "Set frontmatter key. Value parsed as JSON if valid",
            },
            {
                "name": "add_tag",
                "params": "name: str, tag: str",
                "description": "Add tag to note (validates against allowed list)",
            },
            {
                "name": "remove_tag",
                "params": "name: str, tag: str",
                "description": "Remove tag from note",
            },
            {
                "name": "list_notes",
                "params": "limit: int = 100, offset: int = 0",
                "description": "List note names (paginated)",
            },
            {
                "name": "replace_text",
                "params": "name: str, old_text: str, new_text: str, replace_all: bool = False",
                "description": "Replace text in note body (frontmatter preserved)",
            },
            {
                "name": "insert_text",
                "params": "name: str, text: str, before: str = '', after: str = ''",
                "description": "Insert text before/after pattern line",
            },
            {
                "name": "read_section",
                "params": "name: str, section: str",
                "description": "Read section content by heading",
            },
            {
                "name": "append_section",
                "params": "name: str, section: str, text: str",
                "description": "Append text to end of section",
            },
            {
                "name": "get_headings",
                "params": "name: str",
                "description": "Get all headings from note [{level, text}]",
            },
            {
                "name": "update_section",
                "params": "name: str, section: str, content: str",
                "description": "Replace section content (heading preserved)",
            },
            {
                "name": "delete_section",
                "params": "name: str, section: str",
                "description": "Delete section including heading",
            },
            {
                "name": "find_broken_links",
                "params": "",
                "description": "Find wikilinks to non-existent notes",
            },
            {
                "name": "get_help",
                "params": "",
                "description": "This help message",
            },
        ]
        return inject_context(_json(tools_info))


def main() -> None:
    """Entry point for obs-mcp."""
    vault_path = os.environ.get("OBSIDIAN_VAULT_PATH")
    if not vault_path:
        sys.exit("OBSIDIAN_VAULT_PATH not set")
    server = _create_server(vault_path)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
