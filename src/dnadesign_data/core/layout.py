"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/core/layout.py

Centralizes source and generated-data repository layout helpers.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

SOURCES_ROOT = PurePosixPath("sources")
DATABASE_SOURCES_ROOT = SOURCES_ROOT / "databases"
LITERATURE_SOURCES_ROOT = SOURCES_ROOT / "literature"
GENERATED_ROOT = PurePosixPath("generated")
FUNCTIONAL_ANNOTATIONS_ROOT = GENERATED_ROOT / "functional_annotations"


def default_data_root() -> Path:
    """Return the repository root for this installed source checkout."""

    return Path(__file__).resolve().parents[3]


def posix_path(path: PurePosixPath) -> str:
    return path.as_posix()


def database_release_path(provider: str, release: str, *parts: str) -> str:
    _require_safe_path_part(provider, "provider")
    _require_safe_path_part(release, "release")
    return posix_path(
        DATABASE_SOURCES_ROOT / provider / release / PurePosixPath(*parts)
    )


def regulondb_release_path(release: str, *parts: str) -> str:
    return database_release_path("regulondb", release, *parts)


def ecocyc_release_path(release: str, *parts: str) -> str:
    return database_release_path("ecocyc", release, *parts)


def literature_path(citation_slug: str, *parts: str) -> str:
    _require_safe_path_part(citation_slug, "citation_slug")
    return posix_path(LITERATURE_SOURCES_ROOT / citation_slug / PurePosixPath(*parts))


def gene_ontology_release_path(release: str, *parts: str) -> str:
    _require_safe_path_part(release, "release")
    return posix_path(
        FUNCTIONAL_ANNOTATIONS_ROOT / "gene_ontology" / release / PurePosixPath(*parts)
    )


def biocyc_kb_path(kb_version: str, *parts: str) -> str:
    _require_safe_path_part(kb_version, "kb_version")
    return posix_path(
        FUNCTIONAL_ANNOTATIONS_ROOT / "biocyc" / kb_version / PurePosixPath(*parts)
    )


def _require_safe_path_part(value: str, field: str) -> None:
    if not value or "/" in value or "\\" in value:
        raise ValueError(f"{field} must be a non-empty single path segment")
