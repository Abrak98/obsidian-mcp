# Validation

Narrative-Hash: 42346687a1f7eadb9a57b9c3190c9475
Status: draft

## Types

```python
@dataclass(slots=True)
class ValidationWarning:
    line: int
    message: str
    rule: str  # "table-blank-line" | "unclosed-code-block" | "broken-link"


class InvalidNameError(VaultError):
    """Raised when note name contains invalid characters (Cyrillic, etc)."""
    pass


class InvalidHeadingError(VaultError):
    """Raised when heading contains Cyrillic characters."""
    pass


class BrokenLinkError(VaultError):
    """Raised when wikilink points to non-existent note or section."""
    pass
```

## State

```python
class Validator:
    """Stateless markdown validator."""
    pass
```

## Methods

```python
def validate(content: str) -> list[ValidationWarning]:
    """Validate markdown content (post-write).

    Checks:
    - Tables must have blank line before them (if preceded by text)
    - Fenced code blocks must be closed (paired ```)

    Returns list of warnings (empty if valid).
    """


def validate_name(name: str) -> None:
    """Validate note name (pre-write, blocking).

    Raises InvalidNameError if name contains Cyrillic characters.
    Allowed: a-zA-Z, 0-9, spaces, underscore, hyphen, @, Obsidian Tasks emojis.
    """


def validate_headings(content: str) -> None:
    """Validate headings are English only (pre-write, blocking).

    Raises InvalidHeadingError if any heading contains Cyrillic.
    Skips headings inside code blocks.
    """


# In Operations class:
def _validate_wikilinks(self, content: str) -> list[ValidationWarning]:
    """Validate wikilinks in content (pre-write).

    - [[NonExistentNote]] → warning (forward reference allowed)
    - [[ExistingNote#NonExistentSection]] → raises BrokenLinkError

    Returns warnings for non-existent notes.
    Raises BrokenLinkError for broken section links.
    """
```

## Invariants

1. **Table blank line**: If a GFM table exists and has non-blank content above it, there must be at least one blank line between that content and the table.

2. **Fenced code block closure**: Every opening ``` must have a matching closing ```.

3. **Post-write validation**: Tables and code blocks checked after write, return warnings.

4. **Note name English only**: Note names must contain only: a-zA-Z, 0-9, spaces, underscore, hyphen, @ (for Person notes), and Obsidian Tasks emojis (➕⏳🛫📅✅❌⏬🔽🔼⏫🔺🔁🏁🆔⛔). Cyrillic characters are forbidden.

5. **Heading English only**: Heading text (after # symbols) must not contain Cyrillic. Blocking error.

6. **Pre-write blocking**: Name, headings, and section links validated before write. Raises exception on error.

7. **Forward references allowed**: `[[NonExistentNote]]` returns warning, not error (allows creating links to future notes).

8. **Broken section links blocked**: `[[ExistingNote#NonExistentSection]]` raises BrokenLinkError (explicit error, note exists but section doesn't).

## Formulas

### Code block detection (must run first)

```
FENCE = line starts with ``` (3+ backticks at line start, not inline)
FENCE_LENGTH = number of backticks in opening fence

Parse fences as stack:
  for each line:
    if line matches r"^(`{3,})":
      backtick_count = len(match.group(1))
      if not in_code_block:
        push (line_num, backtick_count) to stack
        in_code_block = True
        current_fence_length = backtick_count
      else:
        if backtick_count >= current_fence_length:
          pop from stack
          in_code_block = False

After parsing:
  if stack not empty:
    for each (line_num, _) in stack:
      WARNING("unclosed-code-block", line=line_num)

  code_block_ranges = list of (start, end) for closed blocks
```

### Table detection (skip lines inside code blocks)

```
TABLE_LINE = line matches r"^\|.*\|$" AND line not inside code_block_ranges
TABLE_SEPARATOR = line matches r"^\|[-:| ]+\|$"
TABLE_START = TABLE_LINE at position i AND TABLE_SEPARATOR at position i+1
```

### Table blank line check

```
For each TABLE_START at line i (1-indexed):
  if i > 1 AND line[i-1] is not blank:
    WARNING("table-blank-line", line=i)
```

### Note name validation

```
TASKS_EMOJIS = "➕⏳🛫📅✅❌⏬🔽🔼⏫🔺🔁🏁🆔⛔"
ALLOWED_PATTERN = r"^[a-zA-Z0-9 _@-" + TASKS_EMOJIS + r"]+$"
CYRILLIC_PATTERN = r"[\u0400-\u04FF]"

def validate_name(name: str):
  if re.search(CYRILLIC_PATTERN, name):
    raise InvalidNameError(f"Note name contains Cyrillic: {name}")
  if not re.match(ALLOWED_PATTERN, name):
    raise InvalidNameError(f"Note name contains invalid characters: {name}")
```

### Heading validation (skip code blocks, blocking)

```
HEADING_RE = r"^(#+)\s+(.+)$"
CYRILLIC_PATTERN = r"[\u0400-\u04FF]"

For each line not inside code_block_ranges:
  if line matches HEADING_RE:
    heading_text = match.group(2)
    if re.search(CYRILLIC_PATTERN, heading_text):
      raise InvalidHeadingError(f"Heading contains Cyrillic at line {line_num}: {heading_text}")
```

### Wikilinks validation (in Operations)

```
WIKILINK_RE = r"\[\[([^\]]+)\]\]"

def _validate_wikilinks(content: str) -> list[ValidationWarning]:
  warnings = []
  for match in re.finditer(WIKILINK_RE, content):
    link = match.group(1)
    if "#" in link:
      note_name, section = link.split("#", 1)
    else:
      note_name, section = link, None

    # Check note exists
    try:
      note = vault.get_note(note_name)
    except NoteNotFoundError:
      warnings.append(ValidationWarning(line=..., message=f"Link to non-existent note: {note_name}", rule="broken-link"))
      continue

    # If section specified, check it exists
    if section:
      headings = get_headings(note_name)
      heading_texts = [h["text"] for h in headings]
      if section not in heading_texts:
        raise BrokenLinkError(f"Section '{section}' not found in note '{note_name}'")

  return warnings
```

## Integration

Operations that validate BEFORE write (blocking):

- `create()` → validate_name(name), validate_headings(content), _validate_wikilinks(content)
- `update()` → validate_headings(content), _validate_wikilinks(content)
- `append()` → validate_headings(full_content), _validate_wikilinks(full_content)
- `append_section()` → validate_headings(full_content), _validate_wikilinks(full_content)
- `update_section()` → validate_headings(full_content), _validate_wikilinks(full_content)
- `rename()` → validate_name(new_name)

Operations that validate AFTER write (warnings):

- All write operations → validate(full_content) for tables/code blocks

Return type modification:
```python
# Before
def create(...) -> Path

# After
@dataclass
class WriteResult:
    path: Path  # or other result type
    warnings: list[ValidationWarning]

def create(...) -> WriteResult
```

## Test Cases

### TC1: Valid markdown - no warnings
```
GIVEN: content = "# Title\n\nSome text.\n\n| A | B |\n|---|---|\n| 1 | 2 |"
WHEN: validate(content)
THEN: result == []
```

### TC2: Table without blank line before
```
GIVEN: content = "Some text\n| A | B |\n|---|---|\n| 1 | 2 |"
WHEN: validate(content)
THEN: len(result) == 1
  AND result[0].rule == "table-blank-line"
  AND result[0].line == 2
```

### TC3: Unclosed code block
```
GIVEN: content = "# Title\n\n```python\ncode here"
WHEN: validate(content)
THEN: len(result) == 1
  AND result[0].rule == "unclosed-code-block"
  AND result[0].line == 3
```

### TC4: Multiple issues
```
GIVEN: content = "text\n| A |\n|---|\n```\ncode"
WHEN: validate(content)
THEN: len(result) == 2
  AND any(w.rule == "table-blank-line" for w in result)
  AND any(w.rule == "unclosed-code-block" for w in result)
```

### TC5: Table at document start - valid
```
GIVEN: content = "| A | B |\n|---|---|\n| 1 | 2 |"
WHEN: validate(content)
THEN: result == []
```

### TC6: Closed code block - valid
```
GIVEN: content = "```python\ncode\n```"
WHEN: validate(content)
THEN: result == []
```

### TC7: Multiple code blocks all closed
```
GIVEN: content = "```\na\n```\n\n```\nb\n```"
WHEN: validate(content)
THEN: result == []
```

### TC8: Table after blank line - valid

```
GIVEN: content = "text\n\n| A |\n|---|"
WHEN: validate(content)
THEN: result == []
```

### TC9: Table inside closed code block - ignored

```
GIVEN: content = "```\n| A |\n|---|\n```"
WHEN: validate(content)
THEN: result == []
```

### TC10: Nested code blocks with 4 backticks

````text
GIVEN: content = "````\n```\nnested\n```\n````"
WHEN: validate(content)
THEN: result == []
````

### TC11: Inner fence inside outer block is text, not fence

````text
GIVEN: content = "````\n```\nnested\n````"
WHEN: validate(content)
THEN: result == []
````

Updated: Inner ``` is content inside ```` block, not a fence (CommonMark spec).

### TC12: Inline backticks not treated as fence

```
GIVEN: content = "Use `code` inline and ```also``` triple"
WHEN: validate(content)
THEN: result == []
```

---

## Name Validation Test Cases

### TC13: Valid English name

```
GIVEN: name = "My Project 2024"
WHEN: validate_name(name)
THEN: no exception
```

### TC14: Name with Cyrillic - error

```
GIVEN: name = "Мой проект"
WHEN: validate_name(name)
THEN: raises InvalidNameError
```

### TC15: Name with Tasks emoji - valid

```
GIVEN: name = "Task 📅 deadline"
WHEN: validate_name(name)
THEN: no exception
```

### TC16: Name with mixed valid chars

```
GIVEN: name = "Project 123 ⏫ high"
WHEN: validate_name(name)
THEN: no exception
```

### TC17: Name with invalid punctuation - error

```
GIVEN: name = "Project: Test"
WHEN: validate_name(name)
THEN: raises InvalidNameError
```

---

## Heading Validation Test Cases

### TC18: English heading - valid

```text
GIVEN: content = "# My Title\n\nText"
WHEN: validate_headings(content)
THEN: no exception
```

### TC19: Cyrillic heading - blocking error

```text
GIVEN: content = "# Заголовок\n\nText"
WHEN: validate_headings(content)
THEN: raises InvalidHeadingError
```

### TC20: Cyrillic heading inside code block - ignored

```text
GIVEN: content = "```\n# Заголовок\n```"
WHEN: validate_headings(content)
THEN: no exception
```

### TC21: Multiple headings, one Cyrillic - error on first

```text
GIVEN: content = "# Title\n\n## Секция\n\n### Footer"
WHEN: validate_headings(content)
THEN: raises InvalidHeadingError (line 3)
```

---

## Wikilinks Validation Test Cases

### TC22: Valid wikilink to existing note

```text
GIVEN: vault with note "Target"
  AND content = "Link to [[Target]]"
WHEN: _validate_wikilinks(content)
THEN: warnings == []
```

### TC23: Wikilink to non-existent note - warning

```text
GIVEN: vault without note "Missing"
  AND content = "Link to [[Missing]]"
WHEN: _validate_wikilinks(content)
THEN: len(warnings) == 1
  AND warnings[0].rule == "broken-link"
```

### TC24: Valid wikilink with section

```text
GIVEN: vault with note "Target" containing "# Section"
  AND content = "Link to [[Target#Section]]"
WHEN: _validate_wikilinks(content)
THEN: warnings == []
```

### TC25: Wikilink with non-existent section - blocking error

```text
GIVEN: vault with note "Target" (no section "Missing")
  AND content = "Link to [[Target#Missing]]"
WHEN: _validate_wikilinks(content)
THEN: raises BrokenLinkError
```

### TC26: Multiple wikilinks, one broken section

```text
GIVEN: vault with notes "A" (has "# Intro"), "B" (no "# Nope")
  AND content = "[[A#Intro]] and [[B#Nope]]"
WHEN: _validate_wikilinks(content)
THEN: raises BrokenLinkError for B#Nope
```
