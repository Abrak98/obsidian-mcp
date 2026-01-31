#!/usr/bin/env python3
"""
SDD Validator - Pre-commit hook for Specification-Driven Development.

Features:
1. Hash validation: narrative.md hash must match Narrative-Hash in technical.md
2. Auto-update: If code for an approved spec is committed, auto-update Status to committed
3. Spec tests: Run spec tests for affected specs

Usage:
    poetry run python hooks/sdd_validator.py
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path


SPECS_DIR = Path("specs")
TESTS_SPEC_DIR = Path("tests/spec")


def get_staged_files() -> list[str]:
    """Get list of staged files."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [f for f in result.stdout.strip().split("\n") if f]


def git_add(file_path: str) -> None:
    """Add file to staging area."""
    subprocess.run(["git", "add", file_path], check=True)


def compute_md5(file_path: Path) -> str:
    """Compute MD5 hash of a file."""
    return hashlib.md5(file_path.read_bytes()).hexdigest()


def find_all_specs() -> list[tuple[Path, Path]]:
    """Find all narrative/technical spec pairs.

    Returns list of (narrative_path, technical_path) tuples.
    """
    specs = []
    for technical_path in SPECS_DIR.rglob("*.technical.md"):
        name = technical_path.stem.replace(".technical", "")
        narrative_path = technical_path.parent / f"{name}.narrative.md"
        if narrative_path.exists():
            specs.append((narrative_path, technical_path))
    return specs


def parse_technical_md(technical_path: Path) -> dict[str, str]:
    """Parse technical.md and extract metadata."""
    content = technical_path.read_text()
    metadata = {}

    hash_match = re.search(r"^Narrative-Hash:\s*(\w+)", content, re.MULTILINE)
    if hash_match:
        metadata["narrative_hash"] = hash_match.group(1)

    status_match = re.search(r"^Status:\s*(\w+)", content, re.MULTILINE)
    if status_match:
        metadata["status"] = status_match.group(1)

    return metadata


def update_status_in_technical_md(technical_path: Path, new_status: str) -> None:
    """Update Status field in technical.md."""
    content = technical_path.read_text()
    updated = re.sub(
        r"^(Status:\s*)\w+",
        f"\\g<1>{new_status}",
        content,
        count=1,
        flags=re.MULTILINE,
    )
    technical_path.write_text(updated)


def get_spec_name_from_test(test_path: str) -> str | None:
    """Extract spec name from test file path.

    tests/spec/core/test_vault_spec.py -> vault
    """
    match = re.match(r"tests/spec/\w+/test_(\w+)_spec\.py$", test_path)
    if match:
        return match.group(1)
    return None


def find_technical_md_by_name(spec_name: str) -> Path | None:
    """Find technical.md by spec name."""
    for technical_path in SPECS_DIR.rglob("*.technical.md"):
        name = technical_path.stem.replace(".technical", "")
        if name == spec_name:
            return technical_path
    return None


def validate_hashes(specs: list[tuple[Path, Path]]) -> list[str]:
    """Validate narrative hashes match stored hashes.

    Returns list of error messages.
    """
    errors = []
    for narrative_path, technical_path in specs:
        metadata = parse_technical_md(technical_path)
        stored_hash = metadata.get("narrative_hash")
        status = metadata.get("status")

        if status not in ("approved", "committed"):
            continue

        if not stored_hash:
            errors.append(f"ERROR: {technical_path} missing Narrative-Hash")
            continue

        current_hash = compute_md5(narrative_path)
        if stored_hash != current_hash:
            errors.append(
                f"ERROR: Hash mismatch for {narrative_path.stem}\n"
                f"  Stored:  {stored_hash}\n"
                f"  Current: {current_hash}\n"
                f"  Run: md5sum {narrative_path}"
            )

    return errors


def find_affected_specs(staged_files: list[str]) -> set[str]:
    """Find spec names affected by staged files.

    Checks:
    - tests/spec/*/test_{name}_spec.py -> name
    - src/*/{name}.py -> name (if matching spec exists)
    """
    affected: set[str] = set()

    for staged_file in staged_files:
        # From test file
        spec_name = get_spec_name_from_test(staged_file)
        if spec_name:
            affected.add(spec_name)

        # From source file
        if staged_file.startswith("src/") and staged_file.endswith(".py"):
            file_stem = Path(staged_file).stem
            for technical_path in SPECS_DIR.rglob("*.technical.md"):
                spec_name = technical_path.stem.replace(".technical", "")
                if spec_name.replace("_", "") in file_stem.replace("_", ""):
                    affected.add(spec_name)

    return affected


def find_test_file(spec_name: str) -> Path | None:
    """Find test file for spec name."""
    for test_file in TESTS_SPEC_DIR.rglob(f"test_{spec_name}_spec.py"):
        return test_file
    return None


def run_spec_tests(spec_names: set[str]) -> list[str]:
    """Run pytest for affected specs.

    Returns list of error messages.
    """
    errors: list[str] = []
    test_files: list[str] = []

    for spec_name in spec_names:
        test_file = find_test_file(spec_name)
        if test_file:
            test_files.append(str(test_file))

    if not test_files:
        return errors

    print(f"Running tests for specs: {sorted(spec_names)}")
    result = subprocess.run(
        ["poetry", "run", "python", "-m", "pytest", *test_files, "-v", "--tb=short"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        errors.append(f"ERROR: Spec tests failed:\n{result.stdout}\n{result.stderr}")

    return errors


def auto_update_status(staged_files: list[str]) -> list[str]:
    """Auto-update Status from approved to committed for specs with staged code.

    Returns list of updated spec names.
    """
    updated = []
    spec_names = find_affected_specs(staged_files)

    for spec_name in spec_names:
        spec_technical_path = find_technical_md_by_name(spec_name)
        if not spec_technical_path:
            continue

        metadata = parse_technical_md(spec_technical_path)
        if metadata.get("status") == "approved":
            print(f"Auto-updating {spec_technical_path}: approved -> committed")
            update_status_in_technical_md(spec_technical_path, "committed")
            git_add(str(spec_technical_path))
            updated.append(spec_name)

    return updated


def main() -> int:
    """Main entry point."""
    print("SDD Validator running...")

    staged_files = get_staged_files()
    if not staged_files:
        print("No staged files, skipping SDD validation")
        return 0

    specs = find_all_specs()
    if not specs:
        print("No specs found, skipping SDD validation")
        return 0

    updated_specs = auto_update_status(staged_files)
    if updated_specs:
        print(f"Auto-updated specs: {updated_specs}")

    hash_errors = validate_hashes(specs)
    if hash_errors:
        for error in hash_errors:
            print(error)
        return 1

    # Run spec tests for affected specs
    affected_specs = find_affected_specs(staged_files)
    if affected_specs:
        test_errors = run_spec_tests(affected_specs)
        if test_errors:
            for error in test_errors:
                print(error)
            return 1

    print("SDD Validator passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
