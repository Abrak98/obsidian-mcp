"""Vault spec tests (vault.technical.md)."""

from __future__ import annotations

from pathlib import Path

import pytest

from obsidian_mcp.errors import NoteNotFoundError, VaultNotConfiguredError
from obsidian_mcp.vault import Vault


@pytest.fixture()
def vault_dir(tmp_path: Path) -> Path:
    """Create an empty vault directory."""
    return tmp_path


def _write_note(vault_dir: Path, name: str, content: str) -> Path:
    path = vault_dir / f"{name}.md"
    path.write_text(content, encoding="utf-8")
    return path


# --- TC1: from_env with override ---


def test_from_env_with_override(vault_dir: Path) -> None:
    vault = Vault.from_env(str(vault_dir))
    assert vault.vault_path == vault_dir


# --- TC2: from_env with env var ---


def test_from_env_with_env_var(
    vault_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault_dir))
    vault = Vault.from_env()
    assert vault.vault_path == vault_dir


# --- TC3: from_env without config ---


def test_from_env_without_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)
    with pytest.raises(VaultNotConfiguredError):
        Vault.from_env()


# --- TC4: scan files flat ---


def test_scan_files_flat(vault_dir: Path) -> None:
    _write_note(vault_dir, "a", "content a")
    _write_note(vault_dir, "b", "content b")
    (vault_dir / ".obsidian").mkdir()
    (vault_dir / ".obsidian" / "config").write_text("{}", encoding="utf-8")
    (vault_dir / ".trash").mkdir()
    _write_note(vault_dir / ".trash", "old", "trashed")

    files = Vault._scan_files(vault_dir)
    names = sorted(f.name for f in files)
    assert names == ["a.md", "b.md"]


# --- TC5: parse note with frontmatter ---


def test_parse_note_with_frontmatter(vault_dir: Path) -> None:
    path = _write_note(
        vault_dir,
        "test",
        "---\ntags: [vc, vc/project]\n---\n# Title\nBody with [[link1]] and [[link2]]",
    )
    note = Vault._parse_note(path)
    assert note.frontmatter == {"tags": ["vc", "vc/project"]}
    assert note.outgoing_links == ["link1", "link2"]
    assert note.tags == ["vc", "vc/project"]


# --- TC6: parse note without frontmatter ---


def test_parse_note_without_frontmatter(vault_dir: Path) -> None:
    path = _write_note(vault_dir, "test", "# Title\nJust body")
    note = Vault._parse_note(path)
    assert note.frontmatter == {}
    assert note.tags == []
    assert note.body == "# Title\nJust body"


# --- TC7: extract wikilinks ---


def test_extract_wikilinks() -> None:
    body = "See [[note1]] and [[note2]] for details"
    result = Vault._extract_wikilinks(body)
    assert result == ["note1", "note2"]


# --- TC8: get_note not found ---


def test_get_note_not_found(vault_dir: Path) -> None:
    _write_note(vault_dir, "a", "content")
    _write_note(vault_dir, "b", "content")
    vault = Vault(vault_dir)
    with pytest.raises(NoteNotFoundError):
        vault.get_note("c")


# --- TC9: incoming links ---


def test_incoming_links(vault_dir: Path) -> None:
    _write_note(vault_dir, "A", "I link to [[B]]")
    _write_note(vault_dir, "B", "I am B")
    _write_note(vault_dir, "C", "I also link to [[B]]")
    vault = Vault(vault_dir)
    incoming = vault.get_incoming_links("B")
    assert sorted(incoming) == ["A", "C"]


# --- TC10: outgoing links ---


def test_outgoing_links(vault_dir: Path) -> None:
    _write_note(vault_dir, "A", "Links to [[B]] and [[C]]")
    _write_note(vault_dir, "B", "content")
    _write_note(vault_dir, "C", "content")
    vault = Vault(vault_dir)
    outgoing = vault.get_outgoing_links("A")
    assert outgoing == ["B", "C"]


# --- TC11: refresh rebuilds index ---


def test_refresh_rebuilds_index(vault_dir: Path) -> None:
    _write_note(vault_dir, "A", "content")
    vault = Vault(vault_dir)
    assert len(vault.list_notes()) == 1

    _write_note(vault_dir, "B", "new note")
    vault.refresh()
    vault.get_note("B")  # should not raise
    assert len(vault.list_notes()) == 2


# --- TC12: get_note cache miss triggers rescan ---


def test_get_note_cache_miss_triggers_rescan(vault_dir: Path) -> None:
    _write_note(vault_dir, "A", "content")
    vault = Vault(vault_dir)
    vault.get_note("A")  # build index

    _write_note(vault_dir, "B", "new note")
    note = vault.get_note("B")  # should rescan automatically
    assert note.name == "B"


# --- TC13: get_note still raises after rescan if note missing ---


def test_get_note_raises_after_rescan_if_missing(vault_dir: Path) -> None:
    _write_note(vault_dir, "A", "content")
    vault = Vault(vault_dir)
    vault.get_note("A")  # build index

    with pytest.raises(NoteNotFoundError):
        vault.get_note("nonexistent")
