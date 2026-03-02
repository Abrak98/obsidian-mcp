"""Markdown validation."""

from __future__ import annotations

import re
from dataclasses import dataclass

from obsidian_mcp.errors import VaultError

# Obsidian Tasks plugin emojis
TASKS_EMOJIS = "➕⏳🛫📅✅❌⏬🔽🔼⏫🔺🔁🏁🆔⛔"


@dataclass(slots=True)
class ValidationWarning:
    line: int
    message: str
    rule: str  # "table-blank-line" | "unclosed-code-block" | "broken-link"


class InvalidNameError(VaultError):
    """Raised when note name contains invalid characters."""

    pass


class InvalidHeadingError(VaultError):
    """Raised when heading contains Cyrillic characters."""

    pass


class BrokenLinkError(VaultError):
    """Raised when wikilink points to non-existent section."""

    pass


SECTION_SIZE_THRESHOLD = 5000


class Validator:
    """Stateless markdown validator."""

    _FENCE_RE = re.compile(r"^(`{3,})")
    _H2_HEADING_RE = re.compile(r"^##\s+(.+)$")
    _TABLE_LINE_RE = re.compile(r"^\|.*\|$")
    _TABLE_SEP_RE = re.compile(r"^\|[-:| ]+\|$")
    _HEADING_RE = re.compile(r"^(#+)\s+(.+)$")
    _CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
    _ALLOWED_NAME_RE = re.compile(rf"^[a-zA-Z0-9 _@\-{TASKS_EMOJIS}]+$")

    def validate_name(self, name: str) -> None:
        """Validate note name.

        Raises InvalidNameError if name contains Cyrillic or invalid characters.
        Allowed: a-zA-Z, 0-9, spaces, underscore, hyphen, @, Obsidian Tasks emojis.
        """
        if self._CYRILLIC_RE.search(name):
            raise InvalidNameError(f"Note name contains Cyrillic: {name}")
        if not self._ALLOWED_NAME_RE.match(name):
            raise InvalidNameError(f"Note name contains invalid characters: {name}")

    def validate(self, content: str) -> list[ValidationWarning]:
        """Validate markdown content (post-write).

        Checks:
        - Tables must have blank line before them (if preceded by text)
        - Fenced code blocks must be closed (paired ```)

        Returns list of warnings (empty if valid).
        """
        lines = content.split("\n")
        warnings: list[ValidationWarning] = []

        # Step 1: Parse code blocks
        code_block_ranges, unclosed = self._parse_code_blocks(lines)
        for line_num in unclosed:
            warnings.append(
                ValidationWarning(
                    line=line_num,
                    message="Unclosed fenced code block",
                    rule="unclosed-code-block",
                )
            )

        # Step 2: Check tables (skip lines inside code blocks)
        table_warnings = self._check_tables(lines, code_block_ranges)
        warnings.extend(table_warnings)

        return warnings

    def validate_section_sizes(
        self, content: str, threshold: int = SECTION_SIZE_THRESHOLD
    ) -> list[ValidationWarning]:
        """Validate h2 section sizes (post-write, warning).

        Checks that h2 sections don't exceed threshold characters.
        Section = from ## to next ## (or end of file).
        Includes all content including h3/h4 subsections.

        Returns warnings for sections exceeding threshold.
        """
        lines = content.split("\n")
        warnings: list[ValidationWarning] = []

        # Find all h2 positions
        h2_positions: list[tuple[int, str]] = []
        for i, line in enumerate(lines):
            match = self._H2_HEADING_RE.match(line)
            if match:
                h2_positions.append((i, match.group(1)))

        # Calculate section sizes
        for idx, (start_line, heading_text) in enumerate(h2_positions):
            # End is next h2 or end of file
            if idx + 1 < len(h2_positions):
                end_line = h2_positions[idx + 1][0]
            else:
                end_line = len(lines)

            # Calculate section content (excluding the heading itself)
            section_lines = lines[start_line + 1 : end_line]
            section_content = "\n".join(section_lines)
            section_size = len(section_content)

            if section_size > threshold:
                warnings.append(
                    ValidationWarning(
                        line=start_line + 1,  # 1-indexed
                        message=f"Section '{heading_text}' is {section_size} chars "
                        f"(>{threshold}). Consider adding [EXTRACT] marker.",
                        rule="section-too-large",
                    )
                )

        return warnings

    def validate_headings(self, content: str) -> None:
        """Validate headings are English only (pre-write, blocking).

        Raises InvalidHeadingError if any heading contains Cyrillic.
        Skips headings inside code blocks.
        """
        lines = content.split("\n")
        code_block_ranges, _ = self._parse_code_blocks(lines)

        for i, line in enumerate(lines):
            line_num = i + 1  # 1-indexed

            # Skip if inside code block
            if self._is_inside_code_block(line_num, code_block_ranges):
                continue

            match = self._HEADING_RE.match(line)
            if match:
                heading_text = match.group(2)
                if self._CYRILLIC_RE.search(heading_text):
                    raise InvalidHeadingError(
                        f"Heading contains Cyrillic at line {line_num}: {heading_text}"
                    )

    def _parse_code_blocks(
        self, lines: list[str]
    ) -> tuple[list[tuple[int, int]], list[int]]:
        """Parse fenced code blocks.

        Returns:
            (closed_ranges, unclosed_lines):
            - closed_ranges: list of (start, end) line numbers for closed blocks
            - unclosed_lines: list of line numbers for unclosed fences
        """
        closed_ranges: list[tuple[int, int]] = []
        stack: list[tuple[int, int]] = []  # (line_num, backtick_count)
        in_code_block = False
        current_fence_length = 0

        for i, line in enumerate(lines):
            line_num = i + 1  # 1-indexed
            match = self._FENCE_RE.match(line)
            if match:
                backtick_count = len(match.group(1))
                if not in_code_block:
                    stack.append((line_num, backtick_count))
                    in_code_block = True
                    current_fence_length = backtick_count
                else:
                    if backtick_count >= current_fence_length:
                        start_line, _ = stack.pop()
                        closed_ranges.append((start_line, line_num))
                        in_code_block = False
                        current_fence_length = 0

        unclosed_lines = [line_num for line_num, _ in stack]
        return closed_ranges, unclosed_lines

    def _is_inside_code_block(
        self, line_num: int, ranges: list[tuple[int, int]]
    ) -> bool:
        """Check if line is inside any closed code block."""
        for start, end in ranges:
            if start < line_num < end:
                return True
        return False

    def _check_tables(
        self, lines: list[str], code_block_ranges: list[tuple[int, int]]
    ) -> list[ValidationWarning]:
        """Check tables have blank line before them."""
        warnings: list[ValidationWarning] = []

        for i in range(len(lines) - 1):
            line_num = i + 1  # 1-indexed

            # Skip if inside code block
            if self._is_inside_code_block(line_num, code_block_ranges):
                continue

            # Check for table start: TABLE_LINE followed by TABLE_SEPARATOR
            if self._TABLE_LINE_RE.match(lines[i]) and self._TABLE_SEP_RE.match(
                lines[i + 1]
            ):
                # Table at document start is valid
                if i == 0:
                    continue

                # Check if previous line is blank
                prev_line = lines[i - 1]
                if prev_line.strip():  # Not blank
                    warnings.append(
                        ValidationWarning(
                            line=line_num,
                            message="Table should have blank line before it",
                            rule="table-blank-line",
                        )
                    )

        return warnings
