"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/tests/test_publication_check.py

Tests publication-rights gates for changed literature packages.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from dnadesign_data.devtools.publication_check import (
    ChangedPath,
    _changed_paths,
    _validate_generated_motif_inventory,
    check_publication,
)


def test_initial_push_uses_empty_tree_when_before_is_all_zero(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Fixture"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "fixture@example.test"],
        cwd=tmp_path,
        check=True,
    )
    source = tmp_path / "sources/databases/example/1/model.tsv"
    source.parent.mkdir(parents=True)
    source.write_text("record\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "root"], cwd=tmp_path, check=True)

    changes = _changed_paths(tmp_path, "0" * 40)

    assert changes == (ChangedPath("A", "sources/databases/example/1/model.tsv"),)


def _write_metadata(root: Path, *, status: str) -> Path:
    source = root / "sources" / "literature" / "Example_et_al"
    source.mkdir(parents=True)
    metadata = source / "metadata.json"
    metadata.write_text(
        json.dumps(
            {
                "source_type": "primary_literature",
                "redistribution_status": status,
                "redistribution_note": "Test-only rights posture.",
                **(
                    {
                        "redistribution_basis": "Example open license.",
                        "redistribution_basis_url": "https://example.test/license",
                        "redistribution_reviewed_on": "2026-08-26",
                        "redistribution_reviewer": "test-maintainer",
                    }
                    if status == "redistributable"
                    else {}
                ),
            }
        ),
        encoding="utf-8",
    )
    return source


def test_review_required_source_rejects_new_raw_payload(tmp_path: Path) -> None:
    source = _write_metadata(tmp_path, status="review_required")
    raw = source / "raw" / "supplement.xlsx"
    raw.parent.mkdir()
    raw.write_bytes(b"private source bytes")

    errors = check_publication(
        tmp_path,
        changed_paths=(ChangedPath("A", raw.relative_to(tmp_path).as_posix()),),
    )

    assert errors == [
        (
            "sources/literature/Example_et_al/raw/supplement.xlsx: "
            "review_required literature may publish only package metadata, README.md, "
            "and text provenance descriptors"
        )
    ]


def test_link_only_source_allows_metadata_and_provenance_only(tmp_path: Path) -> None:
    source = _write_metadata(tmp_path, status="link_only")
    provenance = source / "raw" / "provenance" / "intake.json"
    provenance.parent.mkdir(parents=True)
    provenance.write_text(
        '{"source_url":"https://example.test/source"}\n', encoding="utf-8"
    )

    errors = check_publication(
        tmp_path,
        changed_paths=(
            ChangedPath(
                "M", source.relative_to(tmp_path).as_posix() + "/metadata.json"
            ),
            ChangedPath("A", provenance.relative_to(tmp_path).as_posix()),
        ),
    )

    assert errors == []


def test_legacy_unclassified_source_is_frozen_until_promoted(tmp_path: Path) -> None:
    source = _write_metadata(tmp_path, status="legacy_unclassified")
    readme = source / "README.md"
    readme.write_text("changed\n", encoding="utf-8")

    errors = check_publication(
        tmp_path,
        changed_paths=(ChangedPath("M", readme.relative_to(tmp_path).as_posix()),),
    )

    assert errors == [
        (
            "sources/literature/Example_et_al/README.md: legacy_unclassified "
            "literature is frozen until redistribution_status is promoted"
        )
    ]


def test_every_metadata_record_requires_explicit_rights_posture(tmp_path: Path) -> None:
    source = tmp_path / "sources" / "literature" / "Example_et_al"
    source.mkdir(parents=True)
    (source / "metadata.json").write_text(
        '{"source_type":"primary_literature"}\n',
        encoding="utf-8",
    )

    errors = check_publication(tmp_path, changed_paths=())

    assert errors == [
        (
            "sources/literature/Example_et_al/metadata.json: "
            "redistribution_status must be one of legacy_unclassified, link_only, "
            "redistributable, review_required"
        )
    ]


def test_metadata_rejects_duplicate_identity_keys(tmp_path: Path) -> None:
    source = tmp_path / "sources" / "literature" / "Example_et_al"
    source.mkdir(parents=True)
    (source / "metadata.json").write_text(
        '{"redistribution_status":"redistributable",'
        '"redistribution_status":"review_required",'
        '"redistribution_note":"ambiguous"}\n',
        encoding="utf-8",
    )

    errors = check_publication(tmp_path, changed_paths=())

    assert len(errors) == 1
    assert "duplicate key 'redistribution_status'" in errors[0]


def test_review_required_source_rejects_payload_at_package_root(tmp_path: Path) -> None:
    source = _write_metadata(tmp_path, status="review_required")
    payload = source / "supplement.xlsx"
    payload.write_bytes(b"private source bytes")

    errors = check_publication(
        tmp_path,
        changed_paths=(ChangedPath("A", payload.relative_to(tmp_path).as_posix()),),
    )

    assert len(errors) == 1
    assert "may publish only package metadata" in errors[0]


def test_review_required_source_rejects_binary_under_provenance(
    tmp_path: Path,
) -> None:
    source = _write_metadata(tmp_path, status="review_required")
    payload = source / "raw" / "provenance" / "source.pdf"
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"private source bytes")

    errors = check_publication(
        tmp_path,
        changed_paths=(ChangedPath("A", payload.relative_to(tmp_path).as_posix()),),
    )

    assert len(errors) == 1
    assert "may publish only package metadata" in errors[0]


def test_review_required_source_rejects_disguised_binary_provenance(
    tmp_path: Path,
) -> None:
    source = _write_metadata(tmp_path, status="review_required")
    payload = source / "raw" / "provenance" / "source.json"
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"%PDF private source bytes")

    errors = check_publication(
        tmp_path,
        changed_paths=(ChangedPath("A", payload.relative_to(tmp_path).as_posix()),),
    )

    assert len(errors) == 1
    assert "cannot read provenance descriptor JSON" in errors[0]


def test_deleting_review_required_payload_is_allowed(tmp_path: Path) -> None:
    source = _write_metadata(tmp_path, status="review_required")
    payload = source / "raw" / "source.pdf"

    errors = check_publication(
        tmp_path,
        changed_paths=(ChangedPath("D", payload.relative_to(tmp_path).as_posix()),),
    )

    assert errors == []


def test_deleting_metadata_while_package_remains_is_rejected(tmp_path: Path) -> None:
    source = _write_metadata(tmp_path, status="review_required")
    metadata = source / "metadata.json"
    metadata.unlink()
    (source / "README.md").write_text("# Source\n", encoding="utf-8")

    errors = check_publication(
        tmp_path,
        changed_paths=(ChangedPath("D", metadata.relative_to(tmp_path).as_posix()),),
    )

    assert errors == [
        f"{metadata.relative_to(tmp_path)}: metadata.json cannot be removed while the literature package remains"
    ]


def test_deleting_complete_literature_package_is_allowed(tmp_path: Path) -> None:
    source = _write_metadata(tmp_path, status="review_required")
    metadata = source / "metadata.json"
    metadata.unlink()
    source.rmdir()

    errors = check_publication(
        tmp_path,
        changed_paths=(ChangedPath("D", metadata.relative_to(tmp_path).as_posix()),),
    )

    assert errors == []


def test_redistributable_source_requires_review_evidence(tmp_path: Path) -> None:
    source = _write_metadata(tmp_path, status="review_required")
    metadata = source / "metadata.json"
    metadata.write_text(
        json.dumps(
            {
                "redistribution_status": "redistributable",
                "redistribution_note": "Unsubstantiated.",
            }
        ),
        encoding="utf-8",
    )

    errors = check_publication(tmp_path, changed_paths=())

    assert errors == [
        f"{metadata.relative_to(tmp_path)}: redistribution_basis must be a non-empty string",
        f"{metadata.relative_to(tmp_path)}: redistribution_reviewer must be a non-empty string",
        f"{metadata.relative_to(tmp_path)}: redistribution_basis_url must be an HTTPS URL",
        f"{metadata.relative_to(tmp_path)}: redistribution_reviewed_on must be a nonfuture ISO date",
    ]


def test_redistributable_source_with_review_evidence_allows_payload(
    tmp_path: Path,
) -> None:
    source = _write_metadata(tmp_path, status="redistributable")
    payload = source / "raw" / "source.pdf"
    payload.parent.mkdir()
    payload.write_bytes(b"publishable source bytes")

    errors = check_publication(
        tmp_path,
        changed_paths=(ChangedPath("A", payload.relative_to(tmp_path).as_posix()),),
    )

    assert errors == []


def _write_database_rights(root: Path, *, status: str) -> Path:
    release = root / "sources/databases/example/1.0"
    release.mkdir(parents=True)
    rights = release / "rights.json"
    rights.write_text(
        json.dumps(
            {
                "schema_version": "dnadesign-data.database-rights/v1",
                "database": "ExampleDB",
                "release": "1.0",
                "redistribution_status": status,
                "rights_url": "https://example.test/rights",
                "attribution": "ExampleDB release 1.0.",
                "reviewed_on": "2026-08-29",
                "reviewer": "test-maintainer",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    return release


def test_database_payload_requires_release_rights_and_attribution(
    tmp_path: Path,
) -> None:
    payload = tmp_path / "sources/databases/example/1.0/records.tsv"
    payload.parent.mkdir(parents=True)
    payload.write_text("record\n", encoding="utf-8")

    errors = check_publication(
        tmp_path,
        changed_paths=(ChangedPath("A", payload.relative_to(tmp_path).as_posix()),),
    )

    assert errors == [
        "sources/databases/example/1.0/records.tsv: database release is missing rights.json"
    ]


def test_database_rights_allow_only_redistributable_payloads(tmp_path: Path) -> None:
    release = _write_database_rights(tmp_path, status="redistributable")
    payload = release / "records.tsv"
    payload.write_text("record\n", encoding="utf-8")
    changed = (ChangedPath("A", payload.relative_to(tmp_path).as_posix()),)

    assert check_publication(tmp_path, changed_paths=changed) == []

    rights = release / "rights.json"
    value = json.loads(rights.read_text())
    value["redistribution_status"] = "private_storage"
    rights.write_text(json.dumps(value), encoding="utf-8")

    assert check_publication(tmp_path, changed_paths=changed) == [
        "sources/databases/example/1.0/records.tsv: private_storage database payload cannot be published"
    ]


def test_database_rights_cannot_be_deleted_while_payload_remains(
    tmp_path: Path,
) -> None:
    release = _write_database_rights(tmp_path, status="redistributable")
    payload = release / "records.tsv"
    payload.write_text("record\n", encoding="utf-8")
    rights = release / "rights.json"
    rights.unlink()

    errors = check_publication(
        tmp_path,
        changed_paths=(ChangedPath("D", rights.relative_to(tmp_path).as_posix()),),
    )

    assert errors == [
        "sources/databases/example/1.0/rights.json: rights.json cannot be removed while the database release remains"
    ]


@pytest.mark.parametrize(
    "unexpected_path",
    [
        "generated/motif_models/jaspar-2026-counts/CTCF/private-source.tsv",
        "generated/motif_models/unclassified/private-source.tsv",
        "generated/motif_models/pools/private-source.tsv",
    ],
)
def test_generated_motif_inventory_rejects_unclassified_paths(
    tmp_path: Path, unexpected_path: str
) -> None:
    path = tmp_path / unexpected_path
    path.parent.mkdir(parents=True)
    path.write_text("private\n", encoding="utf-8")

    errors = _validate_generated_motif_inventory(tmp_path)

    assert len(errors) == 1
    assert unexpected_path in errors[0]
    assert "not an allowed generated motif path" in errors[0]


def test_generated_motif_inventory_rejects_symlinked_member(tmp_path: Path) -> None:
    target = tmp_path / "outside.json"
    target.write_text("{}\n", encoding="utf-8")
    member = tmp_path / "generated/motif_models/example/TF/artifact.json"
    member.parent.mkdir(parents=True)
    member.symlink_to(target)

    errors = _validate_generated_motif_inventory(tmp_path)

    assert len(errors) == 1
    assert "symbolic links are forbidden" in errors[0]


def test_generated_motif_inventory_rejects_dangling_root_symlink(
    tmp_path: Path,
) -> None:
    root = tmp_path / "generated/motif_models"
    root.parent.mkdir(parents=True)
    root.symlink_to(tmp_path / "missing-target")

    assert _validate_generated_motif_inventory(tmp_path) == [
        "generated/motif_models: symbolic links are forbidden"
    ]


def _copy_pool_pair(tmp_path: Path) -> tuple[Path, Path]:
    target = tmp_path / "generated/motif_models/pools"
    target.mkdir(parents=True)
    source = Path("generated/motif_models/pools")
    request = target / "development-exposed-v2.request.json"
    inventory = target / "development-exposed-v2.inventory.json"
    shutil.copy2(source / request.name, request)
    shutil.copy2(source / inventory.name, inventory)
    payload = json.loads(request.read_text())
    for model in payload["models"]:
        bundle = Path(model["bundle_path"])
        shutil.copytree(bundle, tmp_path / bundle)
    return request, inventory


def _write_canonical_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _reseal_inventory(payload: dict[str, object]) -> None:
    payload.pop("seal_sha256", None)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["seal_sha256"] = hashlib.sha256(encoded).hexdigest()


def test_pool_request_rejects_canonical_unknown_private_fields(tmp_path: Path) -> None:
    request, _inventory = _copy_pool_pair(tmp_path)
    payload = json.loads(request.read_text())
    payload["private_source"] = "/private/source.tsv"
    _write_canonical_json(request, payload)

    errors = _validate_generated_motif_inventory(tmp_path)

    assert any("request keys are incomplete or unknown" in error for error in errors)


def test_pool_request_rejects_nonstring_task_members_without_crashing(
    tmp_path: Path,
) -> None:
    request, _inventory = _copy_pool_pair(tmp_path)
    payload = json.loads(request.read_text())
    payload["tasks"][0]["motif_ids"][0] = ["private"]
    _write_canonical_json(request, payload)

    errors = _validate_generated_motif_inventory(tmp_path)

    assert any("task motif_id must match" in error for error in errors)


def test_pool_inventory_rejects_unknown_fields_even_with_resealed_bytes(
    tmp_path: Path,
) -> None:
    _request, inventory = _copy_pool_pair(tmp_path)
    payload = json.loads(inventory.read_text())
    payload["private_source"] = "/private/source.tsv"
    _reseal_inventory(payload)
    _write_canonical_json(inventory, payload)

    errors = _validate_generated_motif_inventory(tmp_path)

    assert any("inventory keys are incomplete or unknown" in error for error in errors)


def test_pool_inventory_rejects_invalid_content_seal(tmp_path: Path) -> None:
    _request, inventory = _copy_pool_pair(tmp_path)
    payload = json.loads(inventory.read_text())
    payload["seal_sha256"] = "0" * 64
    _write_canonical_json(inventory, payload)

    errors = _validate_generated_motif_inventory(tmp_path)

    assert any("inventory seal is invalid" in error for error in errors)


def test_pool_pair_rejects_request_inventory_task_drift(tmp_path: Path) -> None:
    request, _inventory = _copy_pool_pair(tmp_path)
    payload = json.loads(request.read_text())
    payload["tasks"][0]["task_id"] = "different_task"
    _write_canonical_json(request, payload)

    errors = _validate_generated_motif_inventory(tmp_path)

    assert any(
        "request and inventory task identities disagree" in error for error in errors
    )


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("model_digest", "f" * 64),
        ("source_descriptor_id", "private_source"),
        ("conversion_contract", "private_conversion_v1"),
    ],
)
def test_pool_inventory_rejects_resealed_local_bundle_metadata_drift(
    tmp_path: Path, field: str, replacement: str
) -> None:
    _request, inventory = _copy_pool_pair(tmp_path)
    payload = json.loads(inventory.read_text())
    payload["models"][0][field] = replacement
    _reseal_inventory(payload)
    _write_canonical_json(inventory, payload)

    errors = _validate_generated_motif_inventory(tmp_path)

    assert any("local bundle metadata" in error for error in errors)


def test_pool_inventory_rejects_resealed_fabricated_receipt_qualification(
    tmp_path: Path,
) -> None:
    _request, inventory = _copy_pool_pair(tmp_path)
    payload = json.loads(inventory.read_text())
    model = payload["models"][0]
    model["qualification"] = "accepted_owner_receipt"
    model["receipt_sha256"] = "0" * 64
    model["owner_revision"] = "0" * 40
    model["canonical_artifact_ref"] = (
        "git:e-south/dnadesign-data@"
        + "0" * 40
        + "#generated/motif_models/development-exposed-v2/CEBPB/artifact.json"
    )
    _reseal_inventory(payload)
    _write_canonical_json(inventory, payload)

    errors = _validate_generated_motif_inventory(tmp_path)

    assert any("local bundle qualification" in error for error in errors)


def test_pool_request_rejects_unresolved_private_bundle_path(tmp_path: Path) -> None:
    request, _inventory = _copy_pool_pair(tmp_path)
    payload = json.loads(request.read_text())
    payload["models"][0]["bundle_path"] = "generated/motif_models/private/CEBPB"
    _write_canonical_json(request, payload)

    errors = _validate_generated_motif_inventory(tmp_path)

    assert any("does not resolve to a local motif bundle" in error for error in errors)


def test_generated_motif_bundle_requires_source_and_database_rights(
    tmp_path: Path,
) -> None:
    jaspar = tmp_path / "sources/databases/jaspar/2026"
    jaspar.mkdir(parents=True)
    (jaspar / "rights.json").write_text(
        json.dumps(
            {
                "schema_version": "dnadesign-data.database-rights/v1",
                "database": "JASPAR",
                "release": "2026",
                "redistribution_status": "redistributable",
                "rights_url": "https://jaspar.elixir.no/about/",
                "attribution": "JASPAR 2026.",
                "reviewed_on": "2026-08-29",
                "reviewer": "test-maintainer",
            }
        ),
        encoding="utf-8",
    )
    bundle = tmp_path / "generated/motif_models/example/TF"
    bundle.mkdir(parents=True)
    manifest = bundle / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "source": {
                    "descriptor_id": "jaspar_2026_core_counts",
                    "redistribution_status": "redistributable",
                }
            }
        ),
        encoding="utf-8",
    )
    artifact = bundle / "artifact.json"
    artifact.write_text("{}\n", encoding="utf-8")
    changed = (ChangedPath("M", artifact.relative_to(tmp_path).as_posix()),)

    errors = check_publication(tmp_path, changed_paths=changed)
    assert len(errors) == 1
    assert "source replay" in errors[0]

    value = json.loads(manifest.read_text())
    value["source"]["redistribution_status"] = "review_blocked"
    manifest.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    blocked_errors = check_publication(tmp_path, changed_paths=changed)
    assert len(blocked_errors) == 2
    assert "source replay" in blocked_errors[0]
    assert blocked_errors[1].endswith("generated motif source is not redistributable")


def test_cli_without_base_ref_checks_local_worktree_changes(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "fixture@example.test"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Fixture"], cwd=tmp_path, check=True)
    source = _write_metadata(tmp_path, status="review_required")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=tmp_path, check=True)
    raw = source / "raw" / "supplement.xlsx"
    raw.parent.mkdir()
    raw.write_bytes(b"private source bytes")

    completed = subprocess.run(
        [
            "python",
            "-m",
            "dnadesign_data.devtools.publication_check",
            "--repo-root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert "review_required literature may publish only" in completed.stderr
