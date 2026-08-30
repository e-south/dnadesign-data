from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

import dnadesign_data.motifs.pool as pool_module
import dnadesign_data.motifs.receipts as receipt_module
from dnadesign_data.motifs.contracts import (
    MotifExportError,
    canonical_json_bytes,
    model_digest,
)
from dnadesign_data.motifs.pool import build_task_model_pool


@pytest.fixture(autouse=True)
def _advertise_checked_receipt_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    revisions = {
        json.loads(path.read_text(encoding="utf-8"))["owner_revision"]
        for path in Path("generated/motif_models").glob("*/*/receipt.json")
    }
    assert len(revisions) == 1
    monkeypatch.setattr(
        pool_module,
        "_query_canonical_remote_revisions",
        lambda: frozenset(revisions),
    )
    monkeypatch.setattr(
        receipt_module,
        "_query_canonical_remote_revisions",
        lambda: frozenset(revisions),
    )


def _request() -> dict[str, object]:
    return {
        "schema_version": "dnadesign-data.motif-task-pool-request/v1",
        "pool_id": "fresh_pair_pool_v1",
        "pool_kind": "formal",
        "models": [
            {
                "motif_id": "ABI5",
                "bundle_path": "generated/motif_models/jaspar-2026-counts/ABI5",  # pragma: allowlist secret
            },
            {
                "motif_id": "PIF4",
                "bundle_path": "generated/motif_models/jaspar-2026-counts/PIF4",  # pragma: allowlist secret
            },
        ],
        "tasks": [
            {
                "task_id": "abi5_pif4_fresh",
                "motif_ids": ["ABI5", "PIF4"],
            }
        ],
    }


def _copy_unreceipted_fresh_models(root: Path) -> None:
    source_root = Path("sources/databases/jaspar/2026/CORE-counts")
    target_source = root / source_root
    target_source.mkdir(parents=True)
    for name in ("MA0561.1.jaspar", "MA0931.2.jaspar"):
        shutil.copy2(source_root / name, target_source / name)
    ledger = Path("sources/motif-development/development-exposure-ledger.json")
    target_ledger = root / ledger
    target_ledger.parent.mkdir(parents=True)
    shutil.copy2(ledger, target_ledger)
    generated_root = Path("generated/motif_models/jaspar-2026-counts")
    for motif_id in ("ABI5", "PIF4"):
        shutil.copytree(
            generated_root / motif_id,
            root / generated_root / motif_id,
            ignore=shutil.ignore_patterns("receipt.json"),
        )


def test_formal_candidate_without_receipts_remains_pending_without_durable_freshness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _copy_unreceipted_fresh_models(tmp_path)
    monkeypatch.setattr(pool_module, "_query_canonical_remote_revisions", frozenset)
    request = _request()

    first = build_task_model_pool(request, repository_root=tmp_path)
    second = build_task_model_pool(request, repository_root=tmp_path)

    assert first == second
    assert first["schema_version"] == "dnadesign-data.motif-task-pool/v1"
    assert first["admission_status"] == "qualification_pending"
    assert first["freshness_authority"] == "local_untrusted"
    assert len(first["seal_sha256"]) == 64
    assert len(first["development_exposure_authorities"]) == 1
    assert len(first["development_exposure_authorities"][0]["ledger_sha256"]) == 64
    assert [model["motif_id"] for model in first["models"]] == ["ABI5", "PIF4"]
    assert all(
        model["qualification"] == "conversion_verified_pending_receipt"
        for model in first["models"]
    )
    assert all(
        model["development_exposure"] == "unresolved_local_untrusted"
        for model in first["models"]
    )
    assert {model["model_schema"] for model in first["models"]} == {"motif-model/v2"}
    assert {model["scoring_semantics"] for model in first["models"]} == {
        "relative_pwm_attainment_v2"
    }
    assert first["tasks"] == [
        {
            "task_id": "abi5_pif4_fresh",
            "motif_ids": ["ABI5", "PIF4"],
            "development_exposure": "unresolved_local_untrusted",
        }
    ]
    assert all("bundle_path" not in model for model in first["models"])


def test_advertised_unreceipted_cleanroom_models_remain_qualification_pending(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _copy_unreceipted_fresh_models(tmp_path)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=Pool Test",
            "-c",
            "user.email=pool@example.invalid",
            "commit",
            "-qm",
            "unreceipted authority",
        ],
        check=True,
    )
    revision = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    monkeypatch.setattr(
        pool_module,
        "_query_canonical_remote_revisions",
        lambda: frozenset({revision}),
    )

    pool = build_task_model_pool(_request(), repository_root=tmp_path)

    assert pool["freshness_authority"] == "durable_git"
    assert pool["admission_status"] == "qualification_pending"
    assert {model["qualification"] for model in pool["models"]} == {
        "conversion_verified_pending_receipt"
    }
    assert {model["development_exposure"] for model in pool["models"]} == {"not_listed"}


def test_pool_rejects_caller_supplied_exposure_or_qualification() -> None:
    request = _request()
    request["models"][0]["development_exposure"] = "fresh"

    with pytest.raises(MotifExportError, match="exactly motif_id and bundle_path"):
        build_task_model_pool(request, repository_root=Path.cwd())


def test_unreceipted_formal_model_must_replay_its_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        pool_module,
        "_trusted_exposure_ledger",
        lambda _root: (
            set(),
            set(),
            set(),
            [{"owner_revision": "a" * 40, "ledger_sha256": "b" * 64}],
        ),
    )
    monkeypatch.setattr(
        pool_module,
        "_bundles_reachable_from_authorities",
        lambda *_args, **_kwargs: True,
    )
    source_root = Path("sources/databases/jaspar/2026/CORE-counts")
    target_source = tmp_path / source_root
    target_source.mkdir(parents=True)
    shutil.copy2(source_root / "MA0931.2.jaspar", target_source / "MA0931.2.jaspar")
    shutil.copy2(source_root / "MA0561.1.jaspar", target_source / "MA0561.1.jaspar")
    generated_root = Path("generated/motif_models") / "jaspar-2026-counts"
    shutil.copytree(
        generated_root / "PIF4",
        tmp_path / generated_root / "PIF4",
    )
    bundle = tmp_path / generated_root / "ABI5"
    bundle.mkdir(parents=True)
    artifact = json.loads((generated_root / "ABI5/artifact.json").read_text())
    manifest = json.loads((generated_root / "ABI5/manifest.json").read_text())
    artifact["probabilities"][0] = [0.4, 0.2, 0.2, 0.2]
    artifact_bytes = canonical_json_bytes(artifact)
    manifest["artifact_sha256"] = hashlib.sha256(artifact_bytes).hexdigest()
    manifest["model_digest"] = model_digest(artifact)
    (bundle / "artifact.json").write_bytes(artifact_bytes)
    (bundle / "manifest.json").write_bytes(canonical_json_bytes(manifest))
    request = {
        "schema_version": "dnadesign-data.motif-task-pool-request/v1",
        "pool_id": "tampered_pending_v1",
        "pool_kind": "formal",
        "models": [
            {
                "motif_id": "ABI5",
                "bundle_path": (generated_root / "ABI5").as_posix(),
            },
            {
                "motif_id": "PIF4",
                "bundle_path": (generated_root / "PIF4").as_posix(),
            },
        ],
        "tasks": [{"task_id": "tampered_pair", "motif_ids": ["ABI5", "PIF4"]}],
    }

    with pytest.raises(MotifExportError, match="source conversion replay"):
        build_task_model_pool(request, repository_root=tmp_path)


def test_formal_candidate_rejects_authority_ledger_exposed_models() -> None:
    request = {
        "schema_version": "dnadesign-data.motif-task-pool-request/v1",
        "pool_id": "spoofed_fresh_v1",
        "pool_kind": "formal",
        "models": [
            {
                "motif_id": "CEBPB",
                "bundle_path": "generated/motif_models/development-exposed-v2/CEBPB",
            },
            {
                "motif_id": "RELA",
                "bundle_path": "generated/motif_models/development-exposed-v2/RELA",
            },
        ],
        "tasks": [{"task_id": "spoofed_pair", "motif_ids": ["CEBPB", "RELA"]}],
    }

    with pytest.raises(MotifExportError, match="authority-ledger"):
        build_task_model_pool(request, repository_root=Path.cwd())


def test_trusted_exposure_ledger_is_append_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    ledger = tmp_path / "sources/motif-development/development-exposure-ledger.json"
    ledger.parent.mkdir(parents=True)
    first = {
        "schema_version": "dnadesign-data.motif-development-exposure-ledger/v1",
        "models": [{"motif_id": "OLD", "model_digest": "a" * 64}],
        "tasks": [],
    }
    ledger.write_bytes(canonical_json_bytes(first))
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=Ledger Test",
            "-c",
            "user.email=ledger@example.invalid",
            "commit",
            "-qm",
            "add exposure",
        ],
        check=True,
    )
    first["models"] = []
    ledger.write_bytes(canonical_json_bytes(first))
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=Ledger Test",
            "-c",
            "user.email=ledger@example.invalid",
            "commit",
            "-qm",
            "remove exposure",
        ],
        check=True,
    )
    revision = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    monkeypatch.setattr(
        pool_module,
        "_query_canonical_remote_revisions",
        lambda: frozenset({revision}),
    )

    with pytest.raises(MotifExportError, match="append-only"):
        pool_module._trusted_exposure_ledger(tmp_path)


def test_bundle_authority_requires_one_common_anchor(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    bundle = tmp_path / "generated/motif_models/example/TF"
    bundle.mkdir(parents=True)
    artifact = bundle / "artifact.json"
    manifest = bundle / "manifest.json"
    artifact.write_text("artifact-current\n")
    manifest.write_text("manifest-old\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=Pool Test",
            "-c",
            "user.email=pool@example.invalid",
            "commit",
            "-qm",
            "first half",
        ],
        check=True,
    )
    first = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    artifact.write_text("artifact-new\n")
    manifest.write_text("manifest-current\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=Pool Test",
            "-c",
            "user.email=pool@example.invalid",
            "commit",
            "-qm",
            "second half",
        ],
        check=True,
    )
    second = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    artifact.write_text("artifact-current\n")
    entries: list[object] = [
        {
            "motif_id": "TF",
            "bundle_path": "generated/motif_models/example/TF",
        }
    ]
    authorities = [
        {"owner_revision": first, "ledger_sha256": "a" * 64},
        {"owner_revision": second, "ledger_sha256": "b" * 64},
    ]

    assert not pool_module._bundles_reachable_from_authorities(
        entries,
        repository_root=tmp_path,
        authorities=authorities,
    )


def test_development_pool_preserves_exposure_without_formal_admission() -> None:
    request = json.loads(
        Path(
            "generated/motif_models/pools/development-exposed-v2.request.json"
        ).read_text()
    )

    pool = build_task_model_pool(request, repository_root=Path.cwd())

    assert pool["admission_status"] == "development_only"
    assert {model["development_exposure"] for model in pool["models"]} == {
        "development_exposed"
    }
    assert pool["tasks"][0]["development_exposure"] == "development_exposed"


def test_checked_in_pool_inventories_cover_only_active_v2_surfaces() -> None:
    exposed_v2_request = json.loads(
        Path(
            "generated/motif_models/pools/development-exposed-v2.request.json"
        ).read_text()
    )
    exposed_v2_inventory = json.loads(
        Path(
            "generated/motif_models/pools/development-exposed-v2.inventory.json"
        ).read_text()
    )
    assert (
        build_task_model_pool(exposed_v2_request, repository_root=Path.cwd())
        == exposed_v2_inventory
    )
    assert len(exposed_v2_request["models"]) == 12
    assert {model["model_schema"] for model in exposed_v2_inventory["models"]} == {
        "motif-model/v2"
    }

    fresh_request = json.loads(
        Path("generated/motif_models/pools/formal-fresh-v2.request.json").read_text()
    )
    pairs = [
        task for task in fresh_request["tasks"] if task["task_id"].endswith("_pair")
    ]
    assert len(pairs) == 4
    assert len({motif for task in pairs for motif in task["motif_ids"]}) == 8
    with Path("sources/databases/jaspar/2026/CORE-counts/records.tsv").open(
        newline=""
    ) as handle:
        records = list(csv.DictReader(handle, delimiter="\t"))
    species_by_motif = {
        record["motif_id"]: record["source_species"] for record in records
    }
    pair_contexts = {
        tuple(species_by_motif[motif_id] for motif_id in task["motif_ids"])
        for task in pairs
    }
    assert pair_contexts == {
        ("Homo sapiens", "Homo sapiens"),
        ("Arabidopsis thaliana", "Arabidopsis thaliana"),
        ("Drosophila melanogaster", "Drosophila melanogaster"),
    }
    twelve = next(
        task
        for task in fresh_request["tasks"]
        if task["task_id"] == "human_core_twelve"
    )
    assert len(twelve["motif_ids"]) == 12
    pool = build_task_model_pool(fresh_request, repository_root=Path.cwd())
    formal_inventory = json.loads(
        Path("generated/motif_models/pools/formal-fresh-v2.inventory.json").read_text()
    )
    assert pool == formal_inventory
    assert pool["admission_status"] == "qualification_ready"
    assert pool["freshness_authority"] == "durable_git"
    assert {item["qualification"] for item in pool["models"]} == {
        "accepted_owner_receipt"
    }


@pytest.mark.parametrize(
    "bundle_path",
    ["/absolute/path", "../outside", "generated//bad", "generated/./bad"],
)
def test_pool_rejects_noncanonical_bundle_paths(bundle_path: str) -> None:
    request = _request()
    request["models"][0]["bundle_path"] = bundle_path

    with pytest.raises(MotifExportError, match="bundle_path"):
        build_task_model_pool(request, repository_root=Path.cwd())
