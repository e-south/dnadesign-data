from __future__ import annotations

import copy
import csv
import hashlib
import inspect
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

import dnadesign_data.motifs.jaspar as jaspar_module
import dnadesign_data.motifs.receipts as receipt_module
from dnadesign_data.catalog.regulatory_parts import known_motif_source_files
from dnadesign_data.motifs import (
    MotifExportError,
    build_jaspar_count_motif_export,
    build_meme_motif_export,
    build_motif_export_receipt,
    build_regulondb_site_export,
    list_motif_source_providers,
    write_motif_source_export,
)
from dnadesign_data.motifs.contracts import (
    canonical_json_bytes,
    read_source_bytes,
    validate_probability_rows,
)
from dnadesign_data.motifs.io import load_motif_source_export
from dnadesign_data.motifs.receipt_validation import revalidate_motif_export_receipt


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_checked_receipt(
    bundle: Path, monkeypatch: pytest.MonkeyPatch
) -> dict[str, object]:
    receipt = json.loads((bundle / "receipt.json").read_text(encoding="utf-8"))
    owner_revision = receipt["owner_revision"]
    monkeypatch.setattr(
        receipt_module,
        "_query_canonical_remote_revisions",
        lambda: frozenset({owner_revision}),
    )
    assert (
        revalidate_motif_export_receipt(
            bundle,
            receipt,
            owner_repository_path=Path.cwd(),
            data_root=Path.cwd(),
        )
        == receipt
    )
    return receipt


def _write_catalog_meme(root: Path, name: str, content: str) -> Path:
    source = root / "sources/literature/OMalley_et_al/escherichia_coli_motifs" / name
    source.parent.mkdir(parents=True)
    source.write_text(content, encoding="utf-8")
    return source


def _write_catalog_regulondb(root: Path, content: str) -> Path:
    source = root / "sources/databases/regulondb/13.0/binding_sites/TF-RISet.tsv"
    source.parent.mkdir(parents=True)
    source.write_text(content, encoding="utf-8")
    return source


def _write_catalog_jaspar_counts(root: Path, name: str, content: str) -> Path:
    source = root / "sources/databases/jaspar/2026/CORE-counts" / name
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(content, encoding="utf-8")
    return source


def _accepted_model_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[dict[str, dict[str, object]], Path]:
    source = _write_catalog_meme(
        tmp_path,
        "simple.txt",
        """MEME version 5
ALPHABET= ACGT
Background letter frequencies
A 0.25 C 0.25 G 0.25 T 0.25
MOTIF simple
letter-probability matrix: alength= 4 w= 1 nsites= 1 E= 0
0.25 0.25 0.25 0.25
""",
    )
    export = build_meme_motif_export(
        source,
        motif_id="simple",
        source_motif_id="simple",
        source_descriptor_id="omalley_2021_ecoli_meme",
        prior_weight=0.0,
        data_root=tmp_path,
    )
    descriptor = next(
        item
        for item in known_motif_source_files()
        if item.source_id == "omalley_2021_ecoli_meme"
    )
    accepted_descriptor = replace(descriptor, redistribution_status="redistributable")
    monkeypatch.setattr(
        receipt_module,
        "known_motif_source_files",
        lambda: (accepted_descriptor,),
    )

    def advertised_revisions() -> frozenset[str]:
        repository = tmp_path / "owner-repository"
        if not repository.is_dir():
            return frozenset()
        result = subprocess.run(
            ["git", "-C", str(repository), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
        return (
            frozenset({result.stdout.strip()})
            if result.returncode == 0
            else frozenset()
        )

    monkeypatch.setattr(
        receipt_module,
        "_query_canonical_remote_revisions",
        advertised_revisions,
        raising=False,
    )
    export["manifest"]["source"]["redistribution_status"] = "redistributable"
    return export, source


def _git_authority(
    root: Path, export: dict[str, dict[str, object]]
) -> tuple[Path, str, str]:
    repository = root / "owner-repository"
    repository.mkdir()
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "remote",
            "add",
            "origin",
            "https://github.com/e-south/dnadesign-data.git",
        ],
        check=True,
    )
    artifact = repository / "models/simple.json"
    artifact.parent.mkdir()
    artifact.write_bytes(canonical_json_bytes(export["artifact"]))
    descriptor_id = export["manifest"]["source"]["descriptor_id"]
    descriptor = next(
        item for item in known_motif_source_files() if item.source_id == descriptor_id
    )
    source_name = export["manifest"]["source"]["artifact_name"]
    source = repository / descriptor.path / source_name
    source.parent.mkdir(parents=True)
    source.write_bytes((root / descriptor.path / source_name).read_bytes())
    subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "add",
            "models/simple.json",
            str(source.relative_to(repository)),
        ],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "-c",
            "user.name=Receipt Test",
            "-c",
            "user.email=receipt@example.invalid",
            "commit",
            "-qm",
            "admit model",
        ],
        check=True,
    )
    revision = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return (
        repository,
        revision,
        f"git:e-south/dnadesign-data@{revision}#models/simple.json",
    )


def _receipt_bundle(root: Path, export: dict[str, dict[str, object]]) -> Path:
    bundle = root / "receipt-input"
    write_motif_source_export(export, bundle)
    return bundle


def _commit_authority_change(repository: Path, message: str) -> str:
    subprocess.run(["git", "-C", str(repository), "add", "-A"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "-c",
            "user.name=Receipt Test",
            "-c",
            "user.email=receipt@example.invalid",
            "commit",
            "-qm",
            message,
        ],
        check=True,
    )
    return subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_provider_catalog_is_small_explicit_and_capability_bearing() -> None:
    providers = list_motif_source_providers()

    assert [provider["provider_id"] for provider in providers] == [
        "meme_probability_matrix_v1",
        "jaspar_count_matrix_v1",
        "regulondb_tf_riset_sites_v1",
    ]
    assert providers[0]["output_schema"] == "motif-model/v2"
    assert providers[0]["materializes_motif_model"] is True
    assert providers[1]["output_schema"] == "motif-model/v2"
    assert providers[1]["materializes_motif_model"] is True
    assert providers[2]["output_schema"] == "dnadesign-data.binding-site-set/v1"
    assert providers[2]["materializes_motif_model"] is False
    assert all(provider["network_access"] is False for provider in providers)


def test_jaspar_count_export_preserves_source_and_uses_sqrt_n_prior(
    tmp_path: Path,
) -> None:
    source = _write_catalog_jaspar_counts(
        tmp_path,
        "MA0001.1.jaspar",
        ">MA0001.1\tExample\nA [ 4 1 ]\nC [ 0 1 ]\nG [ 0 1 ]\nT [ 0 1 ]\n",
    )

    export = build_jaspar_count_motif_export(
        source,
        motif_id="Example",
        source_motif_id="MA0001.1",
        source_descriptor_id="jaspar_2026_core_counts",
        background=[0.4, 0.1, 0.2, 0.3],
        data_root=tmp_path,
    )

    artifact = export["artifact"]
    assert artifact["schema_version"] == "motif-model/v2"
    assert source.read_text(encoding="utf-8").startswith(">MA0001.1")
    assert artifact["conversion"] == {
        "schema_version": "motif-conversion/v2",
        "method": "count_matrix_sqrt_n_background_prior_v1",
        "source_motif_id": "MA0001.1",
        "position_observed_counts": [4.0, 4.0],
        "position_prior_masses": [2.0, 2.0],
        "position_denominators": [6.0, 6.0],
    }
    assert artifact["probabilities"][0] == pytest.approx(
        [4.8 / 6.0, 0.2 / 6.0, 0.4 / 6.0, 0.6 / 6.0]
    )
    assert export["manifest"]["selection"] == {
        "motif_id": "Example",
        "source_motif_id": "MA0001.1",
        "background": [0.4, 0.1, 0.2, 0.3],
        "conversion_contract": "count_matrix_sqrt_n_background_prior_v1",
    }
    _, _, conversion_contract, descriptor = receipt_module._validate_model_export(
        export, canonical_json_bytes(artifact)
    )
    assert conversion_contract == "count_matrix_sqrt_n_background_prior_v1"
    assert descriptor.source_id == "jaspar_2026_core_counts"


@pytest.mark.parametrize(
    "content",
    [
        ">MA0001.1 Example\nA [ 1 ]\nC [ 1 ]\nG [ 1 ]\n",
        ">MA0001.1 Example\nA [ 1 ]\nC [ 1 ]\nG [ 1 ]\nT [ nan ]\n",
        ">MA0001.1 Example\nA [ 1 ]\nC [ 1 ]\nG [ 1 ]\nT [ -1 ]\n",
        ">MA0001.1 Example\nA [ 1 2 ]\nC [ 1 ]\nG [ 1 ]\nT [ 1 ]\n",
        ">MA0001.1 Example\nA [ 1 ]\nC [ 1 ]\nG [ 1 ]\nT [ 1 ]\ntrailing\n",
        ">MA0001.1 Example\nA [ 1e309 ]\nC [ 1 ]\nG [ 1 ]\nT [ 1 ]\n",
        ">MA0001.1 Example\nA [ " + "1" * 1000 + " ]\nC [ 1 ]\nG [ 1 ]\nT [ 1 ]\n",
    ],
)
def test_jaspar_count_export_rejects_malformed_sources(
    tmp_path: Path, content: str
) -> None:
    source = _write_catalog_jaspar_counts(tmp_path, "MA0001.1.jaspar", content)

    with pytest.raises(MotifExportError):
        build_jaspar_count_motif_export(
            source,
            motif_id="Example",
            source_motif_id="MA0001.1",
            source_descriptor_id="jaspar_2026_core_counts",
            background=[0.25, 0.25, 0.25, 0.25],
            data_root=tmp_path,
        )


def test_jaspar_width_bound_precedes_float_materialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = " ".join("1" for _ in range(jaspar_module.MAX_MOTIF_WIDTH + 1))
    source = (
        ">MA0001.1 Example\n"
        f"A [ {values} ]\nC [ {values} ]\nG [ {values} ]\nT [ {values} ]\n"
    )

    def forbidden_float(_value: object) -> float:
        raise AssertionError("float conversion must not run past the width bound")

    monkeypatch.setattr("builtins.float", forbidden_float)

    with pytest.raises(MotifExportError, match="width"):
        jaspar_module._parse_count_matrix(source, source_motif_id="MA0001.1")


def test_jaspar_width_bound_uses_bounded_tokenization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = " ".join("1" for _ in range(jaspar_module.MAX_MOTIF_WIDTH + 1))
    source = f">MA0001.1 Example\nA [ {values} ]\nC [ 1 ]\nG [ 1 ]\nT [ 1 ]\n"
    original_split = str.split

    def bounded_split(value: str, *, maxsplit: int) -> list[str]:
        assert maxsplit == jaspar_module.MAX_MOTIF_WIDTH
        return original_split(value, maxsplit=maxsplit)

    monkeypatch.setattr(jaspar_module, "_bounded_split", bounded_split)

    with pytest.raises(MotifExportError, match="width"):
        jaspar_module._parse_count_matrix(source, source_motif_id="MA0001.1")


def test_meme_export_takes_release_and_rights_from_catalog_descriptor(
    tmp_path: Path,
) -> None:
    source = _write_catalog_meme(
        tmp_path,
        "simple.txt",
        """MEME version 5
ALPHABET= ACGT
Background letter frequencies
A 0.25 C 0.25 G 0.25 T 0.25
MOTIF simple
letter-probability matrix: alength= 4 w= 1 nsites= 1 E= 0
0.25 0.25 0.25 0.25
""",
    )

    export = build_meme_motif_export(
        source,
        motif_id="simple",
        source_motif_id="simple",
        source_descriptor_id="omalley_2021_ecoli_meme",
        prior_weight=0.0,
        data_root=tmp_path,
    )

    assert export["manifest"]["source"]["revision"] == (
        "s41592-021-01312-2-supplementary-data-2"
    )
    assert export["manifest"]["source"]["redistribution_status"] == ("private_storage")
    parameters = inspect.signature(build_meme_motif_export).parameters
    assert "source_revision" not in parameters
    assert "redistribution_status" not in parameters


@pytest.mark.parametrize("field", ["motif_id", "source_motif_id"])
def test_meme_export_rejects_identifiers_outside_motif_balance_schema(
    tmp_path: Path, field: str
) -> None:
    source = _write_catalog_meme(
        tmp_path,
        "simple.txt",
        """MEME version 5
ALPHABET= ACGT
Background letter frequencies
A 0.25 C 0.25 G 0.25 T 0.25
MOTIF simple
letter-probability matrix: alength= 4 w= 1 nsites= 1 E= 0
0.25 0.25 0.25 0.25
""",
    )
    arguments = {"motif_id": "simple", "source_motif_id": "simple"}
    arguments[field] = "../bad\nidentity"

    with pytest.raises(MotifExportError, match="Motif Balance identity"):
        build_meme_motif_export(
            source,
            **arguments,
            source_descriptor_id="omalley_2021_ecoli_meme",
            prior_weight=0.0,
            data_root=tmp_path,
        )


def test_meme_export_declares_prior_mixture_and_is_deterministic(
    tmp_path: Path,
) -> None:
    source = _write_catalog_meme(
        tmp_path,
        "example.txt",
        """MEME version 5

ALPHABET= ACGT

Background letter frequencies
A 0.30 C 0.20 G 0.20 T 0.30

MOTIF source_cpxR
letter-probability matrix: alength= 4 w= 2 nsites= 4 E= 0
1.0 0.0 0.0 0.0
0.1 0.2 0.3 0.4
""",
    )

    first = build_meme_motif_export(
        source,
        motif_id="cpxR",
        source_motif_id="source_cpxR",
        source_descriptor_id="omalley_2021_ecoli_meme",
        prior_weight=0.1,
        data_root=tmp_path,
    )
    second = build_meme_motif_export(
        source,
        motif_id="cpxR",
        source_motif_id="source_cpxR",
        source_descriptor_id="omalley_2021_ecoli_meme",
        prior_weight=0.1,
        data_root=tmp_path,
    )

    assert first == second
    model = first["artifact"]
    assert model["schema_version"] == "motif-model/v2"
    assert model["motif_id"] == "cpxR"
    assert model["alphabet"] == ["A", "C", "G", "T"]
    assert model["source_digest"] == _sha256(source)
    assert model["source_name"] == "example.txt"
    assert model["conversion"] == {
        "schema_version": "motif-conversion/v1",
        "method": "probability_matrix_prior_mixture_v1",
        "prior_weight": 0.1,
        "source_motif_id": "source_cpxR",
    }
    assert all(value > 0.0 for row in model["probabilities"] for value in row)
    assert model["probabilities"][0] == pytest.approx(
        [1.03 / 1.1, 0.02 / 1.1, 0.02 / 1.1, 0.03 / 1.1]
    )
    assert first["manifest"]["output_schema"] == "motif-model/v2"
    assert first["manifest"]["model_digest"]


def test_meme_export_can_use_an_explicit_target_background_without_losing_source_background(
    tmp_path: Path,
) -> None:
    source = _write_catalog_meme(
        tmp_path,
        "target-background.txt",
        """MEME version 5
ALPHABET= ACGT
Background letter frequencies
A 0.40 C 0.10 G 0.20 T 0.30
MOTIF source_model
letter-probability matrix: alength= 4 w= 1 nsites= 4 E= 0
1.0 0.0 0.0 0.0
""",
    )

    export = build_meme_motif_export(
        source,
        motif_id="model",
        source_motif_id="source_model",
        source_descriptor_id="omalley_2021_ecoli_meme",
        prior_weight=0.1,
        background=[0.25, 0.25, 0.25, 0.25],
        data_root=tmp_path,
    )

    assert export["artifact"]["background"] == [0.25, 0.25, 0.25, 0.25]
    assert export["artifact"]["probabilities"][0] == pytest.approx(
        [1.025 / 1.1, 0.025 / 1.1, 0.025 / 1.1, 0.025 / 1.1]
    )
    assert export["artifact"]["conversion"] == {
        "schema_version": "motif-conversion/v2",
        "method": "probability_matrix_target_background_v1",
        "prior_weight": 0.1,
        "source_motif_id": "source_model",
        "source_background": [0.4, 0.1, 0.2, 0.3],
        "target_background": [0.25, 0.25, 0.25, 0.25],
        "target_background_policy": "explicit_target_background_v1",
    }
    assert export["manifest"]["selection"] == {
        "motif_id": "model",
        "source_motif_id": "source_model",
        "prior_weight": 0.1,
        "source_background": [0.4, 0.1, 0.2, 0.3],
        "target_background": [0.25, 0.25, 0.25, 0.25],
        "target_background_policy": "explicit_target_background_v1",
    }


def test_meme_target_background_source_replay_rejects_provenance_tampering(
    tmp_path: Path,
) -> None:
    source = _write_catalog_meme(
        tmp_path,
        "target-background.txt",
        """MEME version 5
ALPHABET= ACGT
Background letter frequencies
A 0.40 C 0.10 G 0.20 T 0.30
MOTIF source_model
letter-probability matrix: alength= 4 w= 1 nsites= 4 E= 0
0.7 0.1 0.1 0.1
""",
    )
    export = build_meme_motif_export(
        source,
        motif_id="model",
        source_motif_id="source_model",
        source_descriptor_id="omalley_2021_ecoli_meme",
        prior_weight=0.1,
        background=[0.25, 0.25, 0.25, 0.25],
        data_root=tmp_path,
    )
    bundle = _receipt_bundle(tmp_path, export)
    assert (
        receipt_module.validate_motif_export_source_replay(bundle, data_root=tmp_path)
        == export
    )

    tampered = copy.deepcopy(export)
    tampered["artifact"]["conversion"]["source_background"] = [
        0.25,
        0.25,
        0.25,
        0.25,
    ]
    tampered["manifest"]["selection"]["source_background"] = [
        0.25,
        0.25,
        0.25,
        0.25,
    ]
    tampered["manifest"]["artifact_sha256"] = hashlib.sha256(
        canonical_json_bytes(tampered["artifact"])
    ).hexdigest()
    bundle = _receipt_bundle(tmp_path / "tampered", tampered)

    with pytest.raises(MotifExportError, match="source conversion replay"):
        receipt_module.validate_motif_export_source_replay(bundle, data_root=tmp_path)


def test_meme_target_background_receipt_replays_the_explicit_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _write_catalog_meme(
        tmp_path,
        "target-background.txt",
        """MEME version 5
ALPHABET= ACGT
Background letter frequencies
A 0.40 C 0.10 G 0.20 T 0.30
MOTIF source_model
letter-probability matrix: alength= 4 w= 1 nsites= 4 E= 0
0.7 0.1 0.1 0.1
""",
    )
    export = build_meme_motif_export(
        source,
        motif_id="model",
        source_motif_id="source_model",
        source_descriptor_id="omalley_2021_ecoli_meme",
        prior_weight=0.1,
        background=[0.25, 0.25, 0.25, 0.25],
        data_root=tmp_path,
    )
    descriptor = next(
        item
        for item in known_motif_source_files()
        if item.source_id == "omalley_2021_ecoli_meme"
    )
    accepted_descriptor = replace(descriptor, redistribution_status="redistributable")
    monkeypatch.setattr(
        receipt_module, "known_motif_source_files", lambda: (accepted_descriptor,)
    )
    export["manifest"]["source"]["redistribution_status"] = "redistributable"
    bundle = _receipt_bundle(tmp_path, export)
    repository, owner_revision, artifact_ref = _git_authority(tmp_path, export)
    monkeypatch.setattr(
        receipt_module,
        "_query_canonical_remote_revisions",
        lambda: frozenset({owner_revision}),
    )

    receipt = build_motif_export_receipt(
        bundle,
        owner_revision=owner_revision,
        canonical_artifact_ref=artifact_ref,
        owner_repository_path=repository,
        data_root=tmp_path,
    )

    assert receipt["conversion_contract"] == ("probability_matrix_target_background_v1")
    assert (
        revalidate_motif_export_receipt(
            bundle,
            receipt,
            owner_repository_path=repository,
            data_root=tmp_path,
        )
        == receipt
    )


def test_meme_export_fails_without_explicit_prior_for_zero_values(
    tmp_path: Path,
) -> None:
    source = _write_catalog_meme(
        tmp_path,
        "zero.txt",
        """MEME version 5
ALPHABET= ACGT
Background letter frequencies
A 0.25 C 0.25 G 0.25 T 0.25
MOTIF zero
letter-probability matrix: alength= 4 w= 1 nsites= 1 E= 0
1 0 0 0
""",
    )

    with pytest.raises(MotifExportError, match="positive prior_weight"):
        build_meme_motif_export(
            source,
            motif_id="zero",
            source_motif_id="zero",
            source_descriptor_id="omalley_2021_ecoli_meme",
            prior_weight=0.0,
            data_root=tmp_path,
        )


@pytest.mark.parametrize(
    ("source_name", "motif_id", "source_sha256", "artifact_sha256", "model_digest"),
    [
        (
            "MA0466.4.meme",
            "CEBPB",
            "2502444b93ef58652542f957fb1e0f7beb0a69c0ac11f0accc5f1c406e5b7c39",  # pragma: allowlist secret
            "7c24c2f4567ae8db6fa567e85b02c918b7bef9d1e3549c3ef576f2f51cb3e1b9",  # pragma: allowlist secret
            "4d90633137a60e306dca0466bf06c44bc1c8882409d8f56d6498ca12358482ef",  # pragma: allowlist secret
        ),
        (
            "MA0107.1.meme",
            "RELA",
            "581074a99259bbb98794fdfc6f70643b5ef3d780209923fb0be8f421f99e05c6",  # pragma: allowlist secret
            "5653fd86c00056a99647c0f626abcdfc840864751c05b83b9767cfbfb2cae8b5",  # pragma: allowlist secret
            "15737a8cae1d93f2b38713dd167adb83753ade87b39c2fe81f9410c1ed7e39ca",  # pragma: allowlist secret
        ),
        (
            "MA0035.5.meme",
            "GATA1",
            "6790e0d4083db330abd65406a5b75d6549a569df16799742cc8e84ccebba78ec",  # pragma: allowlist secret
            "c5e4fa9ddae9ee74082bb8e12ec113cab7f9dfbfbbb45afd7c217dc8096c30a1",  # pragma: allowlist secret
            "16ee72ac0e0825d63fb5c15cd5931126b18d949416904625029db167c366d5db",  # pragma: allowlist secret
        ),
        (
            "MA0091.2.meme",
            "TAL1_TCF3",
            "c518f379feed2994a9360666efc62488b6e1bbf045dfad7efc361d6f7745c2a1",  # pragma: allowlist secret
            "3fe7c2906d1e4ff816243290b1c378f7f68f3ec678d8d441048ae75c8ada695f",  # pragma: allowlist secret
            "23a4824575df2b3e05bebe5ddca53a63f1b188d61e466f00c40bd3d4ea468951",  # pragma: allowlist secret
        ),
        (
            "MA0099.4.meme",
            "FOS_JUN",
            "f257f4f65f2042a1591bf9f0c7549c88b7e4c44781bc50d56c876cafd23f80bb",  # pragma: allowlist secret
            "7815a77ccd7fff8fd4185ff8098a20761fdbcf5fbde6e2f40a227be66c63e095",  # pragma: allowlist secret
            "e879b45df0d986e173de36764f3181187758592163e454267de0a106d32ac3b6",  # pragma: allowlist secret
        ),
        (
            "MA0138.1.meme",
            "REST",
            "c4e46c2217f74dad49655419a667ecd14c4f8dc19f7cc90515c5af196a75261c",  # pragma: allowlist secret
            "56a7b87a23c558d14927ef97295bce9a086de3e3f7fb52aaaec019e93f93f183",  # pragma: allowlist secret
            "fce858d6c539a9bec6c2670c8ef23bf2769387bdf09ca72f0deb09c0d4a24f30",  # pragma: allowlist secret
        ),
        (
            "MA0143.5.meme",
            "SOX2",
            "be34dbbc5206f48f5acf1565e967d0df13131edfbb06cd88d972a7ae4097d7cc",  # pragma: allowlist secret
            "d5ee3214c1c06e2c1a874964201a37797ca6de445e7a85e42bb7528a38fbe20c",  # pragma: allowlist secret
            "728a2d5a99707a60f6306130f65308c3000161fb1c745b6edcd7027af5b22283",  # pragma: allowlist secret
        ),
        (
            "MA0551.2.meme",
            "HY5",
            "49e4ba2d6e5b88a9d8fc713ddec6e0f244a35a2d9ad3cbbc411d3a8e87abc338",  # pragma: allowlist secret
            "b6c64f61078bb992b034576098d86430287322335dab60eaf07a7f07319fd277",  # pragma: allowlist secret
            "5eb7b7df75ac185a32393821f22da2fe6b38f5c9305f5c9e56c334bbe3dc134b",  # pragma: allowlist secret
        ),
        (
            "MA0560.2.meme",
            "PIF3",
            "f9992091912488b0dfcb7fca7f8af0137ef0df4d1b31c855ab7169a3ac9c3eee",  # pragma: allowlist secret
            "1afd1aa473c19d390018d618056e04941a8d89e3059b1759d50cded96200412f",  # pragma: allowlist secret
            "d5a571fe8a100c134785d8149cbbcea3430f06fae79c7562a030859ab9d084c4",  # pragma: allowlist secret
        ),
    ],
)
def test_real_jaspar_2026_meme_exports_are_deterministic(
    source_name: str,
    motif_id: str,
    source_sha256: str,
    artifact_sha256: str,
    model_digest: str,
) -> None:
    source = Path("sources/databases/jaspar/2026/CORE") / source_name

    first = build_meme_motif_export(
        source,
        motif_id=motif_id,
        source_motif_id=source_name.removesuffix(".meme"),
        source_descriptor_id="jaspar_2026_core_meme",
        prior_weight=0.1,
        model_schema="motif-model/v1",
    )
    second = build_meme_motif_export(
        source,
        motif_id=motif_id,
        source_motif_id=source_name.removesuffix(".meme"),
        source_descriptor_id="jaspar_2026_core_meme",
        prior_weight=0.1,
        model_schema="motif-model/v1",
    )

    assert first == second
    assert first["artifact"]["probabilities"] == validate_probability_rows(
        first["artifact"]["probabilities"]
    )
    assert first["artifact"]["source_digest"] == source_sha256
    assert first["manifest"]["artifact_sha256"] == artifact_sha256
    assert first["manifest"]["model_digest"] == model_digest
    assert first["manifest"]["source"] == {
        "artifact_name": source_name,
        "artifact_sha256": source_sha256,
        "descriptor_id": "jaspar_2026_core_meme",
        "redistribution_status": "redistributable",
        "revision": "2026",
    }


@pytest.mark.parametrize(
    ("source_name", "motif_id", "width"),
    [
        ("MA0035.5.meme", "GATA1", 7),
        ("MA0091.2.meme", "TAL1_TCF3", 10),
        ("MA0099.4.meme", "FOS_JUN", 9),
        ("MA0138.1.meme", "REST", 19),
        ("MA0143.5.meme", "SOX2", 7),
        ("MA0551.2.meme", "HY5", 12),
        ("MA0560.2.meme", "PIF3", 7),
    ],
)
def test_jaspar_2026_dogfood_panel_sources_are_admitted(
    source_name: str,
    motif_id: str,
    width: int,
) -> None:
    source = Path("sources/databases/jaspar/2026/CORE") / source_name

    export = build_meme_motif_export(
        source,
        motif_id=motif_id,
        source_motif_id=source_name.removesuffix(".meme"),
        source_descriptor_id="jaspar_2026_core_meme",
        prior_weight=0.1,
    )

    assert len(export["artifact"]["probabilities"]) == width
    assert export["manifest"]["source"]["redistribution_status"] == "redistributable"
    assert export["manifest"]["source"]["revision"] == "2026"


@pytest.mark.parametrize(
    ("source_name", "source_motif_id", "motif_id", "width", "source_sha256"),
    [
        (
            "MAX.H14CORE.0.PS.A.meme",
            "MAX.H14CORE.0.PS.A",
            "MAX",
            11,
            "c84263e4960266bd65070f9ed68b6de2fa531ede702dce2eecb424b5a3bf47c2",  # pragma: allowlist secret
        ),
        (
            "MYCN.H14CORE.0.PS.A.meme",
            "MYCN.H14CORE.0.PS.A",
            "MYCN",
            11,
            "d349259cc26b1f5a87ebe86d30d3fba0ffb8ad8a3132c4118a4fd2b39a1a08b7",  # pragma: allowlist secret
        ),
        (
            "SP1.H14CORE.0.P.B.meme",
            "SP1.H14CORE.0.P.B",
            "SP1",
            14,
            "04bfe665dc4ff9facbf1190b60d09637945d892e030d5c4e4ce64cf8abf71e48",  # pragma: allowlist secret
        ),
    ],
)
def test_hocomoco_14_core_models_reuse_the_bounded_meme_contract(
    source_name: str,
    source_motif_id: str,
    motif_id: str,
    width: int,
    source_sha256: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = Path("sources/databases/hocomoco/14/CORE") / source_name

    first = build_meme_motif_export(
        source,
        motif_id=motif_id,
        source_motif_id=source_motif_id,
        source_descriptor_id="hocomoco_14_core_meme",
        prior_weight=0.1,
        model_schema="motif-model/v2",
    )
    second = build_meme_motif_export(
        source,
        motif_id=motif_id,
        source_motif_id=source_motif_id,
        source_descriptor_id="hocomoco_14_core_meme",
        prior_weight=0.1,
        model_schema="motif-model/v2",
    )

    assert first == second
    assert len(first["artifact"]["probabilities"]) == width
    assert first["artifact"]["source_digest"] == source_sha256
    assert first["manifest"]["source"] == {
        "artifact_name": source_name,
        "artifact_sha256": source_sha256,
        "descriptor_id": "hocomoco_14_core_meme",
        "redistribution_status": "redistributable",
        "revision": "14",
    }

    generated = Path("generated/motif_models/development-exposed-v2") / motif_id
    assert (
        json.loads((generated / "artifact.json").read_text(encoding="utf-8"))
        == first["artifact"]
    )
    assert (
        json.loads((generated / "manifest.json").read_text(encoding="utf-8"))
        == first["manifest"]
    )
    receipt = _assert_checked_receipt(generated, monkeypatch)
    assert receipt["motif_id"] == motif_id
    assert receipt["model_digest"] == first["manifest"]["model_digest"]


def test_hocomoco_14_record_ledger_binds_the_admitted_source_set() -> None:
    source_root = Path("sources/databases/hocomoco/14/CORE")
    with (source_root / "records.tsv").open(encoding="utf-8", newline="") as handle:
        rows = tuple(csv.DictReader(handle, delimiter="\t"))

    expected = {
        "MAX.H14CORE.0.PS.A": ("MAX", "Homo sapiens"),
        "MYCN.H14CORE.0.PS.A": ("MYCN", "Homo sapiens"),
        "SP1.H14CORE.0.P.B": ("SP1", "Mus musculus"),
    }
    assert {row["source_record"] for row in rows} == set(expected)
    assert {path.name for path in source_root.glob("*.meme")} == {
        row["source_file"] for row in rows
    }
    for row in rows:
        label, species = expected[row["source_record"]]
        assert row["motif_label"] == label
        assert row["source_species"] == species
        assert _sha256(source_root / row["source_file"]) == row["sha256"]
        assert row["retrieval_url"].startswith(
            "https://hocomoco14.autosome.org/final_bundle/"
        )
        assert row["retrieved_on"] == "2026-08-28"
        assert row["ingestion_transform"] == "terminal_blank_line_normalization_v1"
        assert (
            row["redistribution_posture"]
            == "WTFPL_treat_as_CC-BY_per_official_download_page"
        )


def test_jaspar_2026_count_panel_replays_source_models_and_freshness() -> None:
    source_root = Path("sources/databases/jaspar/2026/CORE-counts")
    with (source_root / "records.tsv").open(encoding="utf-8", newline="") as handle:
        rows = tuple(csv.DictReader(handle, delimiter="\t"))

    assert len(rows) == 16
    assert {row["development_exposure"] for row in rows} == {"fresh"}
    assert {row["redistribution_posture"] for row in rows} == {"CC-BY-4.0"}
    assert {row["source_species"] for row in rows} == {
        "Homo sapiens",
        "Arabidopsis thaliana",
        "Drosophila melanogaster",
    }
    assert {path.name for path in source_root.glob("*.jaspar")} == {
        row["source_file"] for row in rows
    }
    for row in rows:
        source = source_root / row["source_file"]
        assert _sha256(source) == row["sha256"]
        export = build_jaspar_count_motif_export(
            source,
            motif_id=row["motif_id"],
            source_motif_id=row["source_record"],
            source_descriptor_id="jaspar_2026_core_counts",
            background=[0.25, 0.25, 0.25, 0.25],
        )
        generated = Path("generated/motif_models/jaspar-2026-counts") / row["motif_id"]
        assert (
            json.loads((generated / "artifact.json").read_text()) == export["artifact"]
        )
        assert (
            json.loads((generated / "manifest.json").read_text()) == export["manifest"]
        )


@pytest.mark.parametrize(
    ("collection", "motif_id", "descriptor_id", "source_revision"),
    [
        ("development-exposed-v2", "CEBPB", "jaspar_2026_core_meme", "2026"),
        ("development-exposed-v2", "RELA", "jaspar_2026_core_meme", "2026"),
        ("development-exposed-v2", "FOS_JUN", "jaspar_2026_core_meme", "2026"),
        ("development-exposed-v2", "GATA1", "jaspar_2026_core_meme", "2026"),
        ("development-exposed-v2", "TAL1_TCF3", "jaspar_2026_core_meme", "2026"),
        ("development-exposed-v2", "SOX2", "jaspar_2026_core_meme", "2026"),
        ("development-exposed-v2", "REST", "jaspar_2026_core_meme", "2026"),
        ("development-exposed-v2", "HY5", "jaspar_2026_core_meme", "2026"),
        ("development-exposed-v2", "PIF3", "jaspar_2026_core_meme", "2026"),
        ("development-exposed-v2", "MAX", "hocomoco_14_core_meme", "14"),
        ("development-exposed-v2", "MYCN", "hocomoco_14_core_meme", "14"),
        ("development-exposed-v2", "SP1", "hocomoco_14_core_meme", "14"),
    ],
)
def test_active_development_panel_has_replayable_accepted_receipt_bundles(
    collection: str,
    motif_id: str,
    descriptor_id: str,
    source_revision: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = Path("generated/motif_models") / collection / motif_id
    artifact = json.loads((bundle / "artifact.json").read_text(encoding="utf-8"))
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    receipt = _assert_checked_receipt(bundle, monkeypatch)
    assert artifact["schema_version"] == "motif-model/v2"
    assert artifact["motif_id"] == motif_id
    assert manifest["model_digest"]
    assert manifest["source"]["descriptor_id"] == descriptor_id
    assert manifest["source"]["revision"] == source_revision
    assert manifest["source"]["redistribution_status"] == "redistributable"
    assert receipt["status"] == "accepted"
    assert receipt["model_digest"] == manifest["model_digest"]


def test_probability_normalization_uses_cross_python_fsum_semantics() -> None:
    normalized = validate_probability_rows([[0.040816, 0.612245, 0.040816, 0.306122]])[
        0
    ]

    assert [value.hex() for value in normalized] == [
        "0x1.4e5d710ea088bp-5",
        "0x1.397841c36dc61p-1",
        "0x1.4e5d710ea088bp-5",
        "0x1.397820357c51bp-2",
    ]


def test_regulondb_export_preserves_sites_and_refuses_pwm_inference(
    tmp_path: Path,
) -> None:
    source = _write_catalog_regulondb(
        tmp_path,
        """# RegulonDB Release: 13.0
1)riId\t4)regulatorName\t3)regulatorId\t6)tfrsID\t7)tfrsLeft\t8)tfrsRight\t9)strand\t10)tfrsSeq\t20)confidenceLevel\t26)tfrsPMIDS
ri-2\tCpxR\ttf-cpxr\tsite-2\t20\t31\treverse\taaaaTTGACAAcccc\tS\t222
ri-1\tCpxR\ttf-cpxr\tsite-1\t5\t12\tforward\taaaaACGTACGTcccc\tC\t111
ri-3\tLexA\ttf-lexa\tsite-3\t40\t47\tforward\taaaaTTTTAAAAcccc\tC\t333
""",
    )

    export = build_regulondb_site_export(
        source,
        regulator_name="CpxR",
        source_descriptor_id="regulondb_13_tf_riset_sites",
        orientation="genomic_forward",
        data_root=tmp_path,
    )

    site_set = export["artifact"]
    assert site_set["schema_version"] == "dnadesign-data.binding-site-set/v1"
    assert site_set["regulator"] == {"id": "tf-cpxr", "name": "CpxR"}
    assert site_set["sequence_semantics"] == "uppercase_tfrs_core_v1"
    assert site_set["orientation"] == "genomic_forward"
    assert site_set["widths"] == [7, 8]
    assert site_set["model_readiness"] == {
        "ready": False,
        "reason": "site sequences have unequal widths; alignment or window policy is required",
    }
    assert [site["site_id"] for site in site_set["sites"]] == ["site-1", "site-2"]
    assert site_set["sites"][0]["sequence"] == "ACGTACGT"
    assert site_set["sites"][1]["sequence"] == "TTGTCAA"
    assert site_set["sites"][1]["source_strands"] == ["-"]
    assert "probabilities" not in site_set
    assert export["manifest"]["output_schema"] == ("dnadesign-data.binding-site-set/v1")


def test_regulondb_export_rejects_ambiguous_regulator_identity(tmp_path: Path) -> None:
    source = _write_catalog_regulondb(
        tmp_path,
        """1)riId\t4)regulatorName\t3)regulatorId\t6)tfrsID\t7)tfrsLeft\t8)tfrsRight\t9)strand\t10)tfrsSeq\t20)confidenceLevel\t26)tfrsPMIDS
ri-1\tCpxR\ttf-a\tsite-1\t5\t12\tforward\taaaaACGTACGTcccc\tC\t111
ri-2\tCpxR\ttf-b\tsite-2\t20\t27\tforward\taaaaTTTTAAAAcccc\tS\t222
""",
    )

    with pytest.raises(MotifExportError, match="multiple regulator identifiers"):
        build_regulondb_site_export(
            source,
            regulator_name="CpxR",
            source_descriptor_id="regulondb_13_tf_riset_sites",
            orientation="genomic_forward",
            data_root=tmp_path,
        )


def test_regulondb_export_rejects_duplicate_normalized_headers(tmp_path: Path) -> None:
    source = _write_catalog_regulondb(
        tmp_path,
        """1)riId\t4)regulatorName\t3)regulatorId\t6)tfrsID\t7)tfrsLeft\t8)tfrsRight\t9)strand\t10)tfrsSeq\t20)confidenceLevel\t26)tfrsPMIDS\t99)regulatorName
ri-1\tCpxR\ttf-cpxr\tsite-1\t5\t12\tforward\taaaaACGTACGTcccc\tC\t111\tCpxR
""",
    )

    with pytest.raises(MotifExportError, match="duplicate normalized columns"):
        build_regulondb_site_export(
            source,
            regulator_name="CpxR",
            source_descriptor_id="regulondb_13_tf_riset_sites",
            orientation="genomic_forward",
            data_root=tmp_path,
        )


def test_regulondb_case_variant_name_replays_across_python_hash_seeds(
    tmp_path: Path,
) -> None:
    source = _write_catalog_regulondb(
        tmp_path,
        """1)riId\t4)regulatorName\t3)regulatorId\t6)tfrsID\t7)tfrsLeft\t8)tfrsRight\t9)strand\t10)tfrsSeq\t20)confidenceLevel\t26)tfrsPMIDS
ri-1\tcpxr\ttf-cpxr\tsite-1\t5\t12\tforward\taaaaACGTACGTcccc\tC\t111
ri-2\tCpxR\ttf-cpxr\tsite-2\t20\t27\tforward\taaaaTTTTAAAAcccc\tS\t222
""",
    )
    code = """
import json
import sys
from dnadesign_data.motifs import build_regulondb_site_export
value = build_regulondb_site_export(
    sys.argv[1], regulator_name="CPXR",
    source_descriptor_id="regulondb_13_tf_riset_sites",
    orientation="genomic_forward", data_root=sys.argv[2],
)
print(json.dumps(value, sort_keys=True, separators=(",", ":")))
"""
    outputs = []
    for seed in ("1", "2", "987654"):
        environment = dict(os.environ, PYTHONHASHSEED=seed)
        outputs.append(
            subprocess.run(
                [sys.executable, "-c", code, str(source), str(tmp_path)],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            ).stdout
        )

    assert len(set(outputs)) == 1
    assert json.loads(outputs[0])["artifact"]["regulator"]["name"] == "CpxR"


def test_regulondb_export_records_missing_site_dispositions(tmp_path: Path) -> None:
    source = _write_catalog_regulondb(
        tmp_path,
        """1)riId\t4)regulatorName\t3)regulatorId\t6)tfrsID\t7)tfrsLeft\t8)tfrsRight\t9)strand\t10)tfrsSeq\t20)confidenceLevel\t26)tfrsPMIDS
ri-1\tCpxR\ttf-cpxr\tsite-1\t5\t12\tforward\taaaaACGTACGTcccc\tC\t111
ri-2\tCpxR\ttf-cpxr\tsite-2\t20\t27\treverse\t\tS\t222
ri-3\tCpxR\ttf-cpxr\t\t\t\t\t\tW\t333
""",
    )

    export = build_regulondb_site_export(
        source,
        regulator_name="CpxR",
        source_descriptor_id="regulondb_13_tf_riset_sites",
        orientation="genomic_forward",
        data_root=tmp_path,
    )

    site_set = export["artifact"]
    assert [site["site_id"] for site in site_set["sites"]] == ["site-1"]
    assert site_set["selection_summary"] == {
        "matched_row_count": 3,
        "usable_observation_count": 1,
        "unique_site_count": 1,
        "duplicate_observation_count": 0,
        "excluded_row_count": 2,
        "exclusion_reasons": {
            "missing_site_identity": 1,
            "missing_site_sequence": 1,
        },
    }


def test_export_writer_is_create_only_and_emits_canonical_files(tmp_path: Path) -> None:
    source = _write_catalog_meme(
        tmp_path,
        "simple.txt",
        """MEME version 5
ALPHABET= ACGT
Background letter frequencies
A 0.25 C 0.25 G 0.25 T 0.25
MOTIF simple
letter-probability matrix: alength= 4 w= 1 nsites= 1 E= 0
0.25 0.25 0.25 0.25
""",
    )
    export = build_meme_motif_export(
        source,
        motif_id="simple",
        source_motif_id="simple",
        source_descriptor_id="omalley_2021_ecoli_meme",
        prior_weight=0.0,
        data_root=tmp_path,
    )
    output = tmp_path / "export"

    written = write_motif_source_export(export, output)

    assert written == output
    assert json.loads((output / "artifact.json").read_text()) == export["artifact"]
    assert json.loads((output / "manifest.json").read_text()) == export["manifest"]
    assert (output / "artifact.json").read_bytes().endswith(b"\n")
    with pytest.raises(MotifExportError, match="already exists"):
        write_motif_source_export(export, output)


def test_source_read_rejects_nonregular_files(tmp_path: Path) -> None:
    with pytest.raises(MotifExportError, match="regular file"):
        read_source_bytes(tmp_path)


def test_catalog_source_rejects_symbolic_link_ancestor(tmp_path: Path) -> None:
    external = tmp_path / "external"
    source = _write_catalog_meme(
        external,
        "simple.txt",
        """MEME version 5
ALPHABET= ACGT
Background letter frequencies
A 0.25 C 0.25 G 0.25 T 0.25
MOTIF simple
letter-probability matrix: alength= 4 w= 1 nsites= 1 E= 0
0.25 0.25 0.25 0.25
""",
    )
    data_root = tmp_path / "mirror"
    data_root.mkdir()
    (data_root / "sources").symlink_to(external / "sources", target_is_directory=True)
    linked_source = data_root / source.relative_to(external)

    with pytest.raises(MotifExportError, match="symbolic-link ancestor"):
        build_meme_motif_export(
            linked_source,
            motif_id="simple",
            source_motif_id="simple",
            source_descriptor_id="omalley_2021_ecoli_meme",
            prior_weight=0.0,
            data_root=data_root,
        )


def test_export_loader_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    export = tmp_path / "export"
    export.mkdir()
    (export / "artifact.json").write_text(
        '{"schema_version":"motif-model/v1","schema_version":"other"}\n',
        encoding="utf-8",
    )
    (export / "manifest.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(MotifExportError, match="duplicate JSON key"):
        load_motif_source_export(export)


@pytest.mark.parametrize("filename", ["artifact.json", "manifest.json"])
def test_export_loader_rejects_noncanonical_json_bytes(
    tmp_path: Path, filename: str
) -> None:
    source = _write_catalog_meme(
        tmp_path,
        "canonical.txt",
        """MEME version 5
ALPHABET= ACGT
Background letter frequencies
A 0.25 C 0.25 G 0.25 T 0.25
MOTIF canonical
letter-probability matrix: alength= 4 w= 1 nsites= 1 E= 0
0.25 0.25 0.25 0.25
""",
    )
    export = build_meme_motif_export(
        source,
        motif_id="canonical",
        source_motif_id="canonical",
        source_descriptor_id="omalley_2021_ecoli_meme",
        prior_weight=0.0,
        data_root=tmp_path,
    )
    bundle = tmp_path / "noncanonical"
    write_motif_source_export(export, bundle)
    value = json.loads((bundle / filename).read_bytes())
    (bundle / filename).write_text(json.dumps(value, indent=2), encoding="utf-8")

    with pytest.raises(MotifExportError, match="canonical JSON bytes"):
        load_motif_source_export(bundle)


def test_export_writer_rejects_symbolic_link_parent(tmp_path: Path) -> None:
    source = _write_catalog_meme(
        tmp_path,
        "safe.txt",
        """MEME version 5
ALPHABET= ACGT
Background letter frequencies
A 0.25 C 0.25 G 0.25 T 0.25
MOTIF safe
letter-probability matrix: alength= 4 w= 1 nsites= 1 E= 0
0.25 0.25 0.25 0.25
""",
    )
    export = build_meme_motif_export(
        source,
        motif_id="safe",
        source_motif_id="safe",
        source_descriptor_id="omalley_2021_ecoli_meme",
        prior_weight=0.0,
        data_root=tmp_path,
    )
    actual = tmp_path / "actual"
    actual.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(actual, target_is_directory=True)

    with pytest.raises(MotifExportError, match="symbolic-link ancestor"):
        write_motif_source_export(export, linked / "new-export")


def test_receipt_binds_catalog_owner_git_source_model_and_canonical_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    export, source = _accepted_model_export(tmp_path, monkeypatch)
    bundle = _receipt_bundle(tmp_path, export)
    repository, owner_revision, artifact_ref = _git_authority(tmp_path, export)

    receipt = build_motif_export_receipt(
        bundle,
        owner_revision=owner_revision,
        canonical_artifact_ref=artifact_ref,
        owner_repository_path=repository,
        data_root=tmp_path,
    )

    assert receipt == {
        "schema": "dnadesign-data.motif-export-receipt/v1",
        "status": "accepted",
        "owner_repository": "e-south/dnadesign-data",
        "owner_revision": owner_revision,
        "motif_id": "simple",
        "source_descriptor_id": "omalley_2021_ecoli_meme",
        "source_revision": "s41592-021-01312-2-supplementary-data-2",
        "source_artifact_sha256": _sha256(source),
        "canonical_artifact_ref": artifact_ref,
        "canonical_file_sha256": export["manifest"]["artifact_sha256"],
        "canonical_media_type": "application/json",
        "canonical_schema": "motif-model/v2",
        "model_digest": export["manifest"]["model_digest"],
        "conversion_contract": "direct_probability_model_v1",
        "redistribution_status": "redistributable",
    }
    assert (
        receipt["canonical_file_sha256"]
        == hashlib.sha256((bundle / "artifact.json").read_bytes()).hexdigest()
    )
    assert (
        revalidate_motif_export_receipt(
            bundle,
            receipt,
            owner_repository_path=repository,
            data_root=tmp_path,
        )
        == receipt
    )


def test_receipt_owner_revision_may_be_reachable_from_newer_integration_tip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    export, _source = _accepted_model_export(tmp_path, monkeypatch)
    bundle = _receipt_bundle(tmp_path, export)
    repository, owner_revision, artifact_ref = _git_authority(tmp_path, export)
    (repository / "README.md").write_text("integration advanced\n", encoding="utf-8")
    integration_revision = _commit_authority_change(repository, "advance main")
    monkeypatch.setattr(
        receipt_module,
        "_query_canonical_remote_revisions",
        lambda: frozenset({integration_revision}),
    )

    receipt = build_motif_export_receipt(
        bundle,
        owner_revision=owner_revision,
        canonical_artifact_ref=artifact_ref,
        owner_repository_path=repository,
        data_root=tmp_path,
    )

    assert receipt["owner_revision"] == owner_revision


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value.update(extra="bad"), "receipt keys"),
        (
            lambda value: value.update(owner_repository="somewhere/else"),
            "owner_repository",
        ),
        (lambda value: value.update(owner_revision="a" * 39), "owner_revision"),
        (
            lambda value: value.update(canonical_media_type="text/plain"),
            "canonical_media_type",
        ),
        (
            lambda value: value.update(conversion_contract="invented_v1"),
            "revalidated authority",
        ),
        (
            lambda value: value.update(source_artifact_sha256="0" * 64),
            "revalidated authority",
        ),
    ],
)
def test_existing_receipt_revalidation_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: object,
    message: str,
) -> None:
    export, _source = _accepted_model_export(tmp_path, monkeypatch)
    bundle = _receipt_bundle(tmp_path, export)
    repository, owner_revision, artifact_ref = _git_authority(tmp_path, export)
    receipt = build_motif_export_receipt(
        bundle,
        owner_revision=owner_revision,
        canonical_artifact_ref=artifact_ref,
        owner_repository_path=repository,
        data_root=tmp_path,
    )
    malformed = copy.deepcopy(receipt)
    mutation(malformed)  # type: ignore[operator]

    with pytest.raises(MotifExportError, match=message):
        revalidate_motif_export_receipt(
            bundle,
            malformed,
            owner_repository_path=repository,
            data_root=tmp_path,
        )


@pytest.mark.parametrize("provider", ["meme", "jaspar"])
def test_receipt_replays_source_conversion_and_rejects_self_consistent_tampering(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
) -> None:
    if provider == "meme":
        export, _source = _accepted_model_export(tmp_path, monkeypatch)
    else:
        source = _write_catalog_jaspar_counts(
            tmp_path,
            "MA0001.1.jaspar",
            ">MA0001.1 Example\nA [ 4 ]\nC [ 0 ]\nG [ 0 ]\nT [ 0 ]\n",
        )
        export = build_jaspar_count_motif_export(
            source,
            motif_id="simple",
            source_motif_id="MA0001.1",
            source_descriptor_id="jaspar_2026_core_counts",
            background=[0.25, 0.25, 0.25, 0.25],
            data_root=tmp_path,
        )
        descriptor = next(
            item
            for item in known_motif_source_files()
            if item.source_id == "jaspar_2026_core_counts"
        )
        monkeypatch.setattr(
            receipt_module, "known_motif_source_files", lambda: (descriptor,)
        )
    tampered = copy.deepcopy(export)
    probabilities = tampered["artifact"]["probabilities"][0]
    if provider == "meme":
        tampered["artifact"]["probabilities"][0] = [0.4, 0.2, 0.2, 0.2]
    else:
        probabilities[0], probabilities[1] = probabilities[1], probabilities[0]
    artifact_bytes = canonical_json_bytes(tampered["artifact"])
    tampered["manifest"]["artifact_sha256"] = hashlib.sha256(artifact_bytes).hexdigest()
    tampered["manifest"]["model_digest"] = receipt_module.model_digest(
        tampered["artifact"]
    )
    bundle = _receipt_bundle(tmp_path, tampered)
    repository, owner_revision, artifact_ref = _git_authority(tmp_path, tampered)

    with pytest.raises(MotifExportError, match="source conversion replay"):
        build_motif_export_receipt(
            bundle,
            owner_revision=owner_revision,
            canonical_artifact_ref=artifact_ref,
            owner_repository_path=repository,
            data_root=tmp_path,
        )


def test_count_receipt_replays_exact_source_conversion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _write_catalog_jaspar_counts(
        tmp_path,
        "MA0001.1.jaspar",
        ">MA0001.1 Example\nA [ 4 ]\nC [ 0 ]\nG [ 0 ]\nT [ 0 ]\n",
    )
    export = build_jaspar_count_motif_export(
        source,
        motif_id="simple",
        source_motif_id="MA0001.1",
        source_descriptor_id="jaspar_2026_core_counts",
        background=[0.25, 0.25, 0.25, 0.25],
        data_root=tmp_path,
    )
    bundle = _receipt_bundle(tmp_path, export)
    repository, owner_revision, artifact_ref = _git_authority(tmp_path, export)
    monkeypatch.setattr(
        receipt_module,
        "_query_canonical_remote_revisions",
        lambda: frozenset({owner_revision}),
    )

    receipt = build_motif_export_receipt(
        bundle,
        owner_revision=owner_revision,
        canonical_artifact_ref=artifact_ref,
        owner_repository_path=repository,
        data_root=tmp_path,
    )

    assert receipt["conversion_contract"] == "count_matrix_sqrt_n_background_prior_v1"
    assert receipt["source_artifact_sha256"] == export["artifact"]["source_digest"]


def test_count_receipt_rejects_alternate_background_despite_self_consistency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _write_catalog_jaspar_counts(
        tmp_path,
        "MA0001.1.jaspar",
        ">MA0001.1 Example\nA [ 4 ]\nC [ 0 ]\nG [ 0 ]\nT [ 0 ]\n",
    )
    admitted = build_jaspar_count_motif_export(
        source,
        motif_id="simple",
        source_motif_id="MA0001.1",
        source_descriptor_id="jaspar_2026_core_counts",
        background=[0.25, 0.25, 0.25, 0.25],
        data_root=tmp_path,
    )
    alternate = build_jaspar_count_motif_export(
        source,
        motif_id="simple",
        source_motif_id="MA0001.1",
        source_descriptor_id="jaspar_2026_core_counts",
        background=[0.4, 0.1, 0.2, 0.3],
        data_root=tmp_path,
    )
    admitted["artifact"] = alternate["artifact"]
    artifact_bytes = canonical_json_bytes(admitted["artifact"])
    admitted["manifest"]["artifact_sha256"] = hashlib.sha256(artifact_bytes).hexdigest()
    admitted["manifest"]["model_digest"] = receipt_module.model_digest(
        admitted["artifact"]
    )
    bundle = _receipt_bundle(tmp_path, admitted)
    repository, owner_revision, artifact_ref = _git_authority(tmp_path, admitted)
    monkeypatch.setattr(
        receipt_module,
        "_query_canonical_remote_revisions",
        lambda: frozenset({owner_revision}),
    )

    with pytest.raises(MotifExportError, match="selection background"):
        build_motif_export_receipt(
            bundle,
            owner_revision=owner_revision,
            canonical_artifact_ref=artifact_ref,
            owner_repository_path=repository,
            data_root=tmp_path,
        )


def test_receipt_refuses_non_model_or_unresolved_redistribution(tmp_path: Path) -> None:
    source = _write_catalog_regulondb(
        tmp_path,
        """1)riId\t4)regulatorName\t3)regulatorId\t6)tfrsID\t7)tfrsLeft\t8)tfrsRight\t9)strand\t10)tfrsSeq\t20)confidenceLevel\t26)tfrsPMIDS
ri-1\tCpxR\ttf-cpxr\tsite-1\t5\t12\tforward\taaaaACGTACGTcccc\tC\t111
""",
    )
    export = build_regulondb_site_export(
        source,
        regulator_name="CpxR",
        source_descriptor_id="regulondb_13_tf_riset_sites",
        orientation="genomic_forward",
        data_root=tmp_path,
    )

    with pytest.raises(MotifExportError, match="supported motif model"):
        bundle = _receipt_bundle(tmp_path, export)
        build_motif_export_receipt(
            bundle,
            owner_revision="a" * 40,
            canonical_artifact_ref=(
                f"storage:dnadesign-data/sites@sha256:{'b' * 64}#sites/cpxR.json"
            ),
            owner_repository_path=tmp_path,
            data_root=tmp_path,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value["manifest"].update(extra=True), "manifest keys"),
        (lambda value: value["manifest"]["source"].update(extra=True), "source keys"),
        (
            lambda value: value["manifest"]["selection"].update(extra=True),
            "selection keys",
        ),
        (
            lambda value: value["artifact"].update(extra=True),
            "motif-model keys",
        ),
        (
            lambda value: value["manifest"]["source"].update(revision="spoofed"),
            "catalog descriptor",
        ),
        (
            lambda value: value["manifest"]["source"].update(
                redistribution_status="private_storage"
            ),
            "catalog descriptor",
        ),
        (
            lambda value: value["manifest"]["source"].update(artifact_name="other.txt"),
            "source cross-link",
        ),
        (
            lambda value: value["manifest"]["selection"].update(motif_id="other"),
            "selection cross-link",
        ),
        (
            lambda value: value["artifact"].update(motif_id="../bad\nidentity"),
            "Motif Balance identity",
        ),
        (
            lambda value: value["manifest"]["selection"].update(
                source_motif_id="../bad\nidentity"
            ),
            "Motif Balance identity",
        ),
        (
            lambda value: value["manifest"].update(model_digest="0" * 64),
            "model digest",
        ),
        (
            lambda value: value["artifact"]["conversion"].update(extra=True),
            "conversion keys",
        ),
        (
            lambda value: value["artifact"]["conversion"].update(
                source_motif_id="other"
            ),
            "conversion source_motif_id",
        ),
        (
            lambda value: value["artifact"].update(source_digest="0" * 64),
            "source cross-link",
        ),
        (
            lambda value: value["artifact"]["probabilities"][0].__setitem__(0, 0.30),
            "probability row 0 must sum to one",
        ),
        (
            lambda value: value["artifact"]["probabilities"][0].__setitem__(
                0, "not-a-number"
            ),
            "finite nonnegative values",
        ),
    ],
)
def test_receipt_rejects_noncanonical_or_cross_linked_model_exports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: object,
    message: str,
) -> None:
    export, _source = _accepted_model_export(tmp_path, monkeypatch)
    if "conversion" in message:
        export = build_meme_motif_export(
            _source,
            motif_id="simple",
            source_motif_id="simple",
            source_descriptor_id="omalley_2021_ecoli_meme",
            prior_weight=0.1,
            data_root=tmp_path,
        )
        export["manifest"]["source"]["redistribution_status"] = "redistributable"
    malformed = copy.deepcopy(export)
    mutation(malformed)  # type: ignore[operator]
    bundle = _receipt_bundle(tmp_path, malformed)
    repository, owner_revision, artifact_ref = _git_authority(tmp_path, export)

    with pytest.raises(MotifExportError, match=message):
        build_motif_export_receipt(
            bundle,
            owner_revision=owner_revision,
            canonical_artifact_ref=artifact_ref,
            owner_repository_path=repository,
            data_root=tmp_path,
        )


@pytest.mark.parametrize(
    "artifact_ref",
    [
        "storage:dnadesign-data/models@sha256:" + "b" * 64 + "#/models/simple.json",
        "storage:dnadesign-data/models@sha256:" + "b" * 64 + "#models/../simple.json",
        "storage:dnadesign-data/models@sha256:" + "b" * 64 + "#models\\simple.json",
        "storage:dnadesign-data/models@sha256:" + "b" * 64 + "#models//simple.json",
        "storage:dnadesign-data/models@sha256:" + "b" * 64 + "#models/./simple.json",
    ],
)
def test_receipt_rejects_traversing_or_noncanonical_artifact_refs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    artifact_ref: str,
) -> None:
    export, _source = _accepted_model_export(tmp_path, monkeypatch)
    bundle = _receipt_bundle(tmp_path, export)
    repository, owner_revision, _artifact_ref = _git_authority(tmp_path, export)

    with pytest.raises(MotifExportError, match="canonical_artifact_ref"):
        build_motif_export_receipt(
            bundle,
            owner_revision=owner_revision,
            canonical_artifact_ref=artifact_ref,
            owner_repository_path=repository,
            data_root=tmp_path,
        )


def test_receipt_fails_closed_for_storage_and_rejects_unverified_git_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    export, _source = _accepted_model_export(tmp_path, monkeypatch)
    bundle = _receipt_bundle(tmp_path, export)
    repository, owner_revision, artifact_ref = _git_authority(tmp_path, export)

    with pytest.raises(MotifExportError, match="Storage.*verifier"):
        build_motif_export_receipt(
            bundle,
            owner_revision=owner_revision,
            canonical_artifact_ref=(
                f"storage:dnadesign-data/models@sha256:{'b' * 64}#models/simple.json"
            ),
            owner_repository_path=repository,
            data_root=tmp_path,
        )

    with pytest.raises(MotifExportError, match="owner_revision.*does not exist"):
        build_motif_export_receipt(
            bundle,
            owner_revision="a" * 40,
            canonical_artifact_ref=(
                f"git:e-south/dnadesign-data@{'a' * 40}#models/simple.json"
            ),
            owner_repository_path=repository,
            data_root=tmp_path,
        )

    with pytest.raises(MotifExportError, match="Git target does not exist"):
        build_motif_export_receipt(
            bundle,
            owner_revision=owner_revision,
            canonical_artifact_ref=(
                f"git:e-south/dnadesign-data@{owner_revision}#models/missing.json"
            ),
            owner_repository_path=repository,
            data_root=tmp_path,
        )

    with monkeypatch.context() as remote_proof:
        remote_proof.setattr(
            receipt_module,
            "_query_canonical_remote_revisions",
            lambda: frozenset(),
        )
        with pytest.raises(MotifExportError, match="canonical GitHub remote"):
            build_motif_export_receipt(
                bundle,
                owner_revision=owner_revision,
                canonical_artifact_ref=artifact_ref,
                owner_repository_path=repository,
                data_root=tmp_path,
            )

    (repository / "models/simple.json").write_text("{}\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(repository), "add", "models/simple.json"], check=True
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "-c",
            "user.name=Receipt Test",
            "-c",
            "user.email=receipt@example.invalid",
            "commit",
            "-qm",
            "different model",
        ],
        check=True,
    )
    different_revision = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    with pytest.raises(MotifExportError, match="Git target bytes"):
        build_motif_export_receipt(
            bundle,
            owner_revision=different_revision,
            canonical_artifact_ref=artifact_ref.replace(
                owner_revision, different_revision
            ),
            owner_repository_path=repository,
            data_root=tmp_path,
        )


def test_receipt_rechecks_catalog_source_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    export, source = _accepted_model_export(tmp_path, monkeypatch)
    bundle = _receipt_bundle(tmp_path, export)
    repository, owner_revision, artifact_ref = _git_authority(tmp_path, export)
    source.write_text(source.read_text() + "# changed after export\n", encoding="utf-8")

    with pytest.raises(MotifExportError, match="catalog source bytes"):
        build_motif_export_receipt(
            bundle,
            owner_revision=owner_revision,
            canonical_artifact_ref=artifact_ref,
            owner_repository_path=repository,
            data_root=tmp_path,
        )


def test_receipt_binds_catalog_source_blob_to_remote_proven_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    export, _source = _accepted_model_export(tmp_path, monkeypatch)
    bundle = _receipt_bundle(tmp_path, export)
    repository, owner_revision, artifact_ref = _git_authority(tmp_path, export)
    git_source = (
        repository
        / "sources/literature/OMalley_et_al/escherichia_coli_motifs/simple.txt"
    )
    altered = bytearray(git_source.read_bytes())
    altered[0] = ord("X") if altered[0] != ord("X") else ord("Y")
    git_source.write_bytes(altered)
    different_revision = _commit_authority_change(repository, "alter source blob")

    with pytest.raises(MotifExportError, match="catalog source Git target bytes"):
        build_motif_export_receipt(
            bundle,
            owner_revision=different_revision,
            canonical_artifact_ref=artifact_ref.replace(
                owner_revision, different_revision
            ),
            owner_repository_path=repository,
            data_root=tmp_path,
        )


def test_receipt_bounds_git_blob_before_reading_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    export, _source = _accepted_model_export(tmp_path, monkeypatch)
    bundle = _receipt_bundle(tmp_path, export)
    repository, owner_revision, artifact_ref = _git_authority(tmp_path, export)
    git_artifact = repository / "models/simple.json"
    git_artifact.write_bytes(git_artifact.read_bytes() + b" ")
    different_revision = _commit_authority_change(repository, "oversize model blob")

    with pytest.raises(MotifExportError, match="artifact Git blob exceeds"):
        build_motif_export_receipt(
            bundle,
            owner_revision=different_revision,
            canonical_artifact_ref=artifact_ref.replace(
                owner_revision, different_revision
            ),
            owner_repository_path=repository,
            data_root=tmp_path,
        )


@pytest.mark.parametrize(
    "result",
    [
        subprocess.CompletedProcess([], 1, stdout=b"", stderr=b"network failed"),
        subprocess.CompletedProcess([], 0, stdout=b"not-a-ref\n", stderr=b""),
        subprocess.CompletedProcess([], 0, stdout=b"", stderr=b""),
    ],
)
def test_canonical_remote_query_fails_closed_on_error_or_malformed_output(
    monkeypatch: pytest.MonkeyPatch,
    result: subprocess.CompletedProcess[bytes],
) -> None:
    monkeypatch.setattr(
        receipt_module.subprocess, "run", lambda *args, **kwargs: result
    )

    with pytest.raises(MotifExportError, match="canonical GitHub remote"):
        receipt_module._query_canonical_remote_revisions()


def test_canonical_remote_query_fails_closed_on_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def timeout(*args: object, **kwargs: object) -> object:
        raise subprocess.TimeoutExpired(cmd="git ls-remote", timeout=15)

    monkeypatch.setattr(receipt_module.subprocess, "run", timeout)

    with pytest.raises(MotifExportError, match="canonical GitHub remote"):
        receipt_module._query_canonical_remote_revisions()


def test_canonical_remote_query_uses_only_fixed_public_url_and_parses_refs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []
    revision = "a" * 40
    feature_revision = "b" * 40
    nonrelease_tag_revision = "c" * 40

    def query(
        arguments: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        calls.append(arguments)
        return subprocess.CompletedProcess(
            arguments,
            0,
            stdout=(
                f"{revision}\trefs/heads/main\n"
                f"{feature_revision}\trefs/heads/feature\n"
                f"{nonrelease_tag_revision}\trefs/tags/scratch\n"
                f"{revision}\trefs/tags/v1\n"
            ).encode("ascii"),
            stderr=b"",
        )

    monkeypatch.setattr(receipt_module.subprocess, "run", query)

    assert receipt_module._query_canonical_remote_revisions() == frozenset({revision})
    assert calls == [
        [
            "git",
            "ls-remote",
            "--heads",
            "--tags",
            "https://github.com/e-south/dnadesign-data.git",
        ]
    ]
