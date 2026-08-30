from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import dnadesign_data.motifs.receipts as receipt_module
from dnadesign_data.motifs import (
    MotifExportError,
    build_meme_motif_export,
    build_motif_export_receipt,
    storage_authority,
    write_motif_source_export,
)
from dnadesign_data.motifs.contracts import canonical_json_bytes
from dnadesign_data.motifs.receipt_validation import revalidate_motif_export_receipt


def _digest(raw: bytes) -> str:
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def _private_storage_export(root: Path) -> tuple[Path, Path]:
    source = root / "sources/literature/OMalley_et_al/escherichia_coli_motifs/acrR.txt"
    source.parent.mkdir(parents=True)
    source.write_text(
        """MEME version 5
ALPHABET= ACGT
Background letter frequencies
A 0.25 C 0.25 G 0.25 T 0.25
MOTIF acrR
letter-probability matrix: alength= 4 w= 2 nsites= 3 E= 0
0.7 0.1 0.1 0.1
0.1 0.2 0.3 0.4
""",
        encoding="utf-8",
    )
    export = build_meme_motif_export(
        source,
        motif_id="acrR",
        source_motif_id="acrR",
        source_descriptor_id="omalley_2021_ecoli_meme",
        prior_weight=0.1,
        data_root=root,
    )
    bundle = write_motif_source_export(export, root / "models/acrR")
    return source, bundle


def _storage_manifest(root: Path, source: Path, bundle: Path, revision: str) -> Path:
    resources = []
    for path, role in ((source, "input"), (bundle / "artifact.json", "artifact")):
        resources.append(
            {
                "path": path.relative_to(root).as_posix(),
                "digest": _digest(path.read_bytes()),
                "role": role,
            }
        )
    manifest = {
        "schema": "dnadesign.storage-object/v1",
        "storage_id": "omalley-motif-models-v1",
        "owner_repository": "dnadesign-data",
        "owner_tool": "dnadesign-data",
        "object_kind": "store",
        "content_schema": "dnadesign-data.private-motif-models",
        "content_schema_version": "1",
        "producer_revision": revision,
        "storage_class": "authoritative",
        "retention_policy": "retain",
        "demo": False,
        "resources": resources,
    }
    path = root / "storage.object.json"
    path.write_bytes(canonical_json_bytes(manifest))
    return path


def _fake_verified_object(root: Path, manifest_path: Path) -> SimpleNamespace:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    resources = tuple(
        SimpleNamespace(
            relative_path=item["path"],
            path=root / item["path"],
            digest=item["digest"],
            role=SimpleNamespace(value=item["role"]),
        )
        for item in payload["resources"]
    )
    manifest = SimpleNamespace(
        **{
            key: SimpleNamespace(value=value)
            if key in {"object_kind", "storage_class"}
            else value
            for key, value in payload.items()
            if key not in {"resources", "schema"}
        },
        schema=payload["schema"],
    )
    return SimpleNamespace(
        root=root,
        manifest_path=manifest_path,
        manifest_digest=_digest(manifest_path.read_bytes()),
        manifest=manifest,
        resources=resources,
    )


def test_private_omalley_export_receives_storage_backed_owner_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    revision = "a" * 40
    source, bundle = _private_storage_export(tmp_path)
    manifest_path = _storage_manifest(tmp_path, source, bundle, revision)
    verified = _fake_verified_object(tmp_path, manifest_path)
    monkeypatch.setattr(
        storage_authority, "_load_storage_verifier", lambda: lambda _root: verified
    )
    monkeypatch.setattr(
        receipt_module,
        "_query_canonical_remote_revisions",
        lambda: frozenset({revision}),
    )

    receipt = build_motif_export_receipt(
        bundle,
        owner_revision=revision,
        canonical_artifact_ref=(
            "storage:dnadesign-data/omalley-motif-models-v1"
            f"@{verified.manifest_digest}#models/acrR/artifact.json"
        ),
        owner_repository_path=tmp_path / "unused-for-storage",
        data_root=tmp_path,
    )

    assert receipt["status"] == "accepted"
    assert receipt["motif_id"] == "acrR"
    assert receipt["redistribution_status"] == "private_storage"
    assert (
        receipt["source_artifact_sha256"]
        == hashlib.sha256(source.read_bytes()).hexdigest()
    )
    assert (
        receipt["canonical_file_sha256"]
        == hashlib.sha256((bundle / "artifact.json").read_bytes()).hexdigest()
    )
    assert (
        revalidate_motif_export_receipt(
            bundle,
            receipt,
            owner_repository_path=tmp_path / "unused-for-storage",
            data_root=tmp_path,
        )
        == receipt
    )


def test_private_storage_receipt_rejects_member_digest_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    revision = "a" * 40
    source, bundle = _private_storage_export(tmp_path)
    manifest_path = _storage_manifest(tmp_path, source, bundle, revision)
    verified = _fake_verified_object(tmp_path, manifest_path)
    verified.resources[0].digest = "sha256:" + "0" * 64
    monkeypatch.setattr(
        storage_authority, "_load_storage_verifier", lambda: lambda _root: verified
    )
    monkeypatch.setattr(
        receipt_module,
        "_query_canonical_remote_revisions",
        lambda: frozenset({revision}),
    )

    with pytest.raises(MotifExportError, match="source member digest"):
        build_motif_export_receipt(
            bundle,
            owner_revision=revision,
            canonical_artifact_ref=(
                "storage:dnadesign-data/omalley-motif-models-v1"
                f"@{verified.manifest_digest}#models/acrR/artifact.json"
            ),
            owner_repository_path=tmp_path / "unused-for-storage",
            data_root=tmp_path,
        )
