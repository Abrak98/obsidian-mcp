"""Tests for validation module based on technical spec."""

from pathlib import Path

import pytest

from obsidian_mcp.operations import Operations
from obsidian_mcp.validation import (
    BrokenLinkError,
    InvalidHeadingError,
    InvalidNameError,
    Validator,
)
from obsidian_mcp.vault import Vault


@pytest.fixture
def validator() -> Validator:
    return Validator()


class TestValidMarkdown:
    """TC1, TC5, TC6, TC7, TC8: Valid markdown cases."""

    def test_valid_markdown_no_warnings(self, validator: Validator) -> None:
        """TC1: Valid markdown with table after blank line."""
        content = "# Title\n\nSome text.\n\n| A | B |\n|---|---|\n| 1 | 2 |"
        result = validator.validate(content)
        assert result == []

    def test_table_at_document_start_valid(self, validator: Validator) -> None:
        """TC5: Table at document start is valid."""
        content = "| A | B |\n|---|---|\n| 1 | 2 |"
        result = validator.validate(content)
        assert result == []

    def test_closed_code_block_valid(self, validator: Validator) -> None:
        """TC6: Closed code block is valid."""
        content = "```python\ncode\n```"
        result = validator.validate(content)
        assert result == []

    def test_multiple_code_blocks_all_closed(self, validator: Validator) -> None:
        """TC7: Multiple closed code blocks are valid."""
        content = "```\na\n```\n\n```\nb\n```"
        result = validator.validate(content)
        assert result == []

    def test_table_after_blank_line_valid(self, validator: Validator) -> None:
        """TC8: Table after blank line is valid."""
        content = "text\n\n| A |\n|---|"
        result = validator.validate(content)
        assert result == []


class TestTableWarnings:
    """TC2: Table without blank line before."""

    def test_table_without_blank_line_before(self, validator: Validator) -> None:
        """TC2: Table without blank line triggers warning."""
        content = "Some text\n| A | B |\n|---|---|\n| 1 | 2 |"
        result = validator.validate(content)
        assert len(result) == 1
        assert result[0].rule == "table-blank-line"
        assert result[0].line == 2


class TestCodeBlockWarnings:
    """TC3: Unclosed code block."""

    def test_unclosed_code_block(self, validator: Validator) -> None:
        """TC3: Unclosed code block triggers warning."""
        content = "# Title\n\n```python\ncode here"
        result = validator.validate(content)
        assert len(result) == 1
        assert result[0].rule == "unclosed-code-block"
        assert result[0].line == 3


class TestMultipleIssues:
    """TC4: Multiple issues in same content."""

    def test_multiple_issues(self, validator: Validator) -> None:
        """TC4: Both table and code block issues detected."""
        content = "text\n| A |\n|---|\n```\ncode"
        result = validator.validate(content)
        assert len(result) == 2
        assert any(w.rule == "table-blank-line" for w in result)
        assert any(w.rule == "unclosed-code-block" for w in result)


class TestTableInsideCodeBlock:
    """TC9: Table inside code block should be ignored."""

    def test_table_inside_closed_code_block_ignored(self, validator: Validator) -> None:
        """TC9: Table inside closed code block is not flagged."""
        content = "```\n| A |\n|---|\n```"
        result = validator.validate(content)
        assert result == []


class TestNestedCodeBlocks:
    """TC10, TC11: Nested code blocks with different backtick counts."""

    def test_nested_code_blocks_with_4_backticks(self, validator: Validator) -> None:
        """TC10: Nested code blocks with 4 backticks are valid."""
        content = "````\n```\nnested\n```\n````"
        result = validator.validate(content)
        assert result == []

    def test_inner_fence_inside_outer_block_is_text(self, validator: Validator) -> None:
        """TC11: Inner ``` is content inside ```` block, not a fence."""
        content = "````\n```\nnested\n````"
        result = validator.validate(content)
        assert result == []


class TestInlineBackticks:
    """TC12: Inline backticks not treated as fence."""

    def test_inline_backticks_not_treated_as_fence(self, validator: Validator) -> None:
        """TC12: Inline triple backticks are not code fences."""
        content = "Use `code` inline and ```also``` triple"
        result = validator.validate(content)
        assert result == []


class TestNameValidation:
    """TC13-TC17: Note name validation."""

    def test_valid_english_name(self, validator: Validator) -> None:
        """TC13: Valid English name passes."""
        validator.validate_name("My Project 2024")  # No exception

    def test_cyrillic_name_error(self, validator: Validator) -> None:
        """TC14: Name with Cyrillic raises error."""
        with pytest.raises(InvalidNameError):
            validator.validate_name("Мой проект")

    def test_name_with_tasks_emoji_valid(self, validator: Validator) -> None:
        """TC15: Name with Tasks emoji passes."""
        validator.validate_name("Task 📅 deadline")  # No exception

    def test_name_mixed_valid_chars(self, validator: Validator) -> None:
        """TC16: Name with mixed valid chars passes."""
        validator.validate_name("Project 123 ⏫ high")  # No exception

    def test_name_invalid_punctuation_error(self, validator: Validator) -> None:
        """TC17: Name with invalid punctuation raises error."""
        with pytest.raises(InvalidNameError):
            validator.validate_name("Project: Test")


class TestHeadingValidation:
    """TC18-TC21: Heading validation for Cyrillic (blocking)."""

    def test_english_heading_valid(self, validator: Validator) -> None:
        """TC18: English heading passes."""
        content = "# My Title\n\nText"
        validator.validate_headings(content)  # No exception

    def test_cyrillic_heading_error(self, validator: Validator) -> None:
        """TC19: Cyrillic heading raises error."""
        content = "# Заголовок\n\nText"
        with pytest.raises(InvalidHeadingError):
            validator.validate_headings(content)

    def test_cyrillic_heading_inside_code_block_ignored(
        self, validator: Validator
    ) -> None:
        """TC20: Cyrillic heading inside code block is ignored."""
        content = "```\n# Заголовок\n```"
        validator.validate_headings(content)  # No exception

    def test_multiple_headings_one_cyrillic(self, validator: Validator) -> None:
        """TC21: Multiple headings, one Cyrillic - error."""
        content = "# Title\n\n## Секция\n\n### Footer"
        with pytest.raises(InvalidHeadingError):
            validator.validate_headings(content)


# --- Wikilinks Validation Tests (TC22-TC26) ---


def _write_note(vault_dir: Path, name: str, content: str) -> Path:
    path = vault_dir / f"{name}.md"
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def vault_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def ops(vault_dir: Path) -> Operations:
    vault = Vault(vault_dir)
    return Operations(vault)


class TestWikilinksValidation:
    """TC22-TC26: Wikilinks validation."""

    def test_valid_wikilink_to_existing_note(
        self, vault_dir: Path, ops: Operations
    ) -> None:
        """TC22: Valid wikilink to existing note - no warnings."""
        _write_note(vault_dir, "Target", "Some content")
        ops.vault.refresh()
        content = "Link to [[Target]]"
        warnings = ops._validate_wikilinks(content)
        assert warnings == []

    def test_wikilink_to_nonexistent_note_warning(
        self, vault_dir: Path, ops: Operations
    ) -> None:
        """TC23: Wikilink to non-existent note - warning."""
        content = "Link to [[Missing]]"
        warnings = ops._validate_wikilinks(content)
        assert len(warnings) == 1
        assert warnings[0].rule == "broken-link"

    def test_valid_wikilink_with_section(
        self, vault_dir: Path, ops: Operations
    ) -> None:
        """TC24: Valid wikilink with section - no warnings."""
        _write_note(vault_dir, "Target", "# Section\n\nContent")
        ops.vault.refresh()
        content = "Link to [[Target#Section]]"
        warnings = ops._validate_wikilinks(content)
        assert warnings == []

    def test_wikilink_with_nonexistent_section_error(
        self, vault_dir: Path, ops: Operations
    ) -> None:
        """TC25: Wikilink with non-existent section - blocking error."""
        _write_note(vault_dir, "Target", "# Other\n\nContent")
        ops.vault.refresh()
        content = "Link to [[Target#Missing]]"
        with pytest.raises(BrokenLinkError):
            ops._validate_wikilinks(content)

    def test_multiple_wikilinks_one_broken_section(
        self, vault_dir: Path, ops: Operations
    ) -> None:
        """TC26: Multiple wikilinks, one broken section - error."""
        _write_note(vault_dir, "A", "# Intro\n\nContent")
        _write_note(vault_dir, "B", "# Other\n\nContent")
        ops.vault.refresh()
        content = "[[A#Intro]] and [[B#Nope]]"
        with pytest.raises(BrokenLinkError):
            ops._validate_wikilinks(content)
