"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/motifs/contracts.py

Defines canonical motif-source export contracts and validation helpers.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
from pathlib import Path
from typing import Any

DNA_ALPHABET = ("A", "C", "G", "T")
EXPORT_SCHEMA = "dnadesign-data.motif-source-export/v1"
LEGACY_MODEL_SCHEMA = "motif-model/v1"
MODEL_SCHEMA = "motif-model/v2"
MODEL_SCHEMAS = frozenset({LEGACY_MODEL_SCHEMA, MODEL_SCHEMA})
SITE_SET_SCHEMA = "dnadesign-data.binding-site-set/v1"
LEGACY_SCORING_SEMANTICS = "normalized_llr_v1"
SCORING_SEMANTICS = "relative_pwm_attainment_v2"
MAX_SOURCE_BYTES = 64 * 1024 * 1024
SOURCE_PROBABILITY_ROUNDING_TOLERANCE = 2.0e-6
MOTIF_IDENTITY_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_.-]*")
REDISTRIBUTION_STATUSES = frozenset(
    {"redistributable", "private_storage", "link_only", "review_blocked"}
)


class MotifExportError(ValueError):
    """Raised when a motif-source export contract cannot be satisfied."""


def canonical_json_bytes(value: object) -> bytes:
    """Serialize a JSON value deterministically, including one final newline."""

    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("ascii")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def reject_symbolic_link_ancestors(path: str | Path) -> None:
    """Reject any existing symbolic-link component without resolving through it."""

    candidate = Path(path)
    absolute = candidate if candidate.is_absolute() else Path.cwd() / candidate
    for ancestor in reversed(absolute.parents):
        if ancestor.is_symlink():
            raise MotifExportError(
                f"path {candidate.name!r} has a symbolic-link ancestor"
            )


def read_source_bytes(
    path: str | Path,
    *,
    max_bytes: int = MAX_SOURCE_BYTES,
    label: str = "source",
) -> tuple[Path, bytes]:
    source = Path(path)
    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    reject_symbolic_link_ancestors(source)
    if source.is_symlink():
        raise MotifExportError(f"refusing symbolic-link source {source.name!r}")
    try:
        source_stat = source.stat(follow_symlinks=False)
    except FileNotFoundError as exc:
        raise MotifExportError(f"source {source.name!r} does not exist") from exc
    except OSError as exc:
        raise MotifExportError(f"unable to inspect source {source.name!r}") from exc
    if not stat.S_ISREG(source_stat.st_mode):
        raise MotifExportError(f"source {source.name!r} must be a regular file")
    if source_stat.st_size > max_bytes:
        raise MotifExportError(
            f"{label} {source.name!r} exceeds the {max_bytes}-byte limit"
        )
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(source, flags)
    except OSError as exc:
        raise MotifExportError(f"unable to read source {source.name!r}") from exc
    try:
        opened_stat = os.fstat(descriptor)
        if not stat.S_ISREG(opened_stat.st_mode):
            raise MotifExportError(f"source {source.name!r} must be a regular file")
        if (opened_stat.st_dev, opened_stat.st_ino) != (
            source_stat.st_dev,
            source_stat.st_ino,
        ):
            raise MotifExportError(f"source {source.name!r} changed before reading")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            raw = handle.read(max_bytes + 1)
    finally:
        os.close(descriptor)
    if len(raw) > max_bytes:
        raise MotifExportError(
            f"{label} {source.name!r} exceeds the {max_bytes}-byte limit"
        )
    return source, raw


def validate_redistribution_status(value: str) -> str:
    if value not in REDISTRIBUTION_STATUSES:
        allowed = ", ".join(sorted(REDISTRIBUTION_STATUSES))
        raise MotifExportError(f"redistribution_status must be one of: {allowed}")
    return value


def validate_identity(value: str, *, label: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise MotifExportError(f"{label} must be a non-empty string")
    return cleaned


def validate_motif_identity(value: str, *, label: str) -> str:
    """Validate the released Motif Balance public motif identity grammar."""

    if not isinstance(value, str) or MOTIF_IDENTITY_PATTERN.fullmatch(value) is None:
        raise MotifExportError(
            f"{label} must match the Motif Balance identity pattern "
            "[A-Za-z][A-Za-z0-9_.-]*"
        )
    return value


def validate_background(values: list[float]) -> list[float]:
    if len(values) != 4:
        raise MotifExportError("background must contain A/C/G/T values")
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0.0
        for value in values
    ):
        raise MotifExportError("background values must be finite and positive")
    total = math.fsum(values)
    if not math.isclose(total, 1.0, abs_tol=1.0e-6):
        raise MotifExportError("background values must sum to one")
    return [value / total for value in values]


def validate_probability_rows(rows: list[list[float]]) -> list[list[float]]:
    if not rows:
        raise MotifExportError("probability matrix must contain at least one row")
    normalized: list[list[float]] = []
    for index, row in enumerate(rows):
        if len(row) != 4:
            raise MotifExportError(f"probability row {index} must contain four values")
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0.0
            for value in row
        ):
            raise MotifExportError(
                f"probability row {index} must contain finite nonnegative values"
            )
        total = math.fsum(row)
        if total <= 0.0 or not math.isclose(
            total,
            1.0,
            abs_tol=SOURCE_PROBABILITY_ROUNDING_TOLERANCE,
        ):
            raise MotifExportError(f"probability row {index} must sum to one")
        normalized.append([float(value) / total for value in row])
    return normalized


def build_manifest(
    *,
    provider_id: str,
    output_schema: str,
    artifact: dict[str, Any],
    source_name: str,
    source_digest: str,
    source_descriptor_id: str,
    source_revision: str,
    redistribution_status: str,
    selection: dict[str, object],
    model_digest: str | None = None,
) -> dict[str, object]:
    artifact_digest = sha256_bytes(canonical_json_bytes(artifact))
    manifest: dict[str, object] = {
        "schema_version": EXPORT_SCHEMA,
        "provider_id": provider_id,
        "output_file": "artifact.json",
        "output_schema": output_schema,
        "artifact_sha256": artifact_digest,
        "source": {
            "artifact_name": source_name,
            "artifact_sha256": source_digest,
            "descriptor_id": validate_identity(
                source_descriptor_id, label="source_descriptor_id"
            ),
            "revision": validate_identity(source_revision, label="source_revision"),
            "redistribution_status": validate_redistribution_status(
                redistribution_status
            ),
        },
        "selection": selection,
    }
    if model_digest is not None:
        manifest["model_digest"] = model_digest
    return manifest


def scoring_semantics_for_model(schema_version: object) -> str:
    """Return the exact scoring authority bound by one model schema."""

    if schema_version not in MODEL_SCHEMAS:
        raise MotifExportError("model schema_version is unsupported")
    return (
        LEGACY_SCORING_SEMANTICS
        if schema_version == LEGACY_MODEL_SCHEMA
        else SCORING_SEMANTICS
    )


def model_digest(model: dict[str, Any]) -> str:
    schema_version = model["schema_version"]
    payload = {
        "schema_version": schema_version,
        "alphabet": model["alphabet"],
        "probabilities": model["probabilities"],
        "background": model["background"],
        "scoring_semantics": scoring_semantics_for_model(schema_version),
    }
    return sha256_bytes(canonical_json_bytes(payload).rstrip(b"\n"))
