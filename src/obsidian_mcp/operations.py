"""All note operations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

import re

from obsidian_mcp.errors import (
    NoteAlreadyExistsError,
    NoteNotFoundError,
    SectionNotFoundError,
    TextNotFoundError,
)
from obsidian_mcp.validation import (
    BrokenLinkError,
    ValidationWarning,
    Validator,
)
from obsidian_mcp.vault import Vault

# Regex for wikilinks with optional section: [[Note]] or [[Note#Section]]
_WIKILINK_WITH_SECTION_RE = re.compile(r"\[\[([^\]#|]+)(?:#([^\]|]+))?\]\]")


class SearchMode(str, Enum):
    NAME = "name"
    NAME_PARTIAL = "name_partial"
    CONTENT = "content"
    TAG = "tag"


class LinkDirection(str, Enum):
    OUTGOING = "out"
    INCOMING = "in"
    BOTH = "both"


@dataclass(slots=True)
class SearchResult:
    name: str
    path: str


@dataclass(slots=True)
class RenameResult:
    old_name: str
    new_name: str
    files_updated: list[str]


@dataclass(slots=True)
class DeleteResult:
    name: str
    trash_path: str
    files_updated: list[str]


@dataclass(slots=True)
class LinksResult:
    name: str
    outgoing: list[str]
    incoming: list[str]


@dataclass(slots=True)
class ReplaceResult:
    name: str
    replacements: int


@dataclass(slots=True)
class InsertResult:
    name: str
    position: str
    pattern: str


@dataclass(slots=True)
class Heading:
    level: int
    text: str


@dataclass(slots=True)
class BrokenLink:
    source: str
    target: str


@dataclass(slots=True)
class CreateResult:
    path: Path
    warnings: list[ValidationWarning]


@dataclass(slots=True)
class WriteResult:
    warnings: list[ValidationWarning]


class Operations:
    """All note operations. Stateless — uses Vault for data access."""

    def __init__(self, vault: Vault) -> None:
        self.vault = vault
        self._validator = Validator()

    def _validate_wikilinks(self, content: str) -> list[ValidationWarning]:
        """Validate wikilinks in content (pre-write).

        - [[NonExistentNote]] → warning (forward reference allowed)
        - [[ExistingNote#NonExistentSection]] → raises BrokenLinkError
        """
        warnings: list[ValidationWarning] = []

        for match in _WIKILINK_WITH_SECTION_RE.finditer(content):
            note_name = match.group(1).strip()
            section = match.group(2)
            if section:
                section = section.strip()

            # Check if note exists
            try:
                self.vault.get_note(note_name)
            except NoteNotFoundError:
                # Forward reference allowed - just warning
                warnings.append(
                    ValidationWarning(
                        line=0,  # Line number not tracked for simplicity
                        message=f"Link to non-existent note: {note_name}",
                        rule="broken-link",
                    )
                )
                continue

            # If section specified, check it exists
            if section:
                headings = self.get_headings(note_name)
                heading_texts = [h.text for h in headings]
                if section not in heading_texts:
                    raise BrokenLinkError(
                        f"Section '{section}' not found in note '{note_name}'"
                    )

        return warnings

    # --- CRUD ---

    def create(
        self,
        name: str,
        content: str = "",
        frontmatter: dict[str, Any] | None = None,
    ) -> CreateResult:
        # Pre-write blocking validation
        self._validator.validate_name(name)
        self._validator.validate_headings(content)
        link_warnings = self._validate_wikilinks(content)

        path = self.vault.vault_path / f"{name}.md"
        if path.exists():
            raise NoteAlreadyExistsError(f"Note '{name}' already exists")
        file_content = self._serialize_note(frontmatter or {}, content)
        path.write_text(file_content, encoding="utf-8")
        self.vault.refresh()

        # Post-write validation (warnings)
        warnings = self._validator.validate(file_content)
        warnings.extend(link_warnings)
        return CreateResult(path=path, warnings=warnings)

    def read(self, name: str) -> str:
        path = self.vault.resolve_path(name)
        return path.read_text(encoding="utf-8")

    def append(self, name: str, text: str) -> WriteResult:
        path = self.vault.resolve_path(name)
        current = path.read_text(encoding="utf-8")
        new_content = current + "\n\n" + text

        # Pre-write blocking validation on full content
        self._validator.validate_headings(new_content)
        link_warnings = self._validate_wikilinks(new_content)

        path.write_text(new_content, encoding="utf-8")
        self.vault.refresh()

        # Post-write validation (warnings)
        warnings = self._validator.validate(new_content)
        warnings.extend(link_warnings)
        return WriteResult(warnings=warnings)

    def update(self, name: str, content: str) -> WriteResult:
        """Replace body of note, preserving frontmatter."""
        note = self.vault.get_note(name)
        fm = dict(note.frontmatter)
        file_content = self._serialize_note(fm, content)

        # Pre-write blocking validation
        self._validator.validate_headings(content)
        link_warnings = self._validate_wikilinks(content)

        note.path.write_text(file_content, encoding="utf-8")
        self.vault.refresh()

        # Post-write validation (warnings)
        warnings = self._validator.validate(file_content)
        warnings.extend(link_warnings)
        return WriteResult(warnings=warnings)

    def delete(self, name: str, dry_run: bool = False) -> DeleteResult:
        note = self.vault.get_note(name)
        trash_dir = self.vault.vault_path / ".trash"
        trash_path = trash_dir / f"{name}.md"

        files_updated = self._find_files_with_link(name)

        if not dry_run:
            for ref_name in files_updated:
                ref_note = self.vault.get_note(ref_name)
                self._update_links_in_file(ref_note.path, name, f"{name} (deleted)")
            trash_dir.mkdir(exist_ok=True)
            note.path.rename(trash_path)
            self.vault.refresh()

        return DeleteResult(
            name=name,
            trash_path=str(trash_path),
            files_updated=files_updated,
        )

    # --- Rename ---

    def rename(
        self, old_name: str, new_name: str, dry_run: bool = False
    ) -> RenameResult:
        self._validator.validate_name(new_name)
        old_note = self.vault.get_note(old_name)
        new_path = self.vault.vault_path / f"{new_name}.md"
        if new_path.exists():
            raise NoteAlreadyExistsError(f"Note '{new_name}' already exists")

        files_updated = self._find_files_with_link(old_name)

        if not dry_run:
            for ref_name in files_updated:
                ref_note = self.vault.get_note(ref_name)
                self._update_links_in_file(ref_note.path, old_name, new_name)
            old_note.path.rename(new_path)
            self.vault.refresh()

        return RenameResult(
            old_name=old_name,
            new_name=new_name,
            files_updated=files_updated,
        )

    # --- Frontmatter ---

    def frontmatter_get(self, name: str) -> dict[str, Any]:
        note = self.vault.get_note(name)
        return note.frontmatter

    def frontmatter_set(self, name: str, key: str, value: Any) -> None:
        note = self.vault.get_note(name)
        fm = dict(note.frontmatter)
        fm[key] = value
        file_content = self._serialize_note(fm, note.body)
        note.path.write_text(file_content, encoding="utf-8")
        self.vault.refresh()

    # --- Search ---

    def search(self, query: str, mode: SearchMode) -> list[SearchResult]:
        notes = self.vault.list_notes()
        results: list[SearchResult] = []

        for note in notes:
            match = False
            if mode == SearchMode.NAME:
                match = note.name == query
            elif mode == SearchMode.NAME_PARTIAL:
                match = query.lower() in note.name.lower()
            elif mode == SearchMode.CONTENT:
                match = query.lower() in note.body.lower()
            elif mode == SearchMode.TAG:
                match = any(
                    tag == query or tag.startswith(query + "/") for tag in note.tags
                )

            if match:
                results.append(SearchResult(name=note.name, path=str(note.path)))

        return results

    # --- Links ---

    def links(self, name: str, direction: LinkDirection) -> LinksResult:
        self.vault.get_note(name)  # validate exists

        outgoing: list[str] = []
        incoming: list[str] = []

        if direction in (LinkDirection.OUTGOING, LinkDirection.BOTH):
            outgoing = self.vault.get_outgoing_links(name)
        if direction in (LinkDirection.INCOMING, LinkDirection.BOTH):
            incoming = self.vault.get_incoming_links(name)

        return LinksResult(name=name, outgoing=outgoing, incoming=incoming)

    def find_broken_links(self) -> list[BrokenLink]:
        """Find all broken links in vault (links to non-existent notes)."""
        existing = {n.name for n in self.vault.list_notes()}
        broken: list[BrokenLink] = []
        for note in self.vault.list_notes():
            for target in self.vault.get_outgoing_links(note.name):
                if target not in existing:
                    broken.append(BrokenLink(source=note.name, target=target))
        return broken

    # --- Batch ---

    def batch_rename(
        self, renames: dict[str, str], dry_run: bool = False
    ) -> list[RenameResult]:
        results: list[RenameResult] = []
        for old_name, new_name in renames.items():
            result = self.rename(old_name, new_name, dry_run=dry_run)
            results.append(result)
        return results

    def batch_delete(
        self, names: list[str], dry_run: bool = False
    ) -> list[DeleteResult]:
        results: list[DeleteResult] = []
        for name in names:
            result = self.delete(name, dry_run=dry_run)
            results.append(result)
        return results

    # --- Text editing ---

    def replace(
        self,
        name: str,
        old_text: str,
        new_text: str,
        replace_all: bool = False,
    ) -> ReplaceResult:
        note = self.vault.get_note(name)
        body = note.body
        if old_text not in body:
            raise TextNotFoundError(f"Text '{old_text}' not found in note '{name}'")
        if replace_all:
            replacements = body.count(old_text)
            new_body = body.replace(old_text, new_text)
        else:
            replacements = 1
            new_body = body.replace(old_text, new_text, 1)
        fm = dict(note.frontmatter)
        file_content = self._serialize_note(fm, new_body)
        note.path.write_text(file_content, encoding="utf-8")
        self.vault.refresh()
        return ReplaceResult(name=name, replacements=replacements)

    def insert(
        self,
        name: str,
        text: str,
        *,
        before: str | None = None,
        after: str | None = None,
    ) -> InsertResult:
        if (before is None) == (after is None):
            raise ValueError("Exactly one of 'before' or 'after' must be specified")
        note = self.vault.get_note(name)
        body = note.body
        pattern = before if before is not None else after
        assert pattern is not None
        lines = body.split("\n")
        match_index: int | None = None
        for i, line in enumerate(lines):
            if line.strip() == pattern.strip():
                match_index = i
                break
        if match_index is None:
            raise TextNotFoundError(f"Pattern '{pattern}' not found in note '{name}'")
        if before is not None:
            lines.insert(match_index, text)
            position = "before"
        else:
            lines.insert(match_index + 1, text)
            position = "after"
        new_body = "\n".join(lines)
        fm = dict(note.frontmatter)
        file_content = self._serialize_note(fm, new_body)
        note.path.write_text(file_content, encoding="utf-8")
        self.vault.refresh()
        return InsertResult(name=name, position=position, pattern=pattern)

    def _find_section_bounds(
        self, lines: list[str], section: str, note_name: str
    ) -> tuple[int, int, int]:
        """Find section start, end, and heading level.

        Args:
            lines: Lines of note body
            section: Section heading (with or without # prefix)
            note_name: Note name for error messages

        Returns:
            Tuple of (start_line, end_line, heading_level)
        """
        section_stripped = section.strip()
        if section_stripped.startswith("#"):
            heading_level = len(section_stripped) - len(section_stripped.lstrip("#"))
            search_pattern = section_stripped
        else:
            heading_level = 0
            search_pattern = None
            search_re = re.compile(rf"^(#+)\s*{re.escape(section_stripped)}\s*$")

        start: int | None = None
        found_level: int = 0

        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if search_pattern is not None:
                if line_stripped == search_pattern:
                    start = i + 1
                    found_level = heading_level
                    break
            else:
                m = search_re.match(line_stripped)
                if m:
                    start = i + 1
                    found_level = len(m.group(1))
                    break

        if start is None:
            raise SectionNotFoundError(
                f"Section '{section}' not found in note '{note_name}'"
            )

        heading_re = re.compile(rf"^#{{1,{found_level}}}\s")
        end = len(lines)
        for i in range(start, len(lines)):
            if heading_re.match(lines[i]):
                end = i
                break

        return start, end, found_level

    def read_section(self, name: str, section: str) -> str:
        """Read section content. Section can be '## Heading' or plain 'Heading'."""
        note = self.vault.get_note(name)
        lines = note.body.split("\n")
        start, end, _ = self._find_section_bounds(lines, section, name)
        return "\n".join(lines[start:end]).strip()

    def append_section(self, name: str, section: str, text: str) -> WriteResult:
        """Append text to section. Section can be '## Heading' or plain 'Heading'."""
        note = self.vault.get_note(name)
        lines = note.body.split("\n")
        _, end, _ = self._find_section_bounds(lines, section, name)
        lines.insert(end, text)
        new_body = "\n".join(lines)
        fm = dict(note.frontmatter)
        file_content = self._serialize_note(fm, new_body)

        # Pre-write blocking validation on full content
        self._validator.validate_headings(new_body)
        link_warnings = self._validate_wikilinks(new_body)

        note.path.write_text(file_content, encoding="utf-8")
        self.vault.refresh()

        # Post-write validation (warnings)
        warnings = self._validator.validate(file_content)
        warnings.extend(link_warnings)
        return WriteResult(warnings=warnings)

    def get_headings(self, name: str) -> list[Heading]:
        """Get all headings from note body (ignores # inside code blocks)."""
        note = self.vault.get_note(name)
        lines = note.body.split("\n")
        headings: list[Heading] = []
        heading_re = re.compile(r"^(#+)\s+(.+)$")
        fence_re = re.compile(r"^(`{3,})")

        in_code_block = False
        current_fence_len = 0

        for line in lines:
            fence_match = fence_re.match(line)
            if fence_match:
                backticks = len(fence_match.group(1))
                if not in_code_block:
                    in_code_block = True
                    current_fence_len = backticks
                elif backticks >= current_fence_len:
                    in_code_block = False
                    current_fence_len = 0
                continue

            if in_code_block:
                continue

            m = heading_re.match(line)
            if m:
                headings.append(Heading(level=len(m.group(1)), text=m.group(2).strip()))
        return headings

    def update_section(self, name: str, section: str, content: str) -> WriteResult:
        """Replace section content (heading preserved)."""
        note = self.vault.get_note(name)
        lines = note.body.split("\n")
        start, end, level = self._find_section_bounds(lines, section, name)
        heading_line = lines[start - 1]
        new_lines = lines[: start - 1] + [heading_line, content] + lines[end:]
        new_body = "\n".join(new_lines)
        fm = dict(note.frontmatter)
        file_content = self._serialize_note(fm, new_body)

        # Pre-write blocking validation on full content
        self._validator.validate_headings(new_body)
        link_warnings = self._validate_wikilinks(new_body)

        note.path.write_text(file_content, encoding="utf-8")
        self.vault.refresh()

        # Post-write validation (warnings)
        warnings = self._validator.validate(file_content)
        warnings.extend(link_warnings)
        return WriteResult(warnings=warnings)

    def delete_section(self, name: str, section: str) -> None:
        """Delete section including its heading."""
        note = self.vault.get_note(name)
        lines = note.body.split("\n")
        start, end, _ = self._find_section_bounds(lines, section, name)
        new_lines = lines[: start - 1] + lines[end:]
        new_body = "\n".join(new_lines)
        fm = dict(note.frontmatter)
        file_content = self._serialize_note(fm, new_body)
        note.path.write_text(file_content, encoding="utf-8")
        self.vault.refresh()

    # --- Internal ---

    def _find_files_with_link(self, name: str) -> list[str]:
        return self.vault.get_incoming_links(name)

    @staticmethod
    def _update_links_in_file(path: Path, old_name: str, new_name: str) -> bool:
        content = path.read_text(encoding="utf-8")
        escaped_old = re.escape(old_name)
        pattern = rf"\[\[{escaped_old}([|#][^\]]*?)?\]\]"
        replacement = rf"[[{new_name}\1]]"
        new_content, count = re.subn(pattern, replacement, content)
        if count == 0:
            return False
        path.write_text(new_content, encoding="utf-8")
        return True

    @staticmethod
    def _serialize_note(frontmatter: dict[str, Any], body: str) -> str:
        if not frontmatter:
            return body
        yaml_str = yaml.dump(
            frontmatter,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        ).rstrip("\n")
        return f"---\n{yaml_str}\n---\n{body}"
