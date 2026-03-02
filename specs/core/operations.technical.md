# Operations

Narrative-Hash: 8e501445993b17fbbe404e47281ead88
Status: committed

## State

```python
class Operations:
    """All note operations. Stateless — uses Vault for data access."""

    vault: Vault
```

## Methods

```python
class Operations:
    def __init__(self, vault: Vault) -> None: ...

    # --- CRUD ---

    def create(
        self,
        name: str,
        content: str = "",
        frontmatter: dict[str, Any] | None = None,
    ) -> Path:
        """Create new note in vault root.
        Returns path to created file.
        Raises NoteAlreadyExistsError if name taken.
        Calls vault.refresh() after creation."""

    def read(self, name: str) -> str:
        """Return full content of note (frontmatter + body).
        Raises NoteNotFoundError."""

    def append(self, name: str, text: str) -> None:
        """Append text to end of note. Prepends \\n\\n before text.
        Raises NoteNotFoundError."""

    def update(self, name: str, content: str) -> None:
        """Replace body of note, preserving frontmatter.
        Reads current frontmatter, replaces body with content.
        Raises NoteNotFoundError.
        Calls vault.refresh() after update."""

    def delete(self, name: str, dry_run: bool = False) -> DeleteResult:
        """Delete note:
        1. Update all [[name]] → [[name (deleted)]] in live notes
        2. Move file to .trash/
        If dry_run: return what would be done without doing it.
        Raises NoteNotFoundError.
        Calls vault.refresh() after deletion."""

    # --- Rename ---

    def rename(self, old_name: str, new_name: str, dry_run: bool = False) -> RenameResult:
        """Rename note file and update all [[old_name]] → [[new_name]] in live notes.
        If dry_run: return what would be done without doing it.
        Raises NoteNotFoundError if old_name not found.
        Raises NoteAlreadyExistsError if new_name taken.
        Calls vault.refresh() after rename."""

    # --- Frontmatter ---

    def frontmatter_get(self, name: str) -> dict[str, Any]:
        """Return frontmatter of note as dict.
        Raises NoteNotFoundError."""

    def frontmatter_set(self, name: str, key: str, value: Any) -> None:
        """Set top-level frontmatter key. Preserve body.
        Raises NoteNotFoundError."""

    # --- Search ---

    def search(self, query: str, mode: SearchMode) -> list[SearchResult]:
        """Search notes. Returns list with full paths.
        Modes: name, name_partial, content, tag."""

    # --- Links ---

    def links(self, name: str, direction: LinkDirection) -> LinksResult:
        """Get linked notes.
        Raises NoteNotFoundError."""

    # --- Batch ---

    def batch_rename(self, renames: dict[str, str], dry_run: bool = False) -> list[RenameResult]:
        """Batch rename from dict {old_name: new_name}.
        Executes sequentially. Stops on first error."""

    def batch_delete(self, names: list[str], dry_run: bool = False) -> list[DeleteResult]:
        """Batch delete from list of names.
        Executes sequentially. Stops on first error."""

    # --- Text editing ---

    def replace(
        self,
        name: str,
        old_text: str,
        new_text: str,
        replace_all: bool = False,
    ) -> ReplaceResult:
        """Replace text in note body only (frontmatter untouched).
        Replaces first occurrence, or all if replace_all=True.
        Raises NoteNotFoundError if note not found.
        Raises TextNotFoundError if old_text not found in body.
        Calls vault.refresh() after modification."""

    def insert(
        self,
        name: str,
        text: str,
        *,
        before: str | None = None,
        after: str | None = None,
    ) -> InsertResult:
        """Insert text before or after a pattern in note body.
        Exactly one of before/after must be specified.
        Pattern matching: exact line match (stripped whitespace).
        Inserts at first occurrence.
        Raises NoteNotFoundError if note not found.
        Raises TextNotFoundError if pattern not found in body.
        Raises ValueError if both or neither before/after specified.
        Calls vault.refresh() after modification."""

    def read_section(self, name: str, section: str) -> str:
        """Return content of a markdown section (without the heading itself).
        Section identified by heading (e.g. '## Budget').
        Content spans from heading to next heading of same or higher level, or EOF.
        Subheadings (### and below) are part of the section.
        Raises NoteNotFoundError if note not found.
        Raises SectionNotFoundError if section heading not found."""

    def append_section(self, name: str, section: str, text: str) -> None:
        """Append text to end of a markdown section.
        Inserts text before the next heading of same or higher level, or at EOF.
        Raises NoteNotFoundError if note not found.
        Raises SectionNotFoundError if section heading not found.
        Calls vault.refresh() after modification."""

    # --- Internal ---

    @staticmethod
    def _update_links_in_file(path: Path, old_name: str, new_name: str) -> bool:
        """Replace all [[old_name]] with [[new_name]] in file.
        Returns True if file was modified."""

    @staticmethod
    def _serialize_note(frontmatter: dict[str, Any], body: str) -> str:
        """Serialize frontmatter + body back to .md file content."""
```

## Types

```python
from enum import Enum

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
    path: str  # full path as string

@dataclass(slots=True)
class RenameResult:
    old_name: str
    new_name: str
    files_updated: list[str]  # names of notes where links were updated

@dataclass(slots=True)
class DeleteResult:
    name: str
    trash_path: str
    files_updated: list[str]  # names where [[name]] → [[name (deleted)]]

@dataclass(slots=True)
class LinksResult:
    name: str
    outgoing: list[str]
    incoming: list[str]

@dataclass(slots=True)
class ReplaceResult:
    name: str
    replacements: int  # number of replacements made

@dataclass(slots=True)
class InsertResult:
    name: str
    position: str  # "before" or "after"
    pattern: str  # the pattern matched
```

## Errors

```python
class NoteAlreadyExistsError(VaultError): ...
class TextNotFoundError(VaultError): ...
class SectionNotFoundError(VaultError): ...
```

## Invariants

1. All mutations (create, delete, rename, append, update, frontmatter_set) call `vault.refresh()` after modifying files
2. `_update_links_in_file` uses exact `[[old_name]]` matching — no partial matches
3. Delete always does TWO things: update links + move to trash. In that order.
4. Delete renames links to `[[name (deleted)]]` — space before parenthesis, no trailing space
5. `.trash/` directory is created if it doesn't exist
6. Append always prepends `\n\n` — even if note is empty (results in leading newlines, acceptable)
7. `_serialize_note`: if frontmatter is empty dict or None, don't write `---` delimiters — output body only
8. `frontmatter_set` preserves all other keys and body unchanged
9. Batch operations execute sequentially, stop on first error, return results of completed operations
10. Search mode `name` is case-sensitive exact match; `name_partial` and `content` are case-insensitive
11. Search mode `tag` is hierarchical: query="vc" matches tags "vc" AND "vc/project" (tag == query OR tag.startswith(query + "/"))
12. `replace` and `insert` operate on body only — frontmatter is parsed, preserved, and re-serialized unchanged
13. `replace` with `replace_all=False` replaces first occurrence only; `replace_all=True` replaces all
14. `insert` pattern matching: exact match of trimmed line (line.strip() == pattern.strip())
15. `insert` requires exactly one of `before`/`after` — both or neither raises ValueError
16. Section boundary: heading of same or higher level (fewer or equal `#`). `### Details` inside `## Budget` is part of Budget section
17. `read_section` returns content after heading line, without the heading itself
18. `append_section` inserts text before the next section boundary (or EOF), with `\n` prefix if section has existing content
19. `replace`, `insert`, `append_section` all call `vault.refresh()` after modification
20. For notes without frontmatter: entire file content is treated as body
21. `update` on note without frontmatter: writes new content as body only, no frontmatter created

## Formulas

```
link_replacement_pattern = f"[[{old_name}]]" → f"[[{new_name}]]"
delete_link_pattern = f"[[{name}]]" → f"[[{name} (deleted)]]"
trash_path = vault_path / ".trash" / f"{name}.md"
new_note_path = vault_path / f"{name}.md"

# replace
new_body = body.replace(old_text, new_text, 1)       # replace_all=False
new_body = body.replace(old_text, new_text)           # replace_all=True
replacements = body.count(old_text) if replace_all else (1 if old_text in body else 0)

# insert — line-based matching
lines = body.split("\n")
match_index = next(i for i, line in enumerate(lines) if line.strip() == pattern.strip())
# before: lines.insert(match_index, text)
# after: lines.insert(match_index + 1, text)

# section boundary
heading_level = len(section) - len(section.lstrip("#"))
# section ends at next line matching: re.match(r'^(#{1,<heading_level>})\s', line)
# or EOF

# read_section: body from (heading_line + 1) to section_end, strip leading/trailing blank lines
# append_section: insert text at section_end position
```

## Test Cases

### TC1: create basic
GIVEN: empty vault
WHEN: create("test", content="Hello")
THEN: file vault/test.md exists, content = "Hello"

### TC2: create with frontmatter
GIVEN: empty vault
WHEN: create("test", frontmatter={"tags": ["vc"]}, content="Body")
THEN: file content starts with "---\ntags:\n- vc\n---\n", followed by "Body"

### TC3: create duplicate
GIVEN: vault with note "test"
WHEN: create("test")
THEN: raises NoteAlreadyExistsError

### TC4: read
GIVEN: vault with note "test" containing "---\ntags: [a]\n---\nBody"
WHEN: read("test")
THEN: returns "---\ntags: [a]\n---\nBody"

### TC5: read not found
GIVEN: empty vault
WHEN: read("nonexistent")
THEN: raises NoteNotFoundError

### TC6: append
GIVEN: vault with note "test" containing "Line1"
WHEN: append("test", "Line2")
THEN: file content = "Line1\n\nLine2"

### TC7: delete with link update
GIVEN: vault with notes A (contains [[B]]) and B
WHEN: delete("B")
THEN: A now contains [[B (deleted)]], B.md moved to .trash/B.md

### TC8: delete dry run
GIVEN: vault with notes A (contains [[B]]) and B
WHEN: delete("B", dry_run=True)
THEN: returns DeleteResult with files_updated=["A"], but no files changed

### TC9: rename with link update
GIVEN: vault with notes A (contains [[B]]) and B
WHEN: rename("B", "B_new")
THEN: B.md renamed to B_new.md, A now contains [[B_new]]

### TC10: rename dry run
GIVEN: vault with notes A (contains [[B]]) and B
WHEN: rename("B", "B_new", dry_run=True)
THEN: returns RenameResult, but no files changed

### TC11: rename to existing name
GIVEN: vault with notes A and B
WHEN: rename("A", "B")
THEN: raises NoteAlreadyExistsError

### TC12: frontmatter_get
GIVEN: vault with note "test" with frontmatter {"tags": ["a"], "status": "draft"}
WHEN: frontmatter_get("test")
THEN: returns {"tags": ["a"], "status": "draft"}

### TC13: frontmatter_set
GIVEN: vault with note "test" with frontmatter {"tags": ["a"]} and body "Hello"
WHEN: frontmatter_set("test", "status", "done")
THEN: frontmatter now {"tags": ["a"], "status": "done"}, body still "Hello"

### TC14: search by name exact
GIVEN: vault with notes ["alpha", "beta", "alpha_2"]
WHEN: search("alpha", mode=NAME)
THEN: returns [SearchResult(name="alpha", path=...)]

### TC15: search by name partial
GIVEN: vault with notes ["alpha", "beta", "alpha_2"]
WHEN: search("alph", mode=NAME_PARTIAL)
THEN: returns [SearchResult(name="alpha",...), SearchResult(name="alpha_2",...)]

### TC16: search by content
GIVEN: vault with note "test" body "Hello World"
WHEN: search("hello", mode=CONTENT)
THEN: returns [SearchResult(name="test",...)] (case-insensitive)

### TC17: search by tag
GIVEN: vault with note "test" tags=["vc", "vc/project"]
WHEN: search("vc", mode=TAG)
THEN: returns [SearchResult(name="test",...)]

### TC18: search by tag hierarchical
GIVEN: vault with note "test" tags=["vc/project"]
WHEN: search("vc", mode=TAG)
THEN: returns [SearchResult(name="test",...)] (hierarchical: "vc" matches "vc/project")

### TC19: links outgoing
GIVEN: vault with note A containing [[B]] and [[C]]
WHEN: links("A", direction=OUTGOING)
THEN: LinksResult(outgoing=["B", "C"], incoming=[])

### TC20: links incoming
GIVEN: vault with notes A→B, C→B
WHEN: links("B", direction=INCOMING)
THEN: LinksResult(outgoing=[], incoming=["A", "C"])

### TC21: links both
GIVEN: vault with A→B, C→A
WHEN: links("A", direction=BOTH)
THEN: LinksResult(outgoing=["B"], incoming=["C"])

### TC22: batch rename
GIVEN: vault with notes A, B, C. C contains [[A]] and [[B]]
WHEN: batch_rename({"A": "A_new", "B": "B_new"})
THEN: files renamed, C now contains [[A_new]] and [[B_new]]

### TC23: batch delete
GIVEN: vault with notes A, B, C. C contains [[A]] and [[B]]
WHEN: batch_delete(["A", "B"])
THEN: A, B in .trash/. C contains [[A (deleted)]] and [[B (deleted)]]

### TC24: update body preserving frontmatter
GIVEN: vault with note "test" with frontmatter {"tags": ["a"]} and body "Old body"
WHEN: update("test", "New body")
THEN: frontmatter still {"tags": ["a"]}, body is "New body"

### TC25: update not found
GIVEN: empty vault
WHEN: update("nonexistent", "content")
THEN: raises NoteNotFoundError

### TC26: replace first occurrence
GIVEN: vault with note "test" with frontmatter {"tags": ["a"]} and body "foo bar foo"
WHEN: replace("test", "foo", "baz")
THEN: body = "baz bar foo", frontmatter unchanged, ReplaceResult(replacements=1)

### TC27: replace all occurrences
GIVEN: vault with note "test" body "foo bar foo"
WHEN: replace("test", "foo", "baz", replace_all=True)
THEN: body = "baz bar baz", ReplaceResult(replacements=2)

### TC28: replace text not found
GIVEN: vault with note "test" body "Hello"
WHEN: replace("test", "xyz", "abc")
THEN: raises TextNotFoundError

### TC29: replace ignores frontmatter
GIVEN: vault with note "test" with frontmatter {"status": "draft"} and body "status: active"
WHEN: replace("test", "status: draft", "status: done")
THEN: raises TextNotFoundError (text is in frontmatter, not in body)

### TC30: insert after pattern
GIVEN: vault with note "test" body "## Header\nContent\n## Footer"
WHEN: insert("test", "New line", after="## Header")
THEN: body = "## Header\nNew line\nContent\n## Footer"

### TC31: insert before pattern
GIVEN: vault with note "test" body "Line1\nLine2\nLine3"
WHEN: insert("test", "Inserted", before="Line2")
THEN: body = "Line1\nInserted\nLine2\nLine3"

### TC32: insert pattern not found
GIVEN: vault with note "test" body "Hello"
WHEN: insert("test", "text", after="## Missing")
THEN: raises TextNotFoundError

### TC33: insert both before and after
GIVEN: vault with note "test"
WHEN: insert("test", "text", before="A", after="B")
THEN: raises ValueError

### TC34: insert neither before nor after
GIVEN: vault with note "test"
WHEN: insert("test", "text")
THEN: raises ValueError

### TC35: read_section basic
GIVEN: vault with note "test" body "## Budget\nAmount: 100\n## Timeline\nQ1 2024"
WHEN: read_section("test", "## Budget")
THEN: returns "Amount: 100"

### TC36: read_section with subsections
GIVEN: vault with note "test" body "## Budget\nTotal: 500\n### Details\nItem: 100\n## Other"
WHEN: read_section("test", "## Budget")
THEN: returns "Total: 500\n### Details\nItem: 100"

### TC37: read_section until EOF
GIVEN: vault with note "test" body "## Budget\nAmount: 100"
WHEN: read_section("test", "## Budget")
THEN: returns "Amount: 100"

### TC38: read_section not found
GIVEN: vault with note "test" body "## Budget\nContent"
WHEN: read_section("test", "## Missing")
THEN: raises SectionNotFoundError

### TC39: append_section basic
GIVEN: vault with note "test" body "## Questions\n- Q1\n## Done"
WHEN: append_section("test", "## Questions", "- Q2")
THEN: body = "## Questions\n- Q1\n- Q2\n## Done"

### TC40: append_section at EOF
GIVEN: vault with note "test" body "## Questions\n- Q1"
WHEN: append_section("test", "## Questions", "- Q2")
THEN: body = "## Questions\n- Q1\n- Q2"

### TC41: append_section not found
GIVEN: vault with note "test" body "## Budget"
WHEN: append_section("test", "## Missing", "text")
THEN: raises SectionNotFoundError

### TC42: replace in note without frontmatter
GIVEN: vault with note "test" (no frontmatter) body "Hello World"
WHEN: replace("test", "Hello", "Hi")
THEN: body = "Hi World", no frontmatter added
