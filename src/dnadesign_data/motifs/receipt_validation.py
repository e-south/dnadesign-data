"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/motifs/receipt_validation.py

Strictly revalidates persisted motif-export receipts against owner authority.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any

from dnadesign_data.motifs.contracts import MODEL_SCHEMAS, MotifExportError

REVISION_PATTERN = re.compile(r"[0-9a-f]{40}")
_DIGEST = re.compile(r"[0-9a-f]{64}")
_GIT_REF = re.compile(
    r"git:e-south/dnadesign-data@(?P<revision>[0-9a-f]{40})#(?P<path>.+)"
)
_STORAGE_REF = re.compile(
    r"storage:dnadesign-data/(?P<object>[a-z0-9][a-z0-9-]*)"
    r"@sha256:(?P<digest>[0-9a-f]{64})#(?P<path>.+)"
)
RECEIPT_KEYS = frozenset(
    {
        "schema",
        "status",
        "owner_repository",
        "owner_revision",
        "motif_id",
        "source_descriptor_id",
        "source_revision",
        "source_artifact_sha256",
        "canonical_artifact_ref",
        "canonical_file_sha256",
        "canonical_media_type",
        "canonical_schema",
        "model_digest",
        "conversion_contract",
        "redistribution_status",
    }
)


def validate_artifact_ref(value: str, *, owner_revision: str) -> tuple[str, str]:
    """Validate one fixed-owner canonical Git or Storage reference."""

    match = _GIT_REF.fullmatch(value)
    kind = "git"
    if match is None:
        match = _STORAGE_REF.fullmatch(value)
        kind = "storage"
    if match is None:
        raise MotifExportError(
            "canonical_artifact_ref must be a content-bound dnadesign-data Git or Storage reference"
        )
    ref_path = match.group("path")
    parts = ref_path.split("/")
    if (
        "\\" in ref_path
        or ref_path.startswith("/")
        or any(part in {"", ".", ".."} for part in parts)
        or str(PurePosixPath(ref_path)) != ref_path
        or any(re.fullmatch(r"[A-Za-z0-9._-]+", part) is None for part in parts)
    ):
        raise MotifExportError("canonical_artifact_ref contains a noncanonical path")
    if kind == "git" and match.group("revision") != owner_revision:
        raise MotifExportError(
            "canonical_artifact_ref Git revision must equal owner_revision"
        )
    return kind, ref_path


def _exact_receipt(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != RECEIPT_KEYS:
        raise MotifExportError(
            f"receipt keys must be exactly: {', '.join(sorted(RECEIPT_KEYS))}"
        )
    return value


def _text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise MotifExportError(f"{label} must be a non-empty string")
    return value


def revalidate_motif_export_receipt(
    export_dir: str | Path,
    receipt: object,
    *,
    owner_repository_path: str | Path,
    data_root: str | Path,
) -> dict[str, object]:
    """Reissue one receipt from authority and require exact receipt semantics."""

    admitted = _exact_receipt(receipt)
    if admitted["schema"] != "dnadesign-data.motif-export-receipt/v1":
        raise MotifExportError("receipt schema is unsupported")
    if admitted["status"] != "accepted":
        raise MotifExportError("receipt status must be accepted")
    if admitted["owner_repository"] != "e-south/dnadesign-data":
        raise MotifExportError("receipt owner_repository is not canonical")
    owner_revision = _text(admitted["owner_revision"], label="receipt owner_revision")
    if REVISION_PATTERN.fullmatch(owner_revision) is None:
        raise MotifExportError("receipt owner_revision must be a 40-character revision")
    canonical_artifact_ref = _text(
        admitted["canonical_artifact_ref"], label="receipt canonical_artifact_ref"
    )
    validate_artifact_ref(canonical_artifact_ref, owner_revision=owner_revision)
    for field in (
        "source_artifact_sha256",
        "canonical_file_sha256",
        "model_digest",
    ):
        if _DIGEST.fullmatch(_text(admitted[field], label=f"receipt {field}")) is None:
            raise MotifExportError(f"receipt {field} must be a SHA-256 digest")
    if admitted["canonical_media_type"] != "application/json":
        raise MotifExportError("receipt canonical_media_type is unsupported")
    if admitted["canonical_schema"] not in MODEL_SCHEMAS:
        raise MotifExportError("receipt canonical_schema is unsupported")
    from dnadesign_data.motifs.receipts import build_motif_export_receipt

    expected = build_motif_export_receipt(
        export_dir,
        owner_revision=owner_revision,
        canonical_artifact_ref=canonical_artifact_ref,
        owner_repository_path=owner_repository_path,
        data_root=data_root,
    )
    if admitted != expected:
        raise MotifExportError("receipt fields disagree with revalidated authority")
    return expected
