"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/motifs/replay.py

Replays source-to-model conversion for receipt issuance.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dnadesign_data.catalog.regulatory_parts import MotifSourceFile
from dnadesign_data.motifs.contracts import MotifExportError


def replay_source_conversion(
    artifact: dict[str, Any],
    manifest: dict[str, Any],
    descriptor: MotifSourceFile,
    *,
    data_root: str | Path,
) -> None:
    """Rebuild canonical scientific fields from the admitted catalog source."""

    source_name = manifest["source"]["artifact_name"]
    source_path = descriptor.absolute_path(data_root)
    if descriptor.file_format in {"meme_report_glob", "jaspar_count_glob"}:
        source_path = source_path / source_name
    selection = manifest["selection"]
    provider_id = manifest["provider_id"]
    if provider_id == "meme_probability_matrix_v1":
        from dnadesign_data.motifs.meme import build_meme_motif_export

        replayed = build_meme_motif_export(
            source_path,
            motif_id=selection["motif_id"],
            source_motif_id=selection["source_motif_id"],
            source_descriptor_id=descriptor.source_id,
            prior_weight=selection["prior_weight"],
            model_schema=artifact["schema_version"],
            data_root=data_root,
        )
    elif provider_id == "jaspar_count_matrix_v1":
        from dnadesign_data.motifs.jaspar import build_jaspar_count_motif_export

        replayed = build_jaspar_count_motif_export(
            source_path,
            motif_id=selection["motif_id"],
            source_motif_id=selection["source_motif_id"],
            source_descriptor_id=descriptor.source_id,
            background=selection["background"],
            data_root=data_root,
        )
    else:  # pragma: no cover - provider already validated
        raise MotifExportError("source conversion replay provider is unsupported")
    if (
        replayed["artifact"] != artifact
        or replayed["manifest"]["selection"] != selection
    ):
        raise MotifExportError(
            "source conversion replay disagrees with canonical scientific fields"
        )
