"""MCP server spec tests (mcp_server.technical.md).

Creates tools via _register_tools with explicit ops, then calls
tool functions directly through the server's internal tool registry.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from mcp.server.fastmcp import FastMCP

from obsidian_mcp.operations import Operations
from obsidian_mcp.vault import Vault
from obsidian_mcp import mcp_server


@pytest.fixture()
def vault_dir(tmp_path: Path) -> Path:
    return tmp_path


class _Tools:
    """Wrapper to call MCP tool functions by name.

    Creates Vault + Operations internally — same instance used for
    both context block and tools, matching production code path.
    """

    def __init__(self, vault_dir: Path) -> None:
        vault = Vault(vault_dir)
        self.ops = Operations(vault)
        instructions = mcp_server._build_instructions()
        context_block = mcp_server._build_context_block(vault)
        self._context_state = {"injected": False}

        def inject_context(result: str) -> str:
            if self._context_state["injected"] or not context_block:
                return result
            self._context_state["injected"] = True
            return (
                result
                + "\n\n<!-- CLAUDE CONTEXT (do not copy to notes):\n"
                + context_block
                + "\n-->"
            )

        self._inject_context = inject_context
        server = FastMCP("obsidian-cli", instructions=instructions)
        mcp_server._register_tools(server, self.ops, inject_context)
        self._server = server
        self._instructions = instructions
        self._context_block = context_block
        self._tools: dict[str, Any] = {}
        for tool in server._tool_manager._tools.values():
            self._tools[tool.fn.__name__] = tool.fn

    def reset_context(self) -> None:
        """Reset context injection state for testing second-call behavior."""
        self._context_state["injected"] = False

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        fn = self._tools.get(name)
        if fn is None:
            raise AttributeError(f"No tool named {name}")
        return fn


@pytest.fixture()
def tools(vault_dir: Path) -> _Tools:
    return _Tools(vault_dir)


def _write_note(vault_dir: Path, name: str, content: str) -> Path:
    path = vault_dir / f"{name}.md"
    path.write_text(content, encoding="utf-8")
    return path


def _read_note(vault_dir: Path, name: str) -> str:
    return (vault_dir / f"{name}.md").read_text(encoding="utf-8")


# --- TC1: read_note ---


def test_read_note(vault_dir: Path, tools: _Tools) -> None:
    _write_note(vault_dir, "test", "Hello")
    tools.ops.vault.refresh()
    result = tools.read_note("test")
    assert "Hello" in result


# --- TC2: read_note not found ---


def test_read_note_not_found(tools: _Tools) -> None:
    with pytest.raises(ValueError, match="not found"):
        tools.read_note("nonexistent")


# --- TC3: create_note basic ---


def test_create_note_basic(vault_dir: Path, tools: _Tools) -> None:
    raw = tools.create_note("test", content="Hello")
    result = json.loads(raw.split("\n\n<!--")[0])
    assert result["name"] == "test"
    assert (vault_dir / "test.md").exists()
    assert _read_note(vault_dir, "test") == "Hello"


# --- TC4: create_note with frontmatter ---


def test_create_note_with_frontmatter(vault_dir: Path) -> None:
    _write_note(vault_dir, "existing", "---\ntags: [vc]\n---\nBody")
    tools = _Tools(vault_dir)
    tools.create_note("test", frontmatter='{"tags": ["vc"]}')
    content = _read_note(vault_dir, "test")
    assert "tags:" in content
    assert "- vc" in content


# --- TC5: append_note ---


def test_append_note(vault_dir: Path, tools: _Tools) -> None:
    tools.ops.create("test", content="Line1")
    raw = tools.append_note("test", "Line2")
    result = json.loads(raw.split("\n\n<!--")[0])
    assert result["status"] == "appended"
    assert _read_note(vault_dir, "test") == "Line1\n\nLine2"


# --- TC6: update_note ---


def test_update_note(vault_dir: Path, tools: _Tools) -> None:
    _write_note(vault_dir, "test", "---\ntags:\n- a\n---\nOld")
    tools.ops.vault.refresh()
    raw = tools.update_note("test", "New")
    result = json.loads(raw.split("\n\n<!--")[0])
    assert result["status"] == "updated"
    content = _read_note(vault_dir, "test")
    assert "New" in content
    assert "- a" in content
    assert "Old" not in content


# --- TC7: delete_note ---


def test_delete_note(vault_dir: Path, tools: _Tools) -> None:
    _write_note(vault_dir, "A", "See [[B]] for info")
    _write_note(vault_dir, "B", "I am B")
    tools.ops.vault.refresh()

    raw = tools.delete_note("B")
    result = json.loads(raw.split("\n\n<!--")[0])
    assert "A" in result["files_updated"]
    assert (vault_dir / ".trash" / "B.md").exists()


# --- TC8: delete_note dry_run ---


def test_delete_note_dry_run(vault_dir: Path, tools: _Tools) -> None:
    _write_note(vault_dir, "A", "See [[B]] for info")
    _write_note(vault_dir, "B", "I am B")
    tools.ops.vault.refresh()

    raw = tools.delete_note("B", dry_run=True)
    result = json.loads(raw.split("\n\n<!--")[0])
    assert "A" in result["files_updated"]
    assert (vault_dir / "B.md").exists()


# --- TC9: rename_note ---


def test_rename_note(vault_dir: Path, tools: _Tools) -> None:
    _write_note(vault_dir, "A", "See [[B]]")
    _write_note(vault_dir, "B", "I am B")
    tools.ops.vault.refresh()

    raw = tools.rename_note("B", "B_new")
    result = json.loads(raw.split("\n\n<!--")[0])
    assert result["new_name"] == "B_new"
    assert (vault_dir / "B_new.md").exists()
    assert "[[B_new]]" in _read_note(vault_dir, "A")


# --- TC10: search_notes ---


def test_search_notes(vault_dir: Path, tools: _Tools) -> None:
    _write_note(vault_dir, "alpha", "content")
    _write_note(vault_dir, "beta", "content")
    tools.ops.vault.refresh()

    raw = tools.search_notes("alph")
    results = json.loads(raw.split("\n\n<!--")[0])
    names = [r["name"] for r in results]
    assert "alpha" in names
    assert "beta" not in names


# --- TC11: search_notes by tag ---


def test_search_notes_by_tag(vault_dir: Path, tools: _Tools) -> None:
    _write_note(vault_dir, "test", "---\ntags: [vc/project]\n---\nBody")
    tools.ops.vault.refresh()

    raw = tools.search_notes("vc", mode="tag")
    results = json.loads(raw.split("\n\n<!--")[0])
    assert len(results) == 1
    assert results[0]["name"] == "test"


# --- TC12: get_links ---


def test_get_links(vault_dir: Path, tools: _Tools) -> None:
    _write_note(vault_dir, "A", "Links to [[B]]")
    _write_note(vault_dir, "B", "content")
    _write_note(vault_dir, "C", "Links to [[A]]")
    tools.ops.vault.refresh()

    raw = tools.get_links("A", direction="both")
    result = json.loads(raw.split("\n\n<!--")[0])
    assert "B" in result["outgoing"]
    assert "C" in result["incoming"]


# --- TC14: set_frontmatter ---


def test_set_frontmatter(vault_dir: Path, tools: _Tools) -> None:
    _write_note(vault_dir, "test", "---\ntags:\n- a\n---\nBody")
    tools.ops.vault.refresh()

    raw = tools.set_frontmatter("test", "status", "done")
    result = json.loads(raw.split("\n\n<!--")[0])
    assert result["key"] == "status"
    content = _read_note(vault_dir, "test")
    assert "status: done" in content


# --- TC15: list_notes paginated ---


def test_list_notes_paginated(vault_dir: Path) -> None:
    _write_note(vault_dir, "alpha", "content")
    _write_note(vault_dir, "beta", "content")
    _write_note(vault_dir, "gamma", "content")
    tools = _Tools(vault_dir)

    raw = tools.list_notes(limit=2, offset=0)
    result = json.loads(raw.split("\n\n<!--")[0])
    assert result == {"names": ["alpha", "beta"], "total": 3, "limit": 2, "offset": 0}


# --- TC16: list_notes empty vault ---


def test_list_notes_empty(vault_dir: Path) -> None:
    tools = _Tools(vault_dir)
    raw = tools.list_notes()
    json_part = raw.split("\n\n<!--")[0]
    result = json.loads(json_part)
    assert result == {"names": [], "total": 0, "limit": 100, "offset": 0}


# --- TC16a: list_notes offset ---


def test_list_notes_offset(vault_dir: Path) -> None:
    _write_note(vault_dir, "alpha", "content")
    _write_note(vault_dir, "beta", "content")
    _write_note(vault_dir, "gamma", "content")
    tools = _Tools(vault_dir)

    raw = tools.list_notes(limit=2, offset=2)
    result = json.loads(raw.split("\n\n<!--")[0])
    assert result == {"names": ["gamma"], "total": 3, "limit": 2, "offset": 2}


# --- TC17: auto-context injected in first tool result ---


def test_autocontext_injected_first_call(vault_dir: Path) -> None:
    _write_note(
        vault_dir,
        "My Rules",
        '---\ntags: [claude]\ndescription: "Read before writing text"\n---\nBody',
    )
    tools = _Tools(vault_dir)
    result = tools.list_notes()
    assert "<!-- CLAUDE CONTEXT" in result
    assert "Your personal notes:" in result
    assert '"My Rules"' in result
    assert "Read before writing text" in result
    assert result.endswith("-->")


# --- TC18: auto-context not injected in second tool result ---


def test_autocontext_not_injected_second_call(vault_dir: Path) -> None:
    _write_note(
        vault_dir,
        "My Rules",
        '---\ntags: [claude]\ndescription: "Read before writing text"\n---\nBody',
    )
    _write_note(vault_dir, "test", "Hello")
    tools = _Tools(vault_dir)
    # First call — context injected
    tools.list_notes()
    # Second call — no context
    result = tools.read_note("test")
    assert "## Your personal notes" not in result


# --- TC19: auto-context no notes — hint in first tool result ---


def test_autocontext_no_notes_hint(vault_dir: Path) -> None:
    tools = _Tools(vault_dir)
    result = tools.list_notes()
    assert "Your personal notes:" in result
    assert "No personal notes found" in result


# --- TC20: auto-context missing description ---


def test_autocontext_missing_description(vault_dir: Path) -> None:
    _write_note(vault_dir, "No Desc", "---\ntags: [claude]\n---\nBody")
    tools = _Tools(vault_dir)
    result = tools.list_notes()
    assert '"No Desc"' in result
    assert "No description" in result
    assert "please add" in result


# --- TC21: no global ops singleton ---


def test_no_global_ops_singleton() -> None:
    assert not hasattr(mcp_server, "_ops")


# --- TC22: single Vault instance ---


def test_single_vault_instance(vault_dir: Path) -> None:
    tools = _Tools(vault_dir)
    assert tools.ops.vault is tools.ops.vault


# --- TC23: tag policy in first tool result ---


def test_tag_policy_in_first_result(vault_dir: Path) -> None:
    _write_note(vault_dir, "a", "---\ntags: [vc, vc/project]\n---\nBody")
    _write_note(vault_dir, "b", "---\ntags: [Person]\n---\nBody")
    tools = _Tools(vault_dir)
    result = tools.list_notes()
    assert "Allowed tags:" in result
    assert "Person" in result
    assert "vc" in result
    assert "vc/project" in result


# --- TC24: tag policy empty vault ---


def test_tag_policy_empty_vault(vault_dir: Path) -> None:
    tools = _Tools(vault_dir)
    result = tools.list_notes()
    assert "Allowed tags:" in result
    assert "No tags in vault yet" in result


# --- TC25: tag policy deduplication ---


def test_tag_policy_deduplication(vault_dir: Path) -> None:
    _write_note(vault_dir, "a", "---\ntags: [vc]\n---\nBody")
    _write_note(vault_dir, "b", "---\ntags: [vc]\n---\nBody")
    vault = Vault(vault_dir)
    section = mcp_server._build_tag_policy(vault)
    assert section.count("vc") == 1


# --- TC26: instructions contain only base instructions ---


def test_instructions_base_only(vault_dir: Path) -> None:
    _write_note(
        vault_dir,
        "My Rules",
        '---\ntags: [claude]\ndescription: "Read before writing text"\n---\nBody',
    )
    (vault_dir / "CLAUDE.md").write_text(
        "Custom rule: always use tag 'vc'", encoding="utf-8"
    )
    instructions = mcp_server._build_instructions()
    assert instructions == mcp_server._BASE_INSTRUCTIONS
    assert "Custom rule" not in instructions
    assert "Your personal notes" not in instructions
    assert "Allowed tags" not in instructions


# --- TC27: no CLAUDE.md file mechanism ---


def test_no_claude_md_mechanism(vault_dir: Path) -> None:
    (vault_dir / "CLAUDE.md").write_text("Custom vault rules", encoding="utf-8")
    tools = _Tools(vault_dir)
    result = tools.list_notes()
    assert "Custom vault rules" not in result
    assert "Vault-specific rules" not in result


# --- TC28: context block with hints ---


def test_context_block_with_hints(vault_dir: Path) -> None:
    vault = Vault(vault_dir)
    block = mcp_server._build_context_block(vault)
    assert "No personal notes found" in block
    assert "No tags in vault yet" in block


# --- TC29: replace_text ---


def test_replace_text(vault_dir: Path, tools: _Tools) -> None:
    _write_note(vault_dir, "test", "foo bar foo")
    tools.ops.vault.refresh()

    raw = tools.replace_text("test", "foo", "baz")
    result = json.loads(raw.split("\n\n<!--")[0])
    assert result == {"name": "test", "replaced": 1}


# --- TC30: replace_text replace_all ---


def test_replace_text_all(vault_dir: Path, tools: _Tools) -> None:
    _write_note(vault_dir, "test", "foo bar foo")
    tools.ops.vault.refresh()

    raw = tools.replace_text("test", "foo", "baz", replace_all=True)
    result = json.loads(raw.split("\n\n<!--")[0])
    assert result == {"name": "test", "replaced": 2}


# --- TC31: replace_text not found ---


def test_replace_text_not_found(vault_dir: Path, tools: _Tools) -> None:
    _write_note(vault_dir, "test", "hello")
    tools.ops.vault.refresh()

    with pytest.raises(ValueError, match="not found"):
        tools.replace_text("test", "xyz", "abc")


# --- TC32: insert_text after ---


def test_insert_text_after(vault_dir: Path, tools: _Tools) -> None:
    _write_note(vault_dir, "test", "line1\nline2")
    tools.ops.vault.refresh()

    raw = tools.insert_text("test", "inserted", after="line1")
    result = json.loads(raw.split("\n\n<!--")[0])
    assert result == {"name": "test", "position": "after", "pattern": "line1"}


# --- TC33: insert_text before ---


def test_insert_text_before(vault_dir: Path, tools: _Tools) -> None:
    _write_note(vault_dir, "test", "line1\nline2")
    tools.ops.vault.refresh()

    raw = tools.insert_text("test", "inserted", before="line2")
    result = json.loads(raw.split("\n\n<!--")[0])
    assert result == {"name": "test", "position": "before", "pattern": "line2"}


# --- TC34: insert_text both params error ---


def test_insert_text_both_params(vault_dir: Path, tools: _Tools) -> None:
    _write_note(vault_dir, "test", "content")
    tools.ops.vault.refresh()

    with pytest.raises(ValueError, match="Exactly one"):
        tools.insert_text("test", "x", before="a", after="b")


# --- TC35: insert_text neither param error ---


def test_insert_text_neither_param(vault_dir: Path, tools: _Tools) -> None:
    _write_note(vault_dir, "test", "content")
    tools.ops.vault.refresh()

    with pytest.raises(ValueError, match="Exactly one"):
        tools.insert_text("test", "x")


# --- TC36: read_section ---


def test_read_section(vault_dir: Path, tools: _Tools) -> None:
    _write_note(vault_dir, "test", "# Intro\nHello\n# Other\nWorld")
    tools.ops.vault.refresh()

    result = tools.read_section("test", "# Intro")
    assert "Hello" in result


# --- TC37: read_section not found ---


def test_read_section_not_found(vault_dir: Path, tools: _Tools) -> None:
    _write_note(vault_dir, "test", "# Intro\nHello")
    tools.ops.vault.refresh()

    with pytest.raises(ValueError, match="not found"):
        tools.read_section("test", "# Missing")


# --- TC38: append_section ---


def test_append_section(vault_dir: Path, tools: _Tools) -> None:
    _write_note(vault_dir, "test", "# Intro\nHello\n# Other\nWorld")
    tools.ops.vault.refresh()

    raw = tools.append_section("test", "# Intro", "More")
    result = json.loads(raw.split("\n\n<!--")[0])
    assert result == {"name": "test", "section": "# Intro", "status": "appended"}


# --- TC39: create_note with invalid tags rejected ---


def test_create_note_invalid_tags(vault_dir: Path) -> None:
    _write_note(vault_dir, "existing", "---\ntags: [vc, Person]\n---\nBody")
    tools = _Tools(vault_dir)

    with pytest.raises(ValueError, match="Tags not in allowed list.*career"):
        tools.create_note("new", frontmatter='{"tags": ["vc", "career"]}')


# --- TC40: create_note with valid tags accepted ---


def test_create_note_valid_tags(vault_dir: Path) -> None:
    _write_note(vault_dir, "existing", "---\ntags: [vc, Person]\n---\nBody")
    tools = _Tools(vault_dir)

    raw = tools.create_note("new", frontmatter='{"tags": ["vc"]}')
    result = json.loads(raw.split("\n\n<!--")[0])
    assert result["name"] == "new"


# --- TC41: set_frontmatter tags validated ---


def test_set_frontmatter_tags_validated(vault_dir: Path) -> None:
    _write_note(vault_dir, "existing", "---\ntags: [vc, Person]\n---\nBody")
    _write_note(vault_dir, "test", "---\ntags: [vc]\n---\nBody")
    tools = _Tools(vault_dir)

    with pytest.raises(ValueError, match="Tags not in allowed list.*unknown"):
        tools.set_frontmatter("test", "tags", '["vc", "unknown"]')


# --- TC42: set_frontmatter non-tags key not validated ---


def test_set_frontmatter_non_tags_no_validation(vault_dir: Path) -> None:
    _write_note(vault_dir, "test", "---\ntags: [vc]\n---\nBody")
    tools = _Tools(vault_dir)

    raw = tools.set_frontmatter("test", "status", "done")
    result = json.loads(raw.split("\n\n<!--")[0])
    assert result["key"] == "status"


# --- TC43: create_note invalid JSON frontmatter ---


def test_create_note_invalid_json(vault_dir: Path, tools: _Tools) -> None:
    with pytest.raises(ValueError, match="Invalid frontmatter JSON"):
        tools.create_note("test", frontmatter="{invalid json}")


# --- TC44: search_notes invalid mode ---


def test_search_notes_invalid_mode(vault_dir: Path, tools: _Tools) -> None:
    _write_note(vault_dir, "test", "content")
    tools.ops.vault.refresh()

    with pytest.raises(ValueError, match="Invalid search mode"):
        tools.search_notes("test", mode="invalid")


# --- TC45: get_links invalid direction ---


def test_get_links_invalid_direction(vault_dir: Path, tools: _Tools) -> None:
    _write_note(vault_dir, "test", "content")
    tools.ops.vault.refresh()

    with pytest.raises(ValueError, match="Invalid direction"):
        tools.get_links("test", direction="invalid")


# --- TC46: add_tag Person to non-@-note ---


def test_add_tag_person_to_non_at_note(vault_dir: Path) -> None:
    _write_note(vault_dir, "test", "---\ntags: [vc]\n---\nBody")
    _write_note(vault_dir, "other", "---\ntags: [Person]\n---\nBody")
    tools = _Tools(vault_dir)

    with pytest.raises(ValueError, match="must start with '@'"):
        tools.add_tag("test", "Person")


# --- TC47: add_tag Person to @-note ---


def test_add_tag_person_to_at_note(vault_dir: Path) -> None:
    _write_note(vault_dir, "@John", "---\ntags: []\n---\nBody")
    _write_note(vault_dir, "other", "---\ntags: [Person]\n---\nBody")
    tools = _Tools(vault_dir)

    raw = tools.add_tag("@John", "Person")
    result = json.loads(raw.split("\n\n<!--")[0])
    assert result == {"name": "@John", "tags": ["Person"]}


# --- TC48: add_tag claude without description ---


def test_add_tag_claude_without_description(vault_dir: Path) -> None:
    _write_note(vault_dir, "test", "---\ntags: []\n---\nBody")
    _write_note(vault_dir, "other", "---\ntags: [claude]\n---\nBody")
    tools = _Tools(vault_dir)

    with pytest.raises(ValueError, match="Requires 'description' field"):
        tools.add_tag("test", "claude")


# --- TC49: add_tag claude with description ---


def test_add_tag_claude_with_description(vault_dir: Path) -> None:
    _write_note(vault_dir, "test", '---\ntags: []\ndescription: "My rules"\n---\nBody')
    _write_note(vault_dir, "other", "---\ntags: [claude]\n---\nBody")
    tools = _Tools(vault_dir)

    raw = tools.add_tag("test", "claude")
    result = json.loads(raw.split("\n\n<!--")[0])
    assert result == {"name": "test", "tags": ["claude"]}


# --- TC50: remove_tag basic ---


def test_remove_tag_basic(vault_dir: Path) -> None:
    _write_note(vault_dir, "test", "---\ntags: [vc, project]\n---\nBody")
    tools = _Tools(vault_dir)

    raw = tools.remove_tag("test", "vc")
    result = json.loads(raw.split("\n\n<!--")[0])
    assert result == {"name": "test", "tags": ["project"], "removed": True}


# --- TC51: remove_tag not present ---


def test_remove_tag_not_present(vault_dir: Path) -> None:
    _write_note(vault_dir, "test", "---\ntags: [vc]\n---\nBody")
    tools = _Tools(vault_dir)

    raw = tools.remove_tag("test", "project")
    result = json.loads(raw.split("\n\n<!--")[0])
    assert result == {"name": "test", "tags": ["vc"], "removed": False}


# --- TC52: create_note with Person tag on non-@ note ---


def test_create_note_person_tag_non_at_note(vault_dir: Path) -> None:
    _write_note(vault_dir, "other", "---\ntags: [Person]\n---\nBody")
    tools = _Tools(vault_dir)

    with pytest.raises(ValueError, match="must start with '@'"):
        tools.create_note("John", frontmatter='{"tags": ["Person"]}')


# --- TC53: create_note with Person tag on @-note ---


def test_create_note_person_tag_at_note(vault_dir: Path) -> None:
    _write_note(vault_dir, "other", "---\ntags: [Person]\n---\nBody")
    tools = _Tools(vault_dir)

    raw = tools.create_note("@John", frontmatter='{"tags": ["Person"]}')
    result = json.loads(raw.split("\n\n<!--")[0])
    assert result["name"] == "@John"


# --- TC54: search_notes multi-tag OR ---


def test_search_notes_multi_tag_or(vault_dir: Path) -> None:
    _write_note(vault_dir, "a", "---\ntags: [vc]\n---\nBody")
    _write_note(vault_dir, "b", "---\ntags: [project]\n---\nBody")
    _write_note(vault_dir, "c", "---\ntags: [vc, project]\n---\nBody")
    tools = _Tools(vault_dir)

    raw = tools.search_notes("vc,project", mode="tag", tag_logic="or")
    results = json.loads(raw.split("\n\n<!--")[0])
    names = sorted(r["name"] for r in results)
    assert names == ["a", "b", "c"]


# --- TC55: search_notes multi-tag AND ---


def test_search_notes_multi_tag_and(vault_dir: Path) -> None:
    _write_note(vault_dir, "a", "---\ntags: [vc]\n---\nBody")
    _write_note(vault_dir, "b", "---\ntags: [project]\n---\nBody")
    _write_note(vault_dir, "c", "---\ntags: [vc, project]\n---\nBody")
    tools = _Tools(vault_dir)

    raw = tools.search_notes("vc,project", mode="tag", tag_logic="and")
    results = json.loads(raw.split("\n\n<!--")[0])
    names = [r["name"] for r in results]
    assert names == ["c"]


# --- TC56: search_notes invalid tag_logic ---


def test_search_notes_invalid_tag_logic(vault_dir: Path) -> None:
    _write_note(vault_dir, "test", "---\ntags: [vc]\n---\nBody")
    tools = _Tools(vault_dir)

    with pytest.raises(ValueError, match="Invalid tag_logic"):
        tools.search_notes("vc", mode="tag", tag_logic="invalid")


# --- TC57: search_notes multi-tag hierarchical ---


def test_search_notes_multi_tag_hierarchical(vault_dir: Path) -> None:
    _write_note(vault_dir, "a", "---\ntags: [vc/project]\n---\nBody")
    _write_note(vault_dir, "b", "---\ntags: [vc/idea]\n---\nBody")
    tools = _Tools(vault_dir)

    raw = tools.search_notes("vc", mode="tag")
    results = json.loads(raw.split("\n\n<!--")[0])
    names = sorted(r["name"] for r in results)
    assert names == ["a", "b"]


# --- TC58: get_note_metadata ---


def test_get_note_metadata(vault_dir: Path) -> None:
    _write_note(vault_dir, "A", "---\ntags: [vc]\n---\nLinks to [[B]]")
    _write_note(vault_dir, "B", "content")
    _write_note(vault_dir, "C", "Links to [[A]]")
    tools = _Tools(vault_dir)

    raw = tools.get_note_metadata("A")
    result = json.loads(raw.split("\n\n<!--")[0])
    assert result["name"] == "A"
    assert result["frontmatter"] == {"tags": ["vc"]}
    assert result["outgoing"] == ["B"]
    assert result["incoming"] == ["C"]


# --- TC59: get_note_metadata not found ---


def test_get_note_metadata_not_found(tools: _Tools) -> None:
    with pytest.raises(ValueError, match="not found"):
        tools.get_note_metadata("nonexistent")


# --- TC60: get_headings basic ---


def test_get_headings_basic(vault_dir: Path) -> None:
    _write_note(vault_dir, "test", "# Intro\nText\n## Details\nMore\n### Sub")
    tools = _Tools(vault_dir)

    raw = tools.get_headings("test")
    result = json.loads(raw.split("\n\n<!--")[0])
    assert result == [
        {"level": 1, "text": "Intro"},
        {"level": 2, "text": "Details"},
        {"level": 3, "text": "Sub"},
    ]


# --- TC61: get_headings no headings ---


def test_get_headings_no_headings(vault_dir: Path) -> None:
    _write_note(vault_dir, "test", "Just plain text")
    tools = _Tools(vault_dir)

    raw = tools.get_headings("test")
    result = json.loads(raw.split("\n\n<!--")[0])
    assert result == []


# --- TC62: update_section basic ---


def test_update_section_basic(vault_dir: Path) -> None:
    _write_note(vault_dir, "test", "# Intro\nOld content\n# Other\nKeep")
    tools = _Tools(vault_dir)

    raw = tools.update_section("test", "Intro", "New content")
    result = json.loads(raw.split("\n\n<!--")[0])
    assert result == {"name": "test", "section": "Intro", "status": "updated"}

    content = _read_note(vault_dir, "test")
    assert "# Intro\nNew content\n# Other\nKeep" == content


# --- TC63: update_section not found ---


def test_update_section_not_found(vault_dir: Path) -> None:
    _write_note(vault_dir, "test", "# Intro\nContent")
    tools = _Tools(vault_dir)

    with pytest.raises(ValueError, match="not found"):
        tools.update_section("test", "Missing", "x")


# --- TC64: delete_section basic ---


def test_delete_section_basic(vault_dir: Path) -> None:
    _write_note(vault_dir, "test", "# Intro\nContent\n# Other\nKeep")
    tools = _Tools(vault_dir)

    raw = tools.delete_section("test", "Intro")
    result = json.loads(raw.split("\n\n<!--")[0])
    assert result == {"name": "test", "section": "Intro", "status": "deleted"}

    content = _read_note(vault_dir, "test")
    assert "# Other\nKeep" == content


# --- TC65: delete_section not found ---


def test_delete_section_not_found(vault_dir: Path) -> None:
    _write_note(vault_dir, "test", "# Intro\nContent")
    tools = _Tools(vault_dir)

    with pytest.raises(ValueError, match="not found"):
        tools.delete_section("test", "Missing")


# --- TC66: find_broken_links ---


def test_find_broken_links(vault_dir: Path) -> None:
    _write_note(vault_dir, "A", "Links to [[B]] and [[Missing]]")
    _write_note(vault_dir, "B", "exists")
    tools = _Tools(vault_dir)

    raw = tools.find_broken_links()
    result = json.loads(raw.split("\n\n<!--")[0])
    assert result == [{"source": "A", "target": "Missing"}]


# --- TC67: find_broken_links no broken ---


def test_find_broken_links_no_broken(vault_dir: Path) -> None:
    _write_note(vault_dir, "A", "Links to [[B]]")
    _write_note(vault_dir, "B", "exists")
    tools = _Tools(vault_dir)

    raw = tools.find_broken_links()
    result = json.loads(raw.split("\n\n<!--")[0])
    assert result == []


# --- TC68: get_help ---


def test_get_help(vault_dir: Path, tools: _Tools) -> None:
    raw = tools.get_help()
    result = json.loads(raw.split("\n\n<!--")[0])

    assert isinstance(result, list)
    assert len(result) > 0

    # Check structure
    for tool in result:
        assert "name" in tool
        assert "params" in tool
        assert "description" in tool

    # Check some known tools are present
    tool_names = [t["name"] for t in result]
    assert "read_note" in tool_names
    assert "create_note" in tool_names
    assert "get_help" in tool_names
    assert "find_broken_links" in tool_names
