"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/motifs/meme.py

Exports one explicit MEME probability matrix as a canonical motif model.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

from dnadesign_data.motifs.contracts import (
    DNA_ALPHABET,
    MODEL_SCHEMA,
    MODEL_SCHEMAS,
    MotifExportError,
    build_manifest,
    model_digest,
    read_source_bytes,
    sha256_bytes,
    validate_background,
    validate_motif_identity,
    validate_probability_rows,
)
from dnadesign_data.motifs.matrix import probability_matrix_background_mixture
from dnadesign_data.motifs.providers import resolve_catalog_source

PROVIDER_ID = "meme_probability_matrix_v1"
TARGET_BACKGROUND_POLICY = "explicit_target_background_v1"
TARGET_BACKGROUND_CONVERSION = "probability_matrix_target_background_v1"
TARGET_BACKGROUND_SELECTION_KEYS = frozenset(
    {
        "motif_id",
        "source_motif_id",
        "prior_weight",
        "source_background",
        "target_background",
        "target_background_policy",
    }
)
TARGET_BACKGROUND_CONVERSION_KEYS = frozenset(
    {
        "schema_version",
        "method",
        "prior_weight",
        "source_motif_id",
        "source_background",
        "target_background",
        "target_background_policy",
    }
)


def validate_target_background_provenance(
    selection: dict[str, Any],
    conversion: dict[str, Any],
    *,
    model_background: list[float],
) -> None:
    """Validate the explicit MEME source-to-target background contract."""

    if not isinstance(selection["source_background"], list) or not isinstance(
        selection["target_background"], list
    ):
        raise MotifExportError(
            "explicit target-background provenance must contain background lists"
        )
    source_background = validate_background(selection["source_background"])
    target_background = validate_background(selection["target_background"])
    if (
        source_background != selection["source_background"]
        or target_background != selection["target_background"]
        or target_background != model_background
        or conversion["source_background"] != source_background
        or conversion["target_background"] != target_background
        or selection["target_background_policy"] != TARGET_BACKGROUND_POLICY
        or conversion["target_background_policy"] != TARGET_BACKGROUND_POLICY
    ):
        raise MotifExportError(
            "explicit target-background provenance disagrees with the model"
        )
    prior_weight = selection["prior_weight"]
    conversion_prior = conversion["prior_weight"]
    if (
        isinstance(prior_weight, bool)
        or not isinstance(prior_weight, (int, float))
        or not math.isfinite(prior_weight)
        or prior_weight < 0.0
        or isinstance(conversion_prior, bool)
        or not isinstance(conversion_prior, (int, float))
        or not math.isfinite(conversion_prior)
        or conversion_prior != prior_weight
    ):
        raise MotifExportError("conversion prior_weight disagrees with selection")


def _parse_background(text: str) -> list[float]:
    match = re.search(
        r"Background letter frequencies[^\n]*\n\s*"
        r"A\s+([0-9.eE+-]+)\s+C\s+([0-9.eE+-]+)\s+"
        r"G\s+([0-9.eE+-]+)\s+T\s+([0-9.eE+-]+)",
        text,
    )
    if match is None:
        raise MotifExportError(
            "MEME source must declare A/C/G/T background frequencies"
        )
    try:
        values = [float(value) for value in match.groups()]
    except ValueError as exc:
        raise MotifExportError("MEME background contains a nonnumeric value") from exc
    return validate_background(values)


def _parse_matrix(text: str, *, source_motif_id: str) -> list[list[float]]:
    motif_matches = list(re.finditer(r"^MOTIF\s+(\S+).*$", text, re.MULTILINE))
    matches = [match for match in motif_matches if match.group(1) == source_motif_id]
    if len(matches) != 1:
        raise MotifExportError(
            f"MEME source must contain exactly one motif named {source_motif_id!r}; "
            f"found {len(matches)}"
        )
    selected = matches[0]
    selected_index = motif_matches.index(selected)
    end = (
        motif_matches[selected_index + 1].start()
        if selected_index + 1 < len(motif_matches)
        else len(text)
    )
    block = text[selected.end() : end]
    header = re.search(r"letter-probability matrix:.*\bw=\s*(\d+).*\n", block)
    if header is None:
        raise MotifExportError(
            f"MEME motif {source_motif_id!r} lacks a letter-probability matrix"
        )
    width = int(header.group(1))
    rows: list[list[float]] = []
    for line in block[header.end() :].splitlines():
        parts = line.split()
        if len(parts) != 4:
            if rows:
                break
            continue
        try:
            row = [float(value) for value in parts]
        except ValueError:
            if rows:
                break
            continue
        rows.append(row)
    if len(rows) != width:
        raise MotifExportError(
            f"MEME motif {source_motif_id!r} declares width {width} but has "
            f"{len(rows)} probability rows"
        )
    return validate_probability_rows(rows)


def _mix_prior(
    rows: list[list[float]],
    *,
    background: list[float],
    prior_weight: float,
) -> list[list[float]]:
    has_zero = any(value == 0.0 for row in rows for value in row)
    if has_zero and prior_weight <= 0.0:
        raise MotifExportError(
            "MEME matrix contains zero probabilities; provide a positive prior_weight"
        )
    if prior_weight == 0.0:
        return rows
    conversion = probability_matrix_background_mixture(
        rows,
        background=background,
        prior_weight=prior_weight,
    )
    return [list(row) for row in conversion.probabilities]


def build_meme_motif_export(
    source_path: str | Path,
    *,
    motif_id: str,
    source_motif_id: str,
    source_descriptor_id: str,
    prior_weight: float,
    background: list[float] | None = None,
    model_schema: str = MODEL_SCHEMA,
    data_root: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Build a deterministic export for one explicitly selected MEME motif."""

    clean_motif_id = validate_motif_identity(motif_id, label="motif_id")
    clean_source_motif_id = validate_motif_identity(
        source_motif_id, label="source_motif_id"
    )
    if model_schema not in MODEL_SCHEMAS:
        raise MotifExportError("model_schema is unsupported")
    source_path, descriptor = resolve_catalog_source(
        source_path,
        source_descriptor_id=source_descriptor_id,
        expected_parser_hint=PROVIDER_ID,
        data_root=data_root,
    )
    source, raw = read_source_bytes(source_path)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MotifExportError(
            f"MEME source {source.name!r} must be UTF-8 text"
        ) from exc
    alphabet = re.search(r"^ALPHABET=\s*(\S+)\s*$", text, re.MULTILINE)
    if alphabet is None or alphabet.group(1) != "ACGT":
        raise MotifExportError("MEME source alphabet must be exactly ACGT")
    source_background = _parse_background(text)
    target_background = (
        source_background if background is None else validate_background(background)
    )
    rows = _parse_matrix(text, source_motif_id=clean_source_motif_id)
    probabilities = _mix_prior(
        rows, background=target_background, prior_weight=prior_weight
    )
    conversion: dict[str, object] | None = None
    if background is not None:
        conversion = {
            "schema_version": "motif-conversion/v2",
            "method": TARGET_BACKGROUND_CONVERSION,
            "prior_weight": prior_weight,
            "source_motif_id": clean_source_motif_id,
            "source_background": source_background,
            "target_background": target_background,
            "target_background_policy": TARGET_BACKGROUND_POLICY,
        }
    elif prior_weight > 0.0:
        conversion = {
            "schema_version": "motif-conversion/v1",
            "method": "probability_matrix_prior_mixture_v1",
            "prior_weight": prior_weight,
            "source_motif_id": clean_source_motif_id,
        }
    source_digest = sha256_bytes(raw)
    model: dict[str, Any] = {
        "schema_version": model_schema,
        "motif_id": clean_motif_id,
        "alphabet": list(DNA_ALPHABET),
        "probabilities": probabilities,
        "background": target_background,
        "source_digest": source_digest,
        "source_name": source.name,
        "conversion": conversion,
    }
    selection: dict[str, object] = {
        "motif_id": clean_motif_id,
        "source_motif_id": clean_source_motif_id,
        "prior_weight": prior_weight,
    }
    if background is not None:
        selection.update(
            {
                "source_background": source_background,
                "target_background": target_background,
                "target_background_policy": TARGET_BACKGROUND_POLICY,
            }
        )
    manifest = build_manifest(
        provider_id=PROVIDER_ID,
        output_schema=model_schema,
        artifact=model,
        source_name=source.name,
        source_digest=source_digest,
        source_descriptor_id=source_descriptor_id,
        source_revision=descriptor.release,
        redistribution_status=descriptor.redistribution_status,
        selection=selection,
        model_digest=model_digest(model),
    )
    return {"artifact": model, "manifest": manifest}
