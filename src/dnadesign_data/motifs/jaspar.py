"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/motifs/jaspar.py

Exports one explicit JASPAR count matrix as a canonical motif model.

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
    MotifExportError,
    build_manifest,
    model_digest,
    read_source_bytes,
    sha256_bytes,
    validate_background,
    validate_motif_identity,
)
from dnadesign_data.motifs.matrix import count_matrix_sqrt_n_background_prior
from dnadesign_data.motifs.providers import resolve_catalog_source

PROVIDER_ID = "jaspar_count_matrix_v1"
MAX_MOTIF_WIDTH = 10_000
MAX_COUNT_VALUE = 1e15
MAX_COUNT_TOKEN_CHARS = 64
_COUNT_TOKEN = re.compile(r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
_BASE_ROW = re.compile(r"\s*([ACGT])\s*\[([^\]]+)\]\s*")


def _bounded_split(value: str, *, maxsplit: int) -> list[str]:
    """Materialize at most maxsplit + 1 whitespace-delimited fields."""

    return value.split(maxsplit=maxsplit)


def _parse_count_matrix(text: str, *, source_motif_id: str) -> list[list[float]]:
    lines = text.splitlines()
    if not lines:
        raise MotifExportError("JASPAR source is empty")
    header = re.fullmatch(r">(\S+)(?:[ \t]+[^\r\n]*)?", lines[0])
    if header is None or header.group(1) != source_motif_id:
        raise MotifExportError(
            "JASPAR source must contain exactly one matching motif header"
        )
    base_rows: dict[str, list[float]] = {}
    for line_number, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        match = _BASE_ROW.fullmatch(line)
        if match is None:
            raise MotifExportError(
                f"JASPAR source contains unsupported content on line {line_number}"
            )
        base, raw_values = match.groups()
        if base in base_rows:
            raise MotifExportError(f"JASPAR source repeats the {base!r} row")
        tokens = _bounded_split(raw_values, maxsplit=MAX_MOTIF_WIDTH)
        if not tokens or len(tokens) > MAX_MOTIF_WIDTH:
            raise MotifExportError(
                "JASPAR count rows must have one nonzero equal width within the supported bound"
            )
        if any(
            len(token) > MAX_COUNT_TOKEN_CHARS or _COUNT_TOKEN.fullmatch(token) is None
            for token in tokens
        ):
            raise MotifExportError(f"JASPAR {base!r} row contains an invalid count")
        values = [float(token) for token in tokens]
        if any(not math.isfinite(value) or value > MAX_COUNT_VALUE for value in values):
            raise MotifExportError(
                f"JASPAR {base!r} row contains a count outside the supported bound"
            )
        base_rows[base] = values
    if set(base_rows) != set(DNA_ALPHABET):
        raise MotifExportError("JASPAR source must contain A/C/G/T count rows")
    widths = {len(values) for values in base_rows.values()}
    if (
        len(widths) != 1
        or not widths
        or next(iter(widths)) == 0
        or next(iter(widths)) > MAX_MOTIF_WIDTH
    ):
        raise MotifExportError("JASPAR count rows must have one nonzero equal width")
    width = widths.pop()
    return [
        [base_rows[base][position] for base in DNA_ALPHABET]
        for position in range(width)
    ]


def build_jaspar_count_motif_export(
    source_path: str | Path,
    *,
    motif_id: str,
    source_motif_id: str,
    source_descriptor_id: str,
    background: list[float],
    data_root: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Build one source-bound count-matrix export with a sqrt(N) prior."""

    clean_motif_id = validate_motif_identity(motif_id, label="motif_id")
    clean_source_motif_id = validate_motif_identity(
        source_motif_id, label="source_motif_id"
    )
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
            f"JASPAR source {source.name!r} must be UTF-8 text"
        ) from exc
    counts = _parse_count_matrix(text, source_motif_id=clean_source_motif_id)
    canonical_background = validate_background(background)
    conversion = count_matrix_sqrt_n_background_prior(
        counts, background=canonical_background
    )
    source_digest = sha256_bytes(raw)
    model: dict[str, Any] = {
        "schema_version": MODEL_SCHEMA,
        "motif_id": clean_motif_id,
        "alphabet": list(DNA_ALPHABET),
        "probabilities": [list(row) for row in conversion.probabilities],
        "background": canonical_background,
        "source_digest": source_digest,
        "source_name": source.name,
        "conversion": {
            "schema_version": "motif-conversion/v2",
            "method": conversion.method,
            "source_motif_id": clean_source_motif_id,
            "position_observed_counts": list(conversion.position_observed_counts),
            "position_prior_masses": list(conversion.position_prior_masses),
            "position_denominators": list(conversion.position_denominators),
        },
    }
    manifest = build_manifest(
        provider_id=PROVIDER_ID,
        output_schema=MODEL_SCHEMA,
        artifact=model,
        source_name=source.name,
        source_digest=source_digest,
        source_descriptor_id=source_descriptor_id,
        source_revision=descriptor.release,
        redistribution_status=descriptor.redistribution_status,
        selection={
            "motif_id": clean_motif_id,
            "source_motif_id": clean_source_motif_id,
            "background": canonical_background,
            "conversion_contract": conversion.method,
        },
        model_digest=model_digest(model),
    )
    return {"artifact": model, "manifest": manifest}
