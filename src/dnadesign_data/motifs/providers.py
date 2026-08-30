"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/motifs/providers.py

Declares the bounded registry of proven motif-source adapter capabilities.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

from pathlib import Path

from dnadesign_data.catalog.regulatory_parts import (
    MotifSourceFile,
    known_motif_source_files,
)
from dnadesign_data.motifs.contracts import (
    MODEL_SCHEMA,
    SITE_SET_SCHEMA,
    MotifExportError,
    reject_symbolic_link_ancestors,
)

_PROVIDERS: tuple[dict[str, object], ...] = (
    {
        "provider_id": "meme_probability_matrix_v1",
        "input_kind": "meme_probability_matrix",
        "output_schema": MODEL_SCHEMA,
        "materializes_motif_model": True,
        "network_access": False,
    },
    {
        "provider_id": "jaspar_count_matrix_v1",
        "input_kind": "jaspar_count_matrix",
        "output_schema": MODEL_SCHEMA,
        "materializes_motif_model": True,
        "network_access": False,
    },
    {
        "provider_id": "regulondb_tf_riset_sites_v1",
        "input_kind": "regulondb_tf_riset_table",
        "output_schema": SITE_SET_SCHEMA,
        "materializes_motif_model": False,
        "network_access": False,
    },
)


def list_motif_source_providers() -> list[dict[str, object]]:
    """Return JSON-ready descriptions of implemented provider contracts."""

    return [dict(provider) for provider in _PROVIDERS]


def resolve_catalog_source(
    source_path: str | Path,
    *,
    source_descriptor_id: str,
    expected_parser_hint: str,
    data_root: str | Path | None,
) -> tuple[Path, MotifSourceFile]:
    """Resolve one selected source against its catalog-owned path and policy."""

    matches = [
        descriptor
        for descriptor in known_motif_source_files()
        if descriptor.source_id == source_descriptor_id
    ]
    if len(matches) != 1:
        raise MotifExportError(
            f"unknown motif source descriptor {source_descriptor_id!r}"
        )
    descriptor = matches[0]
    if descriptor.parser_hint != expected_parser_hint:
        raise MotifExportError(
            f"source descriptor {source_descriptor_id!r} is not compatible with this provider"
        )
    root = Path(data_root) if data_root is not None else None
    authority_path = descriptor.absolute_path(root)
    source = Path(source_path)
    reject_symbolic_link_ancestors(source)
    reject_symbolic_link_ancestors(authority_path)
    try:
        resolved_source = source.resolve(strict=True)
        resolved_authority = authority_path.resolve(strict=True)
    except OSError as exc:
        raise MotifExportError(
            f"unable to resolve catalog source {source.name!r}"
        ) from exc
    if descriptor.file_format in {"meme_report_glob", "jaspar_count_glob"}:
        try:
            relative = resolved_source.relative_to(resolved_authority)
        except ValueError as exc:
            raise MotifExportError(
                f"source {source.name!r} is outside catalog descriptor {source_descriptor_id!r}"
            ) from exc
        if len(relative.parts) != 1 or not relative.match(descriptor.table):
            raise MotifExportError(
                f"source {source.name!r} does not match catalog descriptor {source_descriptor_id!r}"
            )
    elif resolved_source != resolved_authority:
        raise MotifExportError(
            f"source {source.name!r} does not match catalog descriptor {source_descriptor_id!r}"
        )
    return source, descriptor
