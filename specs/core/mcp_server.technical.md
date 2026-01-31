# MCP Server

Narrative-Hash: de0f5989ab302a74fb7ca5b86ca4cf91
Status: committed

## State

```python
from mcp.server.fastmcp import FastMCP
from obsidian_mcp.vault import Vault
from obsidian_mcp.operations import Operations

_AUTOCONTEXT_TAG = "claude"
_MISSING_DESCRIPTION = (
    "⚠️ No description. Claude, please add a 'description' field "
    "to this note's frontmatter explaining when to read it."
)

# Mutable state per server instance (set in _create_server, shared via closure)
_context_injected: bool  # False at start, True after first tool call
_context_block: str      # Pre-built context string (auto-context + tag policy)
```

## Startup

```python
def main() -> None:
    """Entry point (obs-mcp). Reads OBSIDIAN_VAULT_PATH from env.
    Creates Vault once. Passes it to _create_server.
    No global singleton — explicit dependency passing.
    If OBSIDIAN_VAULT_PATH not set — exits with error."""

def _create_server(vault_path_str: str) -> FastMCP:
    """Create Vault, build instructions (base only), build context block
    (auto-context + tag policy), create FastMCP, create Operations,
    register tools with ops and context injection passed explicitly.
    Sets _context_injected = False, _context_block = pre-built string."""

def _build_instructions() -> str:
    """Return _BASE_INSTRUCTIONS only. No vault-specific content.
    No CLAUDE.md — vault rules are regular notes with tag 'claude'."""

def _build_context_block(vault: Vault) -> str:
    """Build context block for injection into first tool result.
    Combines auto-context + tag policy. Called once at startup, cached.
    Returns empty string if no auto-context and no tags (nothing to inject)."""

def _build_autocontext(vault: Vault) -> str:
    """Build auto-context section from notes with tag 'claude'.
    Iterates vault.list_notes(), filters by _AUTOCONTEXT_TAG in note.tags.
    Returns formatted section with note names + descriptions.
    If no notes found — returns section with hint about creating notes.
    If note has no 'description' in frontmatter — uses _MISSING_DESCRIPTION."""

def _build_tag_policy(vault: Vault) -> str:
    """Build tag policy section from all unique tags in vault.
    Iterates vault.list_notes(), collects all unique tags across all notes.
    Returns formatted section with sorted tag list and strict prohibition.
    If no tags found — returns section with hint."""

def _inject_context(result: str) -> str:
    """Append context block to tool result on first call.
    If _context_injected is True — returns result unchanged.
    If _context_block is empty — returns result unchanged, sets flag.
    Otherwise — appends '\\n\\n---\\n' + _context_block + '\\n---',
    sets _context_injected = True."""

def _validate_tags(tags: list[str], vault: Vault) -> None:
    """Validate tags against allowed list (all unique tags in vault).
    Raises ValueError with allowed list if any tag is not in vault.
    Called by create_note (if frontmatter has 'tags') and set_frontmatter (if key='tags')."""

def _validate_tag_rules(
    tags: list[str],
    note_name: str,
    frontmatter: dict[str, Any],
) -> None:
    """Validate tag-specific rules. Called after _validate_tags.
    Rules:
    - 'Person': note_name must start with '@'
    - 'claude': frontmatter must contain 'description'
    Raises ValueError with tag use case explanation if rule violated."""

_TAG_RULES: dict[str, dict] = {
    "Person": {
        "check": lambda name, fm: name.startswith("@"),
        "error": "Tag 'Person' is for people notes only. Note name must start with '@' (e.g. '@John Doe').",
    },
    "claude": {
        "check": lambda name, fm: "description" in fm and fm["description"],
        "error": "Tag 'claude' marks instructions for Claude AI. Requires 'description' field in frontmatter explaining when to read the note.",
    },
}
```

## Tools

```python
def _register_tools(server: FastMCP, ops: Operations) -> None:
    """Register all MCP tools. ops passed explicitly, no global state."""

@server.tool()
def read_note(name: str) -> str:
    """Read full note content (frontmatter + body).
    Returns content as text."""

@server.tool()
def create_note(
    name: str,
    content: str = "",
    frontmatter: str = "",
) -> str:
    """Create new note. frontmatter is JSON string parsed to dict.
    Validates tags against allowed list if frontmatter contains 'tags'.
    Returns JSON {"name": ..., "path": ...}."""

@server.tool()
def append_note(name: str, text: str) -> str:
    """Append text to end of note.
    Returns JSON {"name": ..., "status": "appended"}."""

@server.tool()
def update_note(name: str, content: str) -> str:
    """Replace body of note, preserving frontmatter.
    Returns JSON {"name": ..., "status": "updated"}."""

@server.tool()
def delete_note(name: str, dry_run: bool = False) -> str:
    """Delete note. Updates [[links]] → [[name (deleted)]], moves to .trash/.
    Returns JSON DeleteResult."""

@server.tool()
def rename_note(
    old_name: str, new_name: str, dry_run: bool = False,
) -> str:
    """Rename note and update all [[wikilinks]].
    Returns JSON RenameResult."""

@server.tool()
def search_notes(
    query: str,
    mode: str = "name_partial",
    tag_logic: str = "or",
) -> str:
    """Search notes. mode: name|name_partial|content|tag.
    When mode=tag: query is comma-separated tags, tag_logic: and|or.
    Returns JSON list of {name, path}."""

@server.tool()
def get_links(name: str, direction: str = "both") -> str:
    """Get linked notes. direction: in|out|both.
    Returns JSON LinksResult."""

@server.tool()
def get_note_metadata(name: str) -> str:
    """Get note metadata without body: frontmatter + links.
    Returns JSON {"name": ..., "frontmatter": {...}, "outgoing": [...], "incoming": [...]}."""

@server.tool()
def set_frontmatter(name: str, key: str, value: str) -> str:
    """Set top-level frontmatter key.
    Validates tags against allowed list if key='tags'.
    Returns JSON {"name": ..., "key": ..., "value": ...}."""

@server.tool()
def add_tag(name: str, tag: str) -> str:
    """Add tag to note. Validates against allowed list and tag rules.
    Returns JSON {"name": ..., "tags": [...]}."""

@server.tool()
def remove_tag(name: str, tag: str) -> str:
    """Remove tag from note.
    Returns JSON {"name": ..., "tags": [...], "removed": true|false}."""

@server.tool()
def list_notes(limit: int = 100, offset: int = 0) -> str:
    """List note names in vault (names only, no paths).
    Paginated: limit (default 100), offset (default 0).
    Returns JSON {"names": [...], "total": int, "limit": int, "offset": int}."""

@server.tool()
def replace_text(
    name: str,
    old_text: str,
    new_text: str,
    replace_all: bool = False,
) -> str:
    """Replace text in note body. Frontmatter preserved.
    Returns JSON {"name": ..., "replaced": int}."""

@server.tool()
def insert_text(
    name: str,
    text: str,
    before: str = "",
    after: str = "",
) -> str:
    """Insert text before/after a pattern line in note body.
    Exactly one of before/after must be non-empty.
    Returns JSON {"name": ..., "position": "before"|"after", "pattern": ...}."""

@server.tool()
def read_section(name: str, section: str) -> str:
    """Read section content by heading (without the heading line itself).
    Returns plain text like read_note."""

@server.tool()
def append_section(name: str, section: str, text: str) -> str:
    """Append text to end of section.
    Returns JSON {"name": ..., "section": ..., "status": "appended"}."""

@server.tool()
def get_headings(name: str) -> str:
    """Get all headings from note.
    Returns JSON [{"level": 1, "text": "Intro"}, {"level": 2, "text": "Details"}, ...]."""

@server.tool()
def update_section(name: str, section: str, content: str) -> str:
    """Replace section content (heading preserved).
    Returns JSON {"name": ..., "section": ..., "status": "updated"}."""

@server.tool()
def delete_section(name: str, section: str) -> str:
    """Delete section including its heading.
    Returns JSON {"name": ..., "section": ..., "status": "deleted"}."""

@server.tool()
def find_broken_links() -> str:
    """Find all broken links (links to non-existent notes).
    Returns JSON [{"source": ..., "target": ...}, ...]."""

@server.tool()
def get_help() -> str:
    """Get list of all available tools with descriptions and parameters.
    Returns JSON [{"name": ..., "params": ..., "description": ...}, ...]."""
```

## Invariants

1. All tools are thin wrappers around Operations methods — no business logic in MCP layer
2. All tools return JSON strings (MCP tools return text content)
3. VaultError subclasses → `raise ValueError(str(e))` — FastMCP converts to ToolError
4. `frontmatter` param in create_note: empty string → None, non-empty → `json.loads(frontmatter)`. Invalid JSON → ValueError("Invalid frontmatter JSON: {error}")
5. `mode` param in search_notes: string → `SearchMode(mode)`. Invalid mode → ValueError("Invalid search mode: {mode}. Valid: name, name_partial, content, tag")
6. `direction` param in get_links: string → `LinkDirection(direction)`. Invalid direction → ValueError("Invalid direction: {direction}. Valid: in, out, both")
7. Server uses stdio transport: `server.run(transport="stdio")`
8. OBSIDIAN_VAULT_PATH not set → `sys.exit("OBSIDIAN_VAULT_PATH not set")` before server starts
9. No batch tools — ClaudeDesktop calls tools individually
10. `value` in set_frontmatter passed as string — same as CLI behavior
11. Vault created once in `_create_server`, shared between `_build_context_block` and `Operations`
12. No global `_ops` singleton — `ops` passed to `_register_tools` as argument
13. Auto-context and tag policy injected into first tool result, NOT into FastMCP instructions. Instructions contain only `_BASE_INSTRUCTIONS`.
14. Notes with tag `claude` but without `description` in frontmatter — `_MISSING_DESCRIPTION` placeholder used, prompting Claude to fill it.
15. Auto-context tag hardcoded as `_AUTOCONTEXT_TAG = "claude"`
16. Tag policy always present in context block. Collects all unique tags from all notes in vault.
17. Tag policy includes strict prohibition: "NEVER create new tags without explicit user permission."
18. `_context_injected` starts as False, set to True after first tool call. Never reset.
19. `_context_block` built once at startup, cached. Not rebuilt between tool calls.
20. Context injection format: `result + "\n\n---\n" + context_block + "\n---"`
21. No CLAUDE.md file mechanism — vault-specific rules are regular notes with tag `claude`.
22. Every tool result passes through `_inject_context` before returning.
23. `replace_text` returns JSON with `replaced` count — critical for verification
24. `insert_text` validates before/after: both empty or both non-empty → `raise ValueError("Exactly one of 'before' or 'after' must be provided")`
25. `insert_text` before/after: empty string = not provided. Non-empty = pattern to match.
26. `read_section` returns plain text (not JSON) — MCP wraps in JSON-RPC automatically
27. All new tools (replace_text, insert_text, read_section, append_section) are thin wrappers around Operations methods
28. `list_notes` returns only names (no paths), paginated with limit/offset. Default limit=100.
29. `_validate_tags` collects allowed tags from vault at call time (not cached). Raises ValueError listing all invalid tags and the allowed list.
30. `create_note` calls `_validate_tags` if parsed frontmatter contains key `tags`
31. `set_frontmatter` calls `_validate_tags` if key is `tags` — value is JSON-parsed list of strings
32. `_validate_tag_rules` called after `_validate_tags` in create_note and add_tag. Checks tag-specific rules.
33. Tag 'Person' requires note name to start with '@'. Error explains: "for people notes only".
34. Tag 'claude' requires 'description' in frontmatter. Error explains: "marks instructions for Claude AI".
35. `add_tag` reads current tags, appends new tag, validates both allowed list and tag rules, writes back.
36. `remove_tag` reads current tags, removes tag if present, writes back. No validation needed for removal.
37. `add_tag`/`remove_tag` return updated tags list in response.
38. `search_notes` with mode="tag": query is comma-separated tags (trimmed). tag_logic: "and"|"or" (default "or"). Invalid tag_logic → ValueError.
39. tag_logic="or": note matches if ANY tag matches. tag_logic="and": note matches if ALL tags match.
40. Tag matching is hierarchical: "vc" matches "vc" and "vc/project".
41. `get_note_metadata` returns frontmatter + links (both directions) without reading body. Faster for scanning.
42. `get_headings` parses body for lines matching `^(#+)\s+(.+)$`, returns list of {level, text} sorted by position.
43. `update_section` finds section by heading, replaces content between heading and next same-or-higher level heading, preserves the heading line.
44. `delete_section` removes heading line AND all content until next same-or-higher level heading.
45. `update_section`/`delete_section` raise ValueError if section not found (SectionNotFoundError → ValueError).
46. `find_broken_links` returns list of {source, target} for all wikilinks pointing to non-existent notes.
47. `get_frontmatter` removed — use `get_note_metadata` instead (returns frontmatter + links).
48. `get_help` returns static list of all tools with name, params, description. Self-documenting API for external integrations.

## Formulas

```
tool_response = json.dumps(data, ensure_ascii=False)
frontmatter_dict = json.loads(frontmatter) if frontmatter else None
search_mode = SearchMode(mode)  # raises ValueError if invalid
link_direction = LinkDirection(direction)  # raises ValueError if invalid

# Multi-tag search (mode="tag")
def _tag_matches(note_tags: list[str], query_tag: str) -> bool:
    return any(t == query_tag or t.startswith(query_tag + "/") for t in note_tags)

def _search_multi_tag(query: str, tag_logic: str, notes) -> list[SearchResult]:
    if tag_logic not in ("and", "or"):
        raise ValueError(f"Invalid tag_logic: {tag_logic}. Valid: and, or")
    tags = [t.strip() for t in query.split(",") if t.strip()]
    results = []
    for note in notes:
        if tag_logic == "or":
            match = any(_tag_matches(note.tags, t) for t in tags)
        else:  # and
            match = all(_tag_matches(note.tags, t) for t in tags)
        if match:
            results.append(SearchResult(name=note.name, path=str(note.path)))
    return results

# Auto-context (built once at startup, cached in _context_block)
claude_notes = [n for n in vault.list_notes() if _AUTOCONTEXT_TAG in n.tags]
description = note.frontmatter.get("description", _MISSING_DESCRIPTION)
autocontext_line = f'- "{note.name}" — {description}'

# Tag policy (built once at startup, part of _context_block)
all_tags = sorted({tag for note in vault.list_notes() for tag in note.tags})

# Context block = autocontext + tag_policy (both sections concatenated)
_context_block = _build_autocontext(vault) + _build_tag_policy(vault)

# Context injection into tool result (every tool passes through this)
def _inject_context(result: str) -> str:
    nonlocal _context_injected
    if _context_injected or not _context_block:
        return result
    _context_injected = True
    return result + "\n\n---\n" + _context_block + "\n---"

# instructions = _BASE_INSTRUCTIONS only (no vault-specific content)

# list_notes (paginated, names only)
all_names = sorted(n.name for n in vault.list_notes())
page = all_names[offset:offset + limit]
return json.dumps({"names": page, "total": len(all_names), "limit": limit, "offset": offset})

# tag validation
def _validate_tags(tags: list[str], vault: Vault) -> None:
    allowed = {tag for note in vault.list_notes() for tag in note.tags}
    invalid = [t for t in tags if t not in allowed]
    if invalid:
        raise ValueError(
            f"Tags not in allowed list: {invalid}. "
            f"Allowed: {sorted(allowed)}. "
            f"Ask user before creating new tags."
        )

# tag rules validation
def _validate_tag_rules(tags: list[str], note_name: str, frontmatter: dict) -> None:
    for tag in tags:
        if tag in _TAG_RULES:
            rule = _TAG_RULES[tag]
            if not rule["check"](note_name, frontmatter):
                raise ValueError(rule["error"])

# add_tag
fm = ops.frontmatter_get(name)
current_tags = fm.get("tags", [])
if tag not in current_tags:
    new_tags = current_tags + [tag]
    _validate_tags([tag], ops.vault)
    _validate_tag_rules([tag], name, fm)
    ops.frontmatter_set(name, "tags", new_tags)
return _inject_context(json.dumps({"name": name, "tags": new_tags}))

# remove_tag
fm = ops.frontmatter_get(name)
current_tags = fm.get("tags", [])
removed = tag in current_tags
new_tags = [t for t in current_tags if t != tag]
if removed:
    ops.frontmatter_set(name, "tags", new_tags)
return _inject_context(json.dumps({"name": name, "tags": new_tags, "removed": removed}))

# replace_text
replace_result = ops.replace(name, old_text, new_text, replace_all=replace_all)
return _inject_context(json.dumps({"name": replace_result.name, "replaced": replace_result.replacements}, ensure_ascii=False))

# insert_text — validation
if (not before and not after) or (before and after):
    raise ValueError("Exactly one of 'before' or 'after' must be provided")
insert_result = ops.insert(name, text, before=before or None, after=after or None)
return _inject_context(json.dumps({"name": insert_result.name, "position": insert_result.position, "pattern": insert_result.pattern}, ensure_ascii=False))

# read_section — returns plain text
return _inject_context(ops.read_section(name, section))

# append_section
ops.append_section(name, section, text)
return _inject_context(json.dumps({"name": name, "section": section, "status": "appended"}, ensure_ascii=False))

# get_headings
headings = ops.get_headings(name)
return _inject_context(json.dumps([{"level": h.level, "text": h.text} for h in headings], ensure_ascii=False))

# update_section
ops.update_section(name, section, content)
return _inject_context(json.dumps({"name": name, "section": section, "status": "updated"}, ensure_ascii=False))

# delete_section
ops.delete_section(name, section)
return _inject_context(json.dumps({"name": name, "section": section, "status": "deleted"}, ensure_ascii=False))

# find_broken_links
broken = ops.find_broken_links()
return _inject_context(json.dumps([{"source": b.source, "target": b.target} for b in broken], ensure_ascii=False))

# get_help — static tool list
tools_info = [{"name": "read_note", "params": "name: str", "description": "..."}, ...]
return _inject_context(json.dumps(tools_info, ensure_ascii=False))
```

## Test Cases

### TC1: read_note
GIVEN: vault with note "test" containing "Hello"
WHEN: read_note(name="test")
THEN: returns "Hello"

### TC2: read_note not found
GIVEN: empty vault
WHEN: read_note(name="nonexistent")
THEN: raises ValueError("Note 'nonexistent' not found")

### TC3: create_note basic
GIVEN: empty vault
WHEN: create_note(name="test", content="Hello")
THEN: returns JSON with name="test", note file created

### TC4: create_note with frontmatter
GIVEN: empty vault
WHEN: create_note(name="test", frontmatter='{"tags": ["vc"]}')
THEN: note created with frontmatter tags=[vc]

### TC5: append_note
GIVEN: vault with note "test" containing "Line1"
WHEN: append_note(name="test", text="Line2")
THEN: returns JSON with status="appended", file content = "Line1\n\nLine2"

### TC6: update_note
GIVEN: vault with note "test" with frontmatter {"tags": ["a"]} and body "Old"
WHEN: update_note(name="test", content="New")
THEN: returns JSON with status="updated", frontmatter preserved, body="New"

### TC7: delete_note
GIVEN: vault with notes A (contains [[B]]) and B
WHEN: delete_note(name="B")
THEN: returns JSON with files_updated=["A"], B moved to .trash/

### TC8: delete_note dry_run
GIVEN: vault with notes A (contains [[B]]) and B
WHEN: delete_note(name="B", dry_run=True)
THEN: returns JSON with plan, no files changed

### TC9: rename_note
GIVEN: vault with notes A (contains [[B]]) and B
WHEN: rename_note(old_name="B", new_name="B_new")
THEN: returns JSON, file renamed, A contains [[B_new]]

### TC10: search_notes
GIVEN: vault with notes ["alpha", "beta"]
WHEN: search_notes(query="alph")
THEN: returns JSON with alpha in results

### TC11: search_notes by tag
GIVEN: vault with note "test" tags=["vc/project"]
WHEN: search_notes(query="vc", mode="tag")
THEN: returns JSON with test in results (hierarchical)

### TC12: get_links
GIVEN: vault with A→B, C→A
WHEN: get_links(name="A", direction="both")
THEN: returns JSON with outgoing=["B"], incoming=["C"]

### TC14: set_frontmatter
GIVEN: vault with note "test"
WHEN: set_frontmatter(name="test", key="status", value="done")
THEN: returns JSON, frontmatter updated

### TC15: list_notes paginated

GIVEN: vault with notes ["alpha", "beta", "gamma"]
WHEN: list_notes(limit=2, offset=0)
THEN: returns JSON {"names": ["alpha", "beta"], "total": 3, "limit": 2, "offset": 0}

### TC16: list_notes empty vault
GIVEN: empty vault
WHEN: list_notes()
THEN: returns JSON {"names": [], "total": 0, "limit": 100, "offset": 0}

### TC16a: list_notes offset

GIVEN: vault with notes ["alpha", "beta", "gamma"]
WHEN: list_notes(limit=2, offset=2)
THEN: returns JSON {"names": ["gamma"], "total": 3, "limit": 2, "offset": 2}

### TC17: auto-context injected in first tool result
GIVEN: vault with note "My Rules" with tags=["claude"] and frontmatter description="Read before writing text"
WHEN: first tool call (e.g. list_notes()) executed
THEN: result contains '\n\n---\n' + '## Your personal notes' section with '"My Rules" — Read before writing text' + '\n---'

### TC18: auto-context not injected in second tool result
GIVEN: vault with note "My Rules" with tags=["claude"], first tool call already made
WHEN: second tool call (e.g. read_note("test")) executed
THEN: result does NOT contain '## Your personal notes' section

### TC19: auto-context no notes — hint in first tool result
GIVEN: vault with no notes tagged "claude"
WHEN: first tool call executed
THEN: result contains '## Your personal notes' section with hint about creating notes

### TC20: auto-context missing description
GIVEN: vault with note "No Desc" with tags=["claude"] and no description in frontmatter
WHEN: first tool call executed
THEN: result contains '"No Desc" — ⚠️ No description...' with prompt to fill it

### TC21: no global ops singleton
GIVEN: server created via _create_server()
WHEN: inspecting module state
THEN: no global _ops variable, ops passed explicitly to _register_tools

### TC22: single Vault instance
GIVEN: _create_server() called
WHEN: Vault used for context block and Operations
THEN: same Vault instance passed to both _build_context_block and Operations constructor

### TC23: tag policy in first tool result
GIVEN: vault with notes having tags ["vc", "vc/project", "Person"]
WHEN: first tool call executed
THEN: result contains '## Allowed tags' section with all three tags and strict prohibition

### TC24: tag policy empty vault
GIVEN: empty vault (no notes, no tags)
WHEN: first tool call executed
THEN: result contains '## Allowed tags' section with hint about no tags

### TC25: tag policy deduplication
GIVEN: vault with two notes both having tag "vc"
WHEN: first tool call executed
THEN: result contains "vc" exactly once in allowed tags section

### TC26: instructions contain only base instructions
GIVEN: vault with notes tagged "claude" and CLAUDE.md file in vault root
WHEN: _build_instructions() called
THEN: instructions == _BASE_INSTRUCTIONS only, no auto-context, no tag policy, no CLAUDE.md content

### TC27: no CLAUDE.md file mechanism
GIVEN: vault with CLAUDE.md file in root
WHEN: _create_server() called
THEN: CLAUDE.md content is NOT read, NOT included anywhere

### TC28: context block empty — no injection
GIVEN: empty vault (no notes, no tags)
WHEN: _build_context_block(vault) called
THEN: both sections are "empty with hints", block is still injected (hints are useful)

### TC29: replace_text

GIVEN: vault with note "test" body containing "foo bar foo"
WHEN: replace_text(name="test", old_text="foo", new_text="baz")
THEN: returns JSON {"name": "test", "replaced": 1}

### TC30: replace_text replace_all

GIVEN: vault with note "test" body containing "foo bar foo"
WHEN: replace_text(name="test", old_text="foo", new_text="baz", replace_all=True)
THEN: returns JSON {"name": "test", "replaced": 2}

### TC31: replace_text not found

GIVEN: vault with note "test" body containing "hello"
WHEN: replace_text(name="test", old_text="xyz", new_text="abc")
THEN: raises ValueError (TextNotFoundError → ValueError)

### TC32: insert_text after

GIVEN: vault with note "test" body containing "line1\nline2"
WHEN: insert_text(name="test", text="inserted", after="line1")
THEN: returns JSON {"name": "test", "position": "after", "pattern": "line1"}

### TC33: insert_text before

GIVEN: vault with note "test" body containing "line1\nline2"
WHEN: insert_text(name="test", text="inserted", before="line2")
THEN: returns JSON {"name": "test", "position": "before", "pattern": "line2"}

### TC34: insert_text both params error

GIVEN: vault with note "test"
WHEN: insert_text(name="test", text="x", before="a", after="b")
THEN: raises ValueError("Exactly one of 'before' or 'after' must be provided")

### TC35: insert_text neither param error

GIVEN: vault with note "test"
WHEN: insert_text(name="test", text="x")
THEN: raises ValueError("Exactly one of 'before' or 'after' must be provided")

### TC36: read_section

GIVEN: vault with note "test" containing "# Intro\nHello\n# Other\nWorld"
WHEN: read_section(name="test", section="Intro")
THEN: returns "Hello" (plain text, not JSON)

### TC37: read_section not found

GIVEN: vault with note "test" without section "Missing"
WHEN: read_section(name="test", section="Missing")
THEN: raises ValueError (SectionNotFoundError → ValueError)

### TC38: append_section

GIVEN: vault with note "test" containing "# Intro\nHello\n# Other\nWorld"
WHEN: append_section(name="test", section="Intro", text="More")
THEN: returns JSON {"name": "test", "section": "Intro", "status": "appended"}

### TC39: create_note with invalid tags rejected

GIVEN: vault with notes having tags ["vc", "Person"]
WHEN: create_note(name="new", frontmatter='{"tags": ["vc", "career"]}')
THEN: raises ValueError containing "Tags not in allowed list: ['career']" and "Allowed: " with existing tags

### TC40: create_note with valid tags accepted

GIVEN: vault with notes having tags ["vc", "Person"]
WHEN: create_note(name="new", frontmatter='{"tags": ["vc"]}')
THEN: note created successfully

### TC41: set_frontmatter tags validated

GIVEN: vault with notes having tags ["vc", "Person"], note "test" exists
WHEN: set_frontmatter(name="test", key="tags", value='["vc", "unknown"]')
THEN: raises ValueError containing "Tags not in allowed list: ['unknown']"

### TC42: set_frontmatter non-tags key not validated

GIVEN: vault with note "test"
WHEN: set_frontmatter(name="test", key="status", value="done")
THEN: frontmatter updated, no tag validation

### TC43: create_note invalid JSON frontmatter

GIVEN: empty vault
WHEN: create_note(name="test", frontmatter="{invalid json}")
THEN: raises ValueError containing "Invalid frontmatter JSON"

### TC44: search_notes invalid mode

GIVEN: vault with notes
WHEN: search_notes(query="test", mode="invalid")
THEN: raises ValueError containing "Invalid search mode"

### TC45: get_links invalid direction

GIVEN: vault with note "test"
WHEN: get_links(name="test", direction="invalid")
THEN: raises ValueError containing "Invalid direction"

### TC46: add_tag basic

GIVEN: vault with note "test" tags=["vc"], note "other" tags=["Person"]
WHEN: add_tag(name="test", tag="Person")
THEN: raises ValueError containing "note name must start with '@'"

### TC47: add_tag Person to @-note

GIVEN: vault with note "@John" tags=[], note "other" tags=["Person"]
WHEN: add_tag(name="@John", tag="Person")
THEN: returns JSON {"name": "@John", "tags": ["Person"]}

### TC48: add_tag claude without description

GIVEN: vault with note "test" tags=[], frontmatter={}, note "other" tags=["claude"]
WHEN: add_tag(name="test", tag="claude")
THEN: raises ValueError containing "Requires 'description' field"

### TC49: add_tag claude with description

GIVEN: vault with note "test" frontmatter={"description": "My rules"}, note "other" tags=["claude"]
WHEN: add_tag(name="test", tag="claude")
THEN: returns JSON {"name": "test", "tags": ["claude"]}

### TC50: remove_tag basic

GIVEN: vault with note "test" tags=["vc", "project"]
WHEN: remove_tag(name="test", tag="vc")
THEN: returns JSON {"name": "test", "tags": ["project"], "removed": true}

### TC51: remove_tag not present

GIVEN: vault with note "test" tags=["vc"]
WHEN: remove_tag(name="test", tag="project")
THEN: returns JSON {"name": "test", "tags": ["vc"], "removed": false}

### TC52: create_note with Person tag on non-@ note

GIVEN: vault with note "other" tags=["Person"]
WHEN: create_note(name="John", frontmatter='{"tags": ["Person"]}')
THEN: raises ValueError containing "note name must start with '@'"

### TC53: create_note with Person tag on @-note

GIVEN: vault with note "other" tags=["Person"]
WHEN: create_note(name="@John", frontmatter='{"tags": ["Person"]}')
THEN: note created successfully

### TC54: search_notes multi-tag OR

GIVEN: vault with notes: "a" tags=["vc"], "b" tags=["project"], "c" tags=["vc", "project"]
WHEN: search_notes(query="vc,project", mode="tag", tag_logic="or")
THEN: returns all three notes (a, b, c)

### TC55: search_notes multi-tag AND

GIVEN: vault with notes: "a" tags=["vc"], "b" tags=["project"], "c" tags=["vc", "project"]
WHEN: search_notes(query="vc,project", mode="tag", tag_logic="and")
THEN: returns only "c" (has both tags)

### TC56: search_notes invalid tag_logic

GIVEN: vault with notes
WHEN: search_notes(query="vc", mode="tag", tag_logic="invalid")
THEN: raises ValueError containing "Invalid tag_logic"

### TC57: search_notes multi-tag hierarchical

GIVEN: vault with notes: "a" tags=["vc/project"], "b" tags=["vc/idea"]
WHEN: search_notes(query="vc", mode="tag")
THEN: returns both notes (hierarchical match)

### TC58: get_note_metadata

GIVEN: vault with note "A" tags=["vc"], body contains [[B]], note "C" contains [[A]]
WHEN: get_note_metadata(name="A")
THEN: returns JSON {"name": "A", "frontmatter": {"tags": ["vc"]}, "outgoing": ["B"], "incoming": ["C"]}

### TC59: get_note_metadata not found

GIVEN: empty vault
WHEN: get_note_metadata(name="nonexistent")
THEN: raises ValueError("Note 'nonexistent' not found")

### TC60: get_headings basic

GIVEN: vault with note "test" body "# Intro\nText\n## Details\nMore\n### Sub"
WHEN: get_headings(name="test")
THEN: returns JSON [{"level": 1, "text": "Intro"}, {"level": 2, "text": "Details"}, {"level": 3, "text": "Sub"}]

### TC61: get_headings no headings

GIVEN: vault with note "test" body "Just plain text"
WHEN: get_headings(name="test")
THEN: returns JSON []

### TC62: update_section basic

GIVEN: vault with note "test" body "# Intro\nOld content\n# Other\nKeep"
WHEN: update_section(name="test", section="Intro", content="New content")
THEN: returns JSON {"name": "test", "section": "Intro", "status": "updated"}, body becomes "# Intro\nNew content\n# Other\nKeep"

### TC63: update_section not found

GIVEN: vault with note "test" without section "Missing"
WHEN: update_section(name="test", section="Missing", content="x")
THEN: raises ValueError (SectionNotFoundError → ValueError)

### TC64: delete_section basic

GIVEN: vault with note "test" body "# Intro\nContent\n# Other\nKeep"
WHEN: delete_section(name="test", section="Intro")
THEN: returns JSON {"name": "test", "section": "Intro", "status": "deleted"}, body becomes "# Other\nKeep"

### TC65: delete_section not found

GIVEN: vault with note "test" without section "Missing"
WHEN: delete_section(name="test", section="Missing")
THEN: raises ValueError (SectionNotFoundError → ValueError)

### TC66: find_broken_links

GIVEN: vault with notes "A" (contains [[B]] and [[Missing]]), "B" (exists)
WHEN: find_broken_links()
THEN: returns JSON [{"source": "A", "target": "Missing"}]

### TC67: find_broken_links no broken

GIVEN: vault with notes "A" (contains [[B]]), "B" (exists)
WHEN: find_broken_links()
THEN: returns JSON []

### TC68: get_help

GIVEN: any vault
WHEN: get_help()
THEN: returns JSON list with all tools, each having "name", "params", "description"
