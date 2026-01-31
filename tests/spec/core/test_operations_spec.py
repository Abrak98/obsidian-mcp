"""Operations spec tests (operations.technical.md)."""

from __future__ import annotations

from pathlib import Path

import pytest

from obsidian_mcp.errors import (
    NoteAlreadyExistsError,
    NoteNotFoundError,
    SectionNotFoundError,
    TextNotFoundError,
)
from obsidian_mcp.operations import (
    LinkDirection,
    Operations,
    SearchMode,
)
from obsidian_mcp.vault import Vault


@pytest.fixture()
def vault_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture()
def ops(vault_dir: Path) -> Operations:
    vault = Vault(vault_dir)
    return Operations(vault)


def _write_note(vault_dir: Path, name: str, content: str) -> Path:
    path = vault_dir / f"{name}.md"
    path.write_text(content, encoding="utf-8")
    return path


def _read_note(vault_dir: Path, name: str) -> str:
    return (vault_dir / f"{name}.md").read_text(encoding="utf-8")


# --- TC1: create basic ---


def test_create_basic(vault_dir: Path, ops: Operations) -> None:
    result = ops.create("test", content="Hello")
    assert result.path == vault_dir / "test.md"
    assert result.path.read_text(encoding="utf-8") == "Hello"
    assert result.warnings == []


# --- TC2: create with frontmatter ---


def test_create_with_frontmatter(vault_dir: Path, ops: Operations) -> None:
    ops.create("test", frontmatter={"tags": ["vc"]}, content="Body")
    content = _read_note(vault_dir, "test")
    assert content.startswith("---\n")
    assert "tags:" in content
    assert "- vc" in content
    assert content.endswith("Body")


# --- TC3: create duplicate ---


def test_create_duplicate(vault_dir: Path, ops: Operations) -> None:
    ops.create("test")
    with pytest.raises(NoteAlreadyExistsError):
        ops.create("test")


# --- TC4: read ---


def test_read(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "test", "---\ntags: [a]\n---\nBody")
    ops.vault.refresh()
    text = ops.read("test")
    assert text == "---\ntags: [a]\n---\nBody"


# --- TC5: read not found ---


def test_read_not_found(ops: Operations) -> None:
    with pytest.raises(NoteNotFoundError):
        ops.read("nonexistent")


# --- TC6: append ---


def test_append(vault_dir: Path, ops: Operations) -> None:
    ops.create("test", content="Line1")
    ops.append("test", "Line2")
    content = _read_note(vault_dir, "test")
    assert content == "Line1\n\nLine2"


# --- TC24: update body preserving frontmatter ---


def test_update_body_preserving_frontmatter(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "test", "---\ntags:\n- a\n---\nOld body")
    ops.vault.refresh()

    ops.update("test", "New body")
    content = _read_note(vault_dir, "test")
    assert "New body" in content
    assert "- a" in content
    assert "Old body" not in content


# --- TC25: update not found ---


def test_update_not_found(ops: Operations) -> None:
    with pytest.raises(NoteNotFoundError):
        ops.update("nonexistent", "content")


# --- TC7: delete with link update ---


def test_delete_with_link_update(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "A", "See [[B]] for info")
    _write_note(vault_dir, "B", "I am B")
    ops.vault.refresh()

    result = ops.delete("B")
    assert (vault_dir / ".trash" / "B.md").exists()
    assert not (vault_dir / "B.md").exists()
    a_content = _read_note(vault_dir, "A")
    assert "[[B (deleted)]]" in a_content
    assert "A" in result.files_updated


# --- TC8: delete dry run ---


def test_delete_dry_run(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "A", "See [[B]] for info")
    _write_note(vault_dir, "B", "I am B")
    ops.vault.refresh()

    result = ops.delete("B", dry_run=True)
    assert "A" in result.files_updated
    # Files not changed
    assert (vault_dir / "B.md").exists()
    assert "[[B]]" in _read_note(vault_dir, "A")


# --- TC9: rename with link update ---


def test_rename_with_link_update(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "A", "See [[B]] for info")
    _write_note(vault_dir, "B", "I am B")
    ops.vault.refresh()

    result = ops.rename("B", "B_new")
    assert (vault_dir / "B_new.md").exists()
    assert not (vault_dir / "B.md").exists()
    a_content = _read_note(vault_dir, "A")
    assert "[[B_new]]" in a_content
    assert "A" in result.files_updated


# --- TC10: rename dry run ---


def test_rename_dry_run(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "A", "See [[B]] for info")
    _write_note(vault_dir, "B", "I am B")
    ops.vault.refresh()

    result = ops.rename("B", "B_new", dry_run=True)
    assert result.old_name == "B"
    assert result.new_name == "B_new"
    # Files not changed
    assert (vault_dir / "B.md").exists()
    assert not (vault_dir / "B_new.md").exists()
    assert "[[B]]" in _read_note(vault_dir, "A")


# --- TC11: rename to existing name ---


def test_rename_to_existing_name(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "A", "content")
    _write_note(vault_dir, "B", "content")
    ops.vault.refresh()

    with pytest.raises(NoteAlreadyExistsError):
        ops.rename("A", "B")


# --- TC12: frontmatter_get ---


def test_frontmatter_get(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "test", "---\ntags:\n- a\nstatus: draft\n---\nBody")
    ops.vault.refresh()

    fm = ops.frontmatter_get("test")
    assert fm == {"tags": ["a"], "status": "draft"}


# --- TC13: frontmatter_set ---


def test_frontmatter_set(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "test", "---\ntags:\n- a\n---\nHello")
    ops.vault.refresh()

    ops.frontmatter_set("test", "status", "done")
    content = _read_note(vault_dir, "test")
    assert "status: done" in content
    assert "Hello" in content
    # Original tag preserved
    assert "- a" in content


# --- TC14: search by name exact ---


def test_search_by_name_exact(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "alpha", "content")
    _write_note(vault_dir, "beta", "content")
    _write_note(vault_dir, "alpha_2", "content")
    ops.vault.refresh()

    results = ops.search("alpha", mode=SearchMode.NAME)
    assert len(results) == 1
    assert results[0].name == "alpha"


# --- TC15: search by name partial ---


def test_search_by_name_partial(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "alpha", "content")
    _write_note(vault_dir, "beta", "content")
    _write_note(vault_dir, "alpha_2", "content")
    ops.vault.refresh()

    results = ops.search("alph", mode=SearchMode.NAME_PARTIAL)
    names = sorted(r.name for r in results)
    assert names == ["alpha", "alpha_2"]


# --- TC16: search by content ---


def test_search_by_content(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "test", "Hello World")
    _write_note(vault_dir, "other", "Goodbye")
    ops.vault.refresh()

    results = ops.search("hello", mode=SearchMode.CONTENT)
    assert len(results) == 1
    assert results[0].name == "test"


# --- TC17: search by tag ---


def test_search_by_tag(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "test", "---\ntags: [vc, vc/project]\n---\nBody")
    _write_note(vault_dir, "other", "---\ntags: [misc]\n---\nBody")
    ops.vault.refresh()

    results = ops.search("vc", mode=SearchMode.TAG)
    assert len(results) == 1
    assert results[0].name == "test"


# --- TC18: search by tag hierarchical ---


def test_search_by_tag_hierarchical(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "test", "---\ntags: [vc/project]\n---\nBody")
    ops.vault.refresh()

    results = ops.search("vc", mode=SearchMode.TAG)
    assert len(results) == 1
    assert results[0].name == "test"


# --- TC19: links outgoing ---


def test_links_outgoing(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "A", "Links to [[B]] and [[C]]")
    _write_note(vault_dir, "B", "content")
    _write_note(vault_dir, "C", "content")
    ops.vault.refresh()

    result = ops.links("A", direction=LinkDirection.OUTGOING)
    assert result.outgoing == ["B", "C"]
    assert result.incoming == []


# --- TC20: links incoming ---


def test_links_incoming(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "A", "Links to [[B]]")
    _write_note(vault_dir, "B", "content")
    _write_note(vault_dir, "C", "Links to [[B]]")
    ops.vault.refresh()

    result = ops.links("B", direction=LinkDirection.INCOMING)
    assert result.outgoing == []
    assert sorted(result.incoming) == ["A", "C"]


# --- TC21: links both ---


def test_links_both(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "A", "Links to [[B]]")
    _write_note(vault_dir, "B", "content")
    _write_note(vault_dir, "C", "Links to [[A]]")
    ops.vault.refresh()

    result = ops.links("A", direction=LinkDirection.BOTH)
    assert result.outgoing == ["B"]
    assert result.incoming == ["C"]


# --- TC22: batch rename ---


def test_batch_rename(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "A", "content A")
    _write_note(vault_dir, "B", "content B")
    _write_note(vault_dir, "C", "Links to [[A]] and [[B]]")
    ops.vault.refresh()

    results = ops.batch_rename({"A": "A_new", "B": "B_new"})
    assert len(results) == 2
    assert (vault_dir / "A_new.md").exists()
    assert (vault_dir / "B_new.md").exists()
    c_content = _read_note(vault_dir, "C")
    assert "[[A_new]]" in c_content
    assert "[[B_new]]" in c_content


# --- TC23: batch delete ---


def test_batch_delete(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "A", "content A")
    _write_note(vault_dir, "B", "content B")
    _write_note(vault_dir, "C", "Links to [[A]] and [[B]]")
    ops.vault.refresh()

    results = ops.batch_delete(["A", "B"])
    assert len(results) == 2
    assert (vault_dir / ".trash" / "A.md").exists()
    assert (vault_dir / ".trash" / "B.md").exists()
    c_content = _read_note(vault_dir, "C")
    assert "[[A (deleted)]]" in c_content
    assert "[[B (deleted)]]" in c_content


# --- TC26: replace first occurrence ---


def test_replace_first_occurrence(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "test", "---\ntags:\n- a\n---\nfoo bar foo")
    ops.vault.refresh()

    result = ops.replace("test", "foo", "baz")
    assert result.replacements == 1
    content = _read_note(vault_dir, "test")
    assert "baz bar foo" in content
    assert "- a" in content


# --- TC27: replace all occurrences ---


def test_replace_all_occurrences(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "test", "foo bar foo")
    ops.vault.refresh()

    result = ops.replace("test", "foo", "baz", replace_all=True)
    assert result.replacements == 2
    content = _read_note(vault_dir, "test")
    assert content == "baz bar baz"


# --- TC28: replace text not found ---


def test_replace_text_not_found(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "test", "Hello")
    ops.vault.refresh()

    with pytest.raises(TextNotFoundError):
        ops.replace("test", "xyz", "abc")


# --- TC29: replace ignores frontmatter ---


def test_replace_ignores_frontmatter(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "test", "---\nstatus: draft\n---\nstatus: active")
    ops.vault.refresh()

    with pytest.raises(TextNotFoundError):
        ops.replace("test", "status: draft", "status: done")


# --- TC30: insert after pattern ---


def test_insert_after_pattern(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "test", "## Header\nContent\n## Footer")
    ops.vault.refresh()

    result = ops.insert("test", "New line", after="## Header")
    assert result.position == "after"
    content = _read_note(vault_dir, "test")
    assert content == "## Header\nNew line\nContent\n## Footer"


# --- TC31: insert before pattern ---


def test_insert_before_pattern(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "test", "Line1\nLine2\nLine3")
    ops.vault.refresh()

    result = ops.insert("test", "Inserted", before="Line2")
    assert result.position == "before"
    content = _read_note(vault_dir, "test")
    assert content == "Line1\nInserted\nLine2\nLine3"


# --- TC32: insert pattern not found ---


def test_insert_pattern_not_found(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "test", "Hello")
    ops.vault.refresh()

    with pytest.raises(TextNotFoundError):
        ops.insert("test", "text", after="## Missing")


# --- TC33: insert both before and after ---


def test_insert_both_before_and_after(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "test", "content")
    ops.vault.refresh()

    with pytest.raises(ValueError):
        ops.insert("test", "text", before="A", after="B")


# --- TC34: insert neither before nor after ---


def test_insert_neither_before_nor_after(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "test", "content")
    ops.vault.refresh()

    with pytest.raises(ValueError):
        ops.insert("test", "text")


# --- TC35: read_section basic ---


def test_read_section_basic(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "test", "## Budget\nAmount: 100\n## Timeline\nQ1 2024")
    ops.vault.refresh()

    content = ops.read_section("test", "## Budget")
    assert content == "Amount: 100"


# --- TC36: read_section with subsections ---


def test_read_section_with_subsections(vault_dir: Path, ops: Operations) -> None:
    _write_note(
        vault_dir,
        "test",
        "## Budget\nTotal: 500\n### Details\nItem: 100\n## Other",
    )
    ops.vault.refresh()

    content = ops.read_section("test", "## Budget")
    assert content == "Total: 500\n### Details\nItem: 100"


# --- TC37: read_section until EOF ---


def test_read_section_until_eof(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "test", "## Budget\nAmount: 100")
    ops.vault.refresh()

    content = ops.read_section("test", "## Budget")
    assert content == "Amount: 100"


# --- TC38: read_section not found ---


def test_read_section_not_found(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "test", "## Budget\nContent")
    ops.vault.refresh()

    with pytest.raises(SectionNotFoundError):
        ops.read_section("test", "## Missing")


# --- TC39: append_section basic ---


def test_append_section_basic(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "test", "## Questions\n- Q1\n## Done")
    ops.vault.refresh()

    ops.append_section("test", "## Questions", "- Q2")
    content = _read_note(vault_dir, "test")
    assert content == "## Questions\n- Q1\n- Q2\n## Done"


# --- TC40: append_section at EOF ---


def test_append_section_at_eof(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "test", "## Questions\n- Q1")
    ops.vault.refresh()

    ops.append_section("test", "## Questions", "- Q2")
    content = _read_note(vault_dir, "test")
    assert content == "## Questions\n- Q1\n- Q2"


# --- TC41: append_section not found ---


def test_append_section_not_found(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "test", "## Budget")
    ops.vault.refresh()

    with pytest.raises(SectionNotFoundError):
        ops.append_section("test", "## Missing", "text")


# --- TC42: replace in note without frontmatter ---


def test_replace_no_frontmatter(vault_dir: Path, ops: Operations) -> None:
    _write_note(vault_dir, "test", "Hello World")
    ops.vault.refresh()

    ops.replace("test", "Hello", "Hi")
    content = _read_note(vault_dir, "test")
    assert content == "Hi World"
    assert "---" not in content


# --- TC43: get_headings ignores code blocks ---


def test_get_headings_ignores_code_blocks(vault_dir: Path, ops: Operations) -> None:
    _write_note(
        vault_dir,
        "test",
        "# Real Heading\n\n```python\n# Comment not heading\ndef foo():\n    pass\n```\n\n## Another Real",
    )
    ops.vault.refresh()

    headings = ops.get_headings("test")
    assert len(headings) == 2
    assert headings[0].level == 1
    assert headings[0].text == "Real Heading"
    assert headings[1].level == 2
    assert headings[1].text == "Another Real"


# --- TC44: get_headings with nested code blocks ---


def test_get_headings_nested_code_blocks(vault_dir: Path, ops: Operations) -> None:
    _write_note(
        vault_dir,
        "test",
        "# Title\n\n````\n```\n# Not heading\n```\n````\n\n## Footer",
    )
    ops.vault.refresh()

    headings = ops.get_headings("test")
    assert len(headings) == 2
    assert headings[0].text == "Title"
    assert headings[1].text == "Footer"
