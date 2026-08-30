"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/motifs/pool_receipt_validation.py

Validates persisted pool receipt fields against already-opened local bundle bytes.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

from typing import Any

from dnadesign_data.motifs.contracts import MotifExportError, sha256_bytes
from dnadesign_data.motifs.receipt_validation import (
    RECEIPT_KEYS,
    REVISION_PATTERN,
    validate_artifact_ref,
)


def _text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise MotifExportError(f"{label} must be a non-empty string")
    return value


def validate_offline_pool_receipt(
    receipt: dict[str, Any],
    *,
    artifact_raw: bytes,
    artifact: dict[str, Any],
    bundle_path: str,
    manifest: dict[str, Any],
    source: dict[str, Any],
    conversion_contract: str,
    motif_id: str,
) -> None:
    """Bind one receipt to local bytes without consulting mutable authority."""

    if set(receipt) != RECEIPT_KEYS:
        raise MotifExportError("local motif receipt keys are incomplete or unknown")
    owner_revision = _text(receipt["owner_revision"], label="receipt owner_revision")
    if REVISION_PATTERN.fullmatch(owner_revision) is None:
        raise MotifExportError("receipt owner_revision must be a Git revision")
    canonical_ref = _text(
        receipt["canonical_artifact_ref"], label="canonical_artifact_ref"
    )
    _kind, ref_path = validate_artifact_ref(
        canonical_ref, owner_revision=owner_revision
    )
    if ref_path != f"{bundle_path}/artifact.json":
        raise MotifExportError("local motif receipt references a different artifact")
    expected = {
        "schema": "dnadesign-data.motif-export-receipt/v1",
        "status": "accepted",
        "owner_repository": "e-south/dnadesign-data",
        "motif_id": motif_id,
        "source_descriptor_id": source["descriptor_id"],
        "source_revision": source["revision"],
        "source_artifact_sha256": source["artifact_sha256"],
        "canonical_file_sha256": sha256_bytes(artifact_raw),
        "canonical_media_type": "application/json",
        "canonical_schema": artifact["schema_version"],
        "model_digest": manifest["model_digest"],
        "conversion_contract": conversion_contract,
        "redistribution_status": source["redistribution_status"],
    }
    if any(receipt[field] != value for field, value in expected.items()):
        raise MotifExportError("local motif receipt does not bind its bundle")
