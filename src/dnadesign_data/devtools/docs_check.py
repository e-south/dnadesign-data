"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/devtools/docs_check.py

Checks repository documentation routing contracts.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MAX_ROUTER_LINES = 120
MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def check_docs(root: Path | None = None) -> list[str]:
    base = ROOT if root is None else root
    errors: list[str] = []
    _check_required_paths(base, errors)
    _check_router_lengths(base, errors)
    _check_readme_contract(base, errors)
    _check_markdown_links(base, errors)
    return errors


def main(argv: Sequence[str] | None = None) -> int:
    del argv
    errors = check_docs()
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("documentation checks passed")
    return 0


def _check_required_paths(base: Path, errors: list[str]) -> None:
    required_paths = [
        "AGENTS.md",
        "ARCHITECTURE.md",
        "DESIGN.md",
        "SECURITY.md",
        "QUALITY_SCORE.md",
        "README.md",
        "LICENSE",
        "THIRD_PARTY_DATA.md",
        "PUBLIC_DATA_INVENTORY.json",
        "docs/README.md",
        "docs/dev/README.md",
        "docs/data-sources/README.md",
        "docs/functional-annotations.md",
        "docs/package-apis.md",
        "assets/dnadesign-data-wordmark.svg",
        "sources/databases/jaspar/2026/rights.json",
        "sources/databases/hocomoco/14/rights.json",
        "generated/motif_models/development-exposed-v2",
        "generated/motif_models/jaspar-2026-counts",
        "generated/motif_models/pools/development-exposed-v2.request.json",
        "generated/motif_models/pools/formal-fresh-v2.request.json",
    ]
    for relative_path in required_paths:
        if not (base / relative_path).exists():
            errors.append(f"missing required documentation path: {relative_path}")


def _check_router_lengths(base: Path, errors: list[str]) -> None:
    for relative_path in ("README.md", "AGENTS.md"):
        path = base / relative_path
        if not path.exists():
            continue
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > MAX_ROUTER_LINES:
            errors.append(
                f"{relative_path} has {line_count} lines; keep it <= {MAX_ROUTER_LINES}"
            )


def _check_readme_contract(base: Path, errors: list[str]) -> None:
    readme_path = base / "README.md"
    if not readme_path.exists():
        return
    text = readme_path.read_text(encoding="utf-8")
    required_snippets = (
        "assets/dnadesign-data-wordmark.svg",
        "docs/data-sources/README.md",
        "docs/functional-annotations.md",
        "https://github.com/e-south/dnadesign",
    )
    for snippet in required_snippets:
        if snippet not in text:
            errors.append(f"README.md missing required route or command: {snippet}")
    if "## Data Sources by Category" in text:
        errors.append(
            "README.md must route source catalog details to docs/data-sources/"
        )


def _check_markdown_links(base: Path, errors: list[str]) -> None:
    for path in _iter_markdown_files(base):
        text = path.read_text(encoding="utf-8")
        for raw_target in MARKDOWN_LINK_PATTERN.findall(text):
            target = raw_target.split("#", 1)[0]
            if not target or _is_external_link(target):
                continue
            if target.startswith("mailto:"):
                continue
            link_path = (path.parent / target).resolve()
            try:
                link_path.relative_to(base.resolve())
            except ValueError:
                errors.append(
                    f"{path.relative_to(base)} links outside repository: {raw_target}"
                )
                continue
            if not link_path.exists():
                errors.append(
                    f"{path.relative_to(base)} has missing link target: {raw_target}"
                )


def _iter_markdown_files(base: Path) -> Iterable[Path]:
    ignored_parts = {".git", ".venv", ".pytest_cache", ".ruff_cache"}
    for path in base.rglob("*.md"):
        if ignored_parts.intersection(path.parts):
            continue
        yield path


def _is_external_link(target: str) -> bool:
    return target.startswith(("http://", "https://", "#"))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
