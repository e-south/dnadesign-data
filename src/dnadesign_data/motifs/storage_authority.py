"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/motifs/storage_authority.py

Verifies private motif source and model members through Storage authority.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from dnadesign_data.motifs.contracts import (
    MotifExportError,
    read_source_bytes,
    sha256_bytes,
)

_STORAGE_REF = re.compile(
    r"storage:dnadesign-data/(?P<object>[a-z0-9][a-z0-9-]*)"
    r"@sha256:(?P<digest>[0-9a-f]{64})#(?P<path>.+)"
)
_CONTENT_SCHEMA = "dnadesign-data.private-motif-models"


def _load_storage_verifier() -> Callable[[Path], Any]:
    try:
        from dnadesign.contracts.storage_objects import verify_storage_object
    except ImportError as exc:
        raise MotifExportError(
            "private-storage receipts require the dnadesign Storage verifier"
        ) from exc
    return verify_storage_object


def _enum_value(value: object) -> object:
    return getattr(value, "value", value)


def verify_private_motif_storage_authority(
    storage_root: str | Path,
    *,
    canonical_artifact_ref: str,
    owner_revision: str,
    source_relative_path: str,
    source_bytes: bytes,
    artifact_bytes: bytes,
) -> None:
    """Bind one private motif export to two exact members of a Storage object."""

    match = _STORAGE_REF.fullmatch(canonical_artifact_ref)
    if match is None:
        raise MotifExportError("private motif receipt requires a Storage reference")
    root = Path(storage_root)
    try:
        verified = _load_storage_verifier()(root)
    except MotifExportError:
        raise
    except Exception as exc:
        raise MotifExportError("Storage object verification failed") from exc

    manifest = verified.manifest
    expected_manifest_digest = f"sha256:{match.group('digest')}"
    if Path(verified.root) != root.resolve():
        raise MotifExportError("Storage verifier returned a different object root")
    if verified.manifest_digest != expected_manifest_digest:
        raise MotifExportError(
            "Storage reference manifest digest disagrees with authority"
        )
    if manifest.schema != "dnadesign.storage-object/v1":
        raise MotifExportError("Storage object schema is unsupported")
    if manifest.storage_id != match.group("object"):
        raise MotifExportError(
            "Storage reference object identity disagrees with authority"
        )
    if (
        manifest.owner_repository != "dnadesign-data"
        or manifest.owner_tool != "dnadesign-data"
        or _enum_value(manifest.object_kind) != "store"
        or manifest.content_schema != _CONTENT_SCHEMA
        or manifest.content_schema_version != "1"
        or manifest.producer_revision != owner_revision
        or _enum_value(manifest.storage_class) != "authoritative"
        or manifest.demo is not False
    ):
        raise MotifExportError(
            "Storage object is not an authoritative dnadesign-data private motif store"
        )

    members = {resource.relative_path: resource for resource in verified.resources}
    artifact_relative_path = match.group("path")
    source_member = members.get(source_relative_path)
    artifact_member = members.get(artifact_relative_path)
    if source_member is None:
        raise MotifExportError("Storage object lacks the declared motif source member")
    if artifact_member is None:
        raise MotifExportError(
            "Storage object lacks the canonical motif artifact member"
        )
    expected_source_digest = f"sha256:{sha256_bytes(source_bytes)}"
    expected_artifact_digest = f"sha256:{sha256_bytes(artifact_bytes)}"
    if (
        _enum_value(source_member.role) != "input"
        or source_member.digest != expected_source_digest
    ):
        raise MotifExportError("Storage source member digest or role disagrees")
    if (
        _enum_value(artifact_member.role) != "artifact"
        or artifact_member.digest != expected_artifact_digest
    ):
        raise MotifExportError("Storage artifact member digest or role disagrees")

    _source_path, admitted_source = read_source_bytes(source_member.path)
    _artifact_path, admitted_artifact = read_source_bytes(artifact_member.path)
    if admitted_source != source_bytes:
        raise MotifExportError("Storage source member bytes changed after verification")
    if admitted_artifact != artifact_bytes:
        raise MotifExportError(
            "Storage artifact member bytes changed after verification"
        )
