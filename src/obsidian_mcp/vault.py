"""Obsidian vault access layer."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

from obsidian_mcp.errors import NoteNotFoundError, VaultNotConfiguredError

_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)\]\]")
_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?(.*)", re.DOTALL)


class Note:
    """Parsed note representation."""

    __slots__ = ("name", "path", "frontmatter", "body", "outgoing_links", "tags")

    def __init__(
        self,
        name: str,
        path: Path,
        frontmatter: dict[str, Any],
        body: str,
        outgoing_links: list[str],
        tags: list[str],
    ) -> None:
        self.name = name
        self.path = path
        self.frontmatter = frontmatter
        self.body = body
        self.outgoing_links = outgoing_links
        self.tags = tags


class Vault:
    """Obsidian vault access layer."""

    def __init__(self, vault_path: Path) -> None:
        if not vault_path.exists():
            raise VaultNotConfiguredError(f"Vault path does not exist: {vault_path}")
        if not vault_path.is_dir():
            raise VaultNotConfiguredError(
                f"Vault path is not a directory: {vault_path}"
            )
        self.vault_path = vault_path
        self._notes: dict[str, Note] | None = None
        self._incoming_links: dict[str, list[str]] | None = None

    @staticmethod
    def from_env(vault_path_override: str | None = None) -> Vault:
        raw = vault_path_override or os.environ.get("OBSIDIAN_VAULT_PATH")
        if not raw:
            raise VaultNotConfiguredError(
                "Vault path not configured. Set OBSIDIAN_VAULT_PATH env var "
                "or pass --vault-path flag."
            )
        return Vault(Path(raw))

    def _ensure_index(self) -> None:
        if self._notes is None:
            self._build_index()

    def list_notes(self) -> list[Note]:
        self._ensure_index()
        assert self._notes is not None
        return list(self._notes.values())

    def get_note(self, name: str) -> Note:
        self._ensure_index()
        assert self._notes is not None
        note = self._notes.get(name)
        if note is None:
            self.refresh()
            note = self._notes.get(name)
        if note is None:
            raise NoteNotFoundError(f"Note '{name}' not found")
        return note

    def resolve_path(self, name: str) -> Path:
        return self.get_note(name).path

    def get_incoming_links(self, name: str) -> list[str]:
        self._ensure_index()
        assert self._incoming_links is not None
        return self._incoming_links.get(name, [])

    def get_outgoing_links(self, name: str) -> list[str]:
        return self.get_note(name).outgoing_links

    def refresh(self) -> None:
        self._notes = None
        self._incoming_links = None
        self._build_index()

    def _build_index(self) -> None:
        files = self._scan_files(self.vault_path)
        notes: dict[str, Note] = {}
        for f in files:
            note = self._parse_note(f)
            notes[note.name] = note
        self._notes = notes

        incoming: dict[str, list[str]] = {}
        for note in notes.values():
            for target in note.outgoing_links:
                incoming.setdefault(target, []).append(note.name)
        self._incoming_links = incoming

    @staticmethod
    def _scan_files(vault_path: Path) -> list[Path]:
        result: list[Path] = []
        for item in vault_path.rglob("*.md"):
            if any(part.startswith(".") for part in item.relative_to(vault_path).parts):
                continue
            result.append(item)
        return result

    @staticmethod
    def _parse_note(path: Path) -> Note:
        raw = path.read_text(encoding="utf-8")
        raw = raw.lstrip("\ufeff")  # strip UTF-8 BOM
        raw = raw.replace("\r\n", "\n")  # normalize CRLF to LF
        name = path.stem

        m = _FRONTMATTER_RE.match(raw)
        if m:
            yaml_str, body = m.group(1), m.group(2)
            try:
                frontmatter = yaml.safe_load(yaml_str) or {}
            except yaml.YAMLError:
                frontmatter = {}
        else:
            frontmatter = {}
            body = raw

        outgoing_links = Vault._extract_wikilinks(body)
        tags = Vault._extract_tags(frontmatter)

        return Note(
            name=name,
            path=path,
            frontmatter=frontmatter,
            body=body,
            outgoing_links=outgoing_links,
            tags=tags,
        )

    @staticmethod
    def _extract_wikilinks(body: str) -> list[str]:
        return _WIKILINK_RE.findall(body)

    @staticmethod
    def _extract_tags(frontmatter: dict[str, Any]) -> list[str]:
        raw_tags = frontmatter.get("tags", [])
        if isinstance(raw_tags, str):
            return [raw_tags]
        if isinstance(raw_tags, list):
            return [str(t) for t in raw_tags]
        return []
