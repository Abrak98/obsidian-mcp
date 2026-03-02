# Vault

Narrative-Hash: 5e7bf56409e6cd3455dae39bf534fc17
Status: committed

## State

```python
class Note:
    """Parsed note representation."""
    __slots__ = ("name", "path", "frontmatter", "body", "outgoing_links", "tags")

    name: str                    # имя без .md
    path: Path                   # полный путь к файлу
    frontmatter: dict[str, Any]  # parsed YAML frontmatter
    body: str                    # markdown body без frontmatter
    outgoing_links: list[str]    # список имён из [[wikilinks]]
    tags: list[str]              # теги из frontmatter["tags"]


class Vault:
    """Obsidian vault access layer."""

    vault_path: Path                        # корень vault
    _notes: dict[str, Note] | None          # name → Note, lazy init
    _incoming_links: dict[str, list[str]] | None  # name → [who links to it]
```

## Methods

```python
class Vault:
    def __init__(self, vault_path: Path) -> None:
        """Validate vault_path exists and is directory."""

    @staticmethod
    def from_env(vault_path_override: str | None = None) -> "Vault":
        """Create Vault from --vault-path flag or OBSIDIAN_VAULT_PATH env var.
        Priority: vault_path_override > env var.
        Raises VaultNotConfiguredError if neither set."""

    def list_notes(self) -> list[Note]:
        """Return all notes in vault. Builds index if not built."""

    def get_note(self, name: str) -> Note:
        """Get note by name (without .md).
        On cache miss: rescan vault and retry once.
        Raises NoteNotFoundError only after rescan fails."""

    def resolve_path(self, name: str) -> Path:
        """Resolve note name to full path. Raises NoteNotFoundError."""

    def get_incoming_links(self, name: str) -> list[str]:
        """Return names of notes that link to `name`."""

    def get_outgoing_links(self, name: str) -> list[str]:
        """Return names of notes that `name` links to."""

    def refresh(self) -> None:
        """Force rebuild of index (after mutations)."""

    def _build_index(self) -> None:
        """Scan vault, parse all notes, build link graph."""

    @staticmethod
    def _scan_files(vault_path: Path) -> list[Path]:
        """List all .md files in vault root. Skip dot-directories."""

    @staticmethod
    def _parse_note(path: Path) -> Note:
        """Parse single .md file: frontmatter + body + wikilinks + tags."""

    @staticmethod
    def _extract_wikilinks(body: str) -> list[str]:
        """Extract [[note]] links from body. Only [[name]] format."""

    @staticmethod
    def _extract_tags(frontmatter: dict[str, Any]) -> list[str]:
        """Extract tags from frontmatter['tags']. Return [] if missing."""
```

## Errors

```python
class VaultError(Exception): ...
class VaultNotConfiguredError(VaultError): ...
class NoteNotFoundError(VaultError): ...
```

## Invariants

1. `_notes` dict keys == note names (без .md, case-sensitive)
2. Vault path MUST exist and be a directory — validated in `__init__`
3. Index is lazy: built on first access to `list_notes()`, `get_note()`, etc.
4. After any mutation (create/delete/rename), caller must call `refresh()` to rebuild index
5. `_scan_files` returns only `.md` files directly in vault root (flat structure)
6. `_scan_files` skips all directories starting with `.` (`.obsidian/`, `.trash/`, etc.)
7. Wikilink regex: `\[\[([^\]|#]+)\]\]` — captures only the note name part of `[[name]]`
8. Tags are always `list[str]`, even if frontmatter has single string tag
9. `from_env` raises `VaultNotConfiguredError` with instructions if path not set
10. `get_note` on cache miss: rescan vault once, then retry lookup. NoteNotFoundError only after rescan

## Formulas

```
wikilink_pattern = r'\[\[([^\]|#]+)\]\]'
incoming_links[target] = [note.name for note in all_notes if target in note.outgoing_links]
```

## Test Cases

### TC1: from_env with override
GIVEN: vault_path_override="/some/path" and directory exists
WHEN: Vault.from_env(vault_path_override="/some/path")
THEN: vault.vault_path == Path("/some/path")

### TC2: from_env with env var
GIVEN: OBSIDIAN_VAULT_PATH="/some/path" in env, no override
WHEN: Vault.from_env()
THEN: vault.vault_path == Path("/some/path")

### TC3: from_env without config
GIVEN: no env var, no override
WHEN: Vault.from_env()
THEN: raises VaultNotConfiguredError

### TC4: scan files flat
GIVEN: vault with files ["a.md", "b.md", ".obsidian/config", ".trash/old.md"]
WHEN: _scan_files(vault_path)
THEN: returns [vault_path/"a.md", vault_path/"b.md"]

### TC5: parse note with frontmatter
GIVEN: file content "---\ntags: [vc, vc/project]\n---\n# Title\nBody with [[link1]] and [[link2]]"
WHEN: _parse_note(path)
THEN: note.frontmatter == {"tags": ["vc", "vc/project"]}, note.outgoing_links == ["link1", "link2"], note.tags == ["vc", "vc/project"]

### TC6: parse note without frontmatter
GIVEN: file content "# Title\nJust body"
WHEN: _parse_note(path)
THEN: note.frontmatter == {}, note.tags == [], note.body == "# Title\nJust body"

### TC7: extract wikilinks
GIVEN: body = "See [[note1]] and [[note2]] for details"
WHEN: _extract_wikilinks(body)
THEN: ["note1", "note2"]

### TC8: get_note not found
GIVEN: vault with notes ["a", "b"]
WHEN: get_note("c")
THEN: raises NoteNotFoundError

### TC9: incoming links
GIVEN: vault with note A linking to B, note C linking to B
WHEN: get_incoming_links("B")
THEN: returns ["A", "C"] (order not guaranteed)

### TC10: outgoing links
GIVEN: vault with note A containing [[B]] and [[C]]
WHEN: get_outgoing_links("A")
THEN: returns ["B", "C"]

### TC11: refresh rebuilds index
GIVEN: vault with note A, index built
WHEN: new file B.md created externally, then refresh()
THEN: get_note("B") succeeds

### TC12: get_note cache miss triggers rescan

GIVEN: vault with note A, index built (B not in index)
WHEN: new file B.md created externally, then get_note("B") WITHOUT explicit refresh()
THEN: get_note("B") succeeds (automatic rescan on cache miss)

### TC13: get_note still raises after rescan if note missing

GIVEN: vault with note A, index built
WHEN: get_note("nonexistent") (no such file on disk)
THEN: raises NoteNotFoundError (rescan happened but note still not found)
