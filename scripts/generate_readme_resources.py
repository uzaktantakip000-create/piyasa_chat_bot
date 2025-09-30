#!/usr/bin/env python3
"""Synchronize the README resource section with documentation files.

This script reads all Markdown documents in the ``docs`` directory, extracts
their main titles and ensures the "Yol Haritası ve Kaynaklar" section in the
README lists every document. Use ``--check`` in CI to make sure contributors
regenerate the README when adding or removing docs.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = REPO_ROOT / "docs"
README_PATH = REPO_ROOT / "README.md"
MARKER_START = "<!-- README_DOCS_START -->"
MARKER_END = "<!-- README_DOCS_END -->"


def _extract_title(markdown_path: Path) -> str:
    """Return the first Markdown heading from ``markdown_path``.

    Falls back to a prettified version of the filename if no heading exists.
    """

    for line in markdown_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            # Remove leading hashes and whitespace
            return stripped.lstrip("#").strip()

    stem = markdown_path.stem.replace("_", " ").replace("-", " ")
    return stem.title()


def _build_resource_lines(paths: Iterable[Path]) -> list[str]:
    lines: list[str] = []
    for path in sorted(paths, key=lambda p: p.name.lower()):
        title = _extract_title(path)
        rel_path = path.relative_to(REPO_ROOT).as_posix()
        lines.append(f"- [{title}]({rel_path})")
    return lines


def _replace_section(content: str, replacement: str) -> str:
    pattern = re.compile(
        rf"{re.escape(MARKER_START)}(.*?){re.escape(MARKER_END)}",
        re.DOTALL,
    )
    if not pattern.search(content):
        raise RuntimeError(
            "Could not find README markers for documentation resources. "
            "Ensure the README contains both markers."
        )
    return pattern.sub(f"{MARKER_START}\n{replacement}\n{MARKER_END}", content)


def sync_readme(check_only: bool) -> int:
    if not DOCS_DIR.exists():
        raise RuntimeError("The docs directory does not exist; nothing to sync.")

    markdown_files = [p for p in DOCS_DIR.glob("*.md") if p.is_file()]
    if not markdown_files:
        raise RuntimeError("No Markdown files found in docs directory.")

    generated_block = "\n".join(_build_resource_lines(markdown_files))
    current_content = README_PATH.read_text(encoding="utf-8")
    updated_content = _replace_section(current_content, generated_block)

    if check_only:
        if current_content != updated_content:
            sys.stderr.write(
                "README resource section is out of date. Run\n"
                "  python scripts/generate_readme_resources.py\n"
                "to update it.\n"
            )
            return 1
        return 0

    README_PATH.write_text(updated_content, encoding="utf-8")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ensure README documentation resources are synchronized."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the README requires regeneration.",
    )
    args = parser.parse_args()
    return sync_readme(check_only=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
