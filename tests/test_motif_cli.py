from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_provider_catalog_cli_is_machine_readable() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dnadesign_data.motifs.cli",
            "providers",
            "--indent",
            "0",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["schema_version"] == (
        "dnadesign-data.motif-source-provider-catalog/v1"
    )
    assert payload["provider_count"] == 3


def test_export_meme_cli_uses_catalog_authority_and_storage_receipt_requires_advertised_revision(
    tmp_path: Path,
) -> None:
    source = (
        tmp_path / "sources/literature/OMalley_et_al/escherichia_coli_motifs/simple.txt"
    )
    source.parent.mkdir(parents=True)
    source.write_text(
        """MEME version 5
ALPHABET= ACGT
Background letter frequencies
A 0.25 C 0.25 G 0.25 T 0.25
MOTIF simple
letter-probability matrix: alength= 4 w= 1 nsites= 1 E= 0
0.25 0.25 0.25 0.25
""",
        encoding="utf-8",
    )
    output = tmp_path / "model-export"
    export_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dnadesign_data.motifs.cli",
            "export-meme",
            str(source),
            "--motif-id",
            "simple",
            "--source-motif-id",
            "simple",
            "--source-descriptor-id",
            "omalley_2021_ecoli_meme",
            "--data-root",
            str(tmp_path),
            "--prior-weight",
            "0",
            "--out",
            str(output),
            "--indent",
            "0",
            "--json-errors",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    export_payload = json.loads(export_result.stdout)
    assert export_payload["report_kind"] == "motif_source_export_written"
    assert export_payload["output_schema"] == "motif-model/v2"
    assert (output / "artifact.json").is_file()
    assert (output / "manifest.json").is_file()

    receipt_path = tmp_path / "simple-receipt.json"
    artifact_ref = f"storage:dnadesign-data/simple@sha256:{'b' * 64}#models/simple.json"
    receipt_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dnadesign_data.motifs.cli",
            "receipt",
            str(output),
            "--owner-revision",
            "a" * 40,
            "--owner-repository-path",
            str(Path.cwd()),
            "--data-root",
            str(tmp_path),
            "--canonical-artifact-ref",
            artifact_ref,
            "--out",
            str(receipt_path),
            "--indent",
            "0",
            "--json-errors",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert receipt_result.returncode == 2
    assert receipt_result.stdout == ""
    receipt_payload = json.loads(receipt_result.stderr)
    assert receipt_payload["report_kind"] == "motif_source_error"
    assert "Storage owner_revision is not advertised" in receipt_payload["message"]
    assert not receipt_path.exists()


def test_export_meme_cli_accepts_an_explicit_target_background(tmp_path: Path) -> None:
    source = (
        tmp_path / "sources/literature/OMalley_et_al/escherichia_coli_motifs/simple.txt"
    )
    source.parent.mkdir(parents=True)
    source.write_text(
        """MEME version 5
ALPHABET= ACGT
Background letter frequencies
A 0.40 C 0.10 G 0.20 T 0.30
MOTIF simple
letter-probability matrix: alength= 4 w= 1 nsites= 1 E= 0
1.0 0.0 0.0 0.0
""",
        encoding="utf-8",
    )
    output = tmp_path / "model-export"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dnadesign_data.motifs.cli",
            "export-meme",
            str(source),
            "--motif-id",
            "simple",
            "--source-motif-id",
            "simple",
            "--source-descriptor-id",
            "omalley_2021_ecoli_meme",
            "--data-root",
            str(tmp_path),
            "--prior-weight",
            "0.1",
            "--background",
            "0.25,0.25,0.25,0.25",
            "--out",
            str(output),
            "--indent",
            "0",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout)["output_schema"] == "motif-model/v2"
    artifact = json.loads((output / "artifact.json").read_text())
    manifest = json.loads((output / "manifest.json").read_text())
    assert artifact["background"] == [0.25, 0.25, 0.25, 0.25]
    assert artifact["conversion"]["source_background"] == [0.4, 0.1, 0.2, 0.3]
    assert manifest["selection"]["target_background_policy"] == (
        "explicit_target_background_v1"
    )


def test_export_cli_returns_structured_contract_error(tmp_path: Path) -> None:
    missing = (
        tmp_path
        / "sources/literature/OMalley_et_al/escherichia_coli_motifs/missing.txt"
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dnadesign_data.motifs.cli",
            "export-meme",
            str(missing),
            "--motif-id",
            "simple",
            "--source-motif-id",
            "simple",
            "--source-descriptor-id",
            "omalley_2021_ecoli_meme",
            "--data-root",
            str(tmp_path),
            "--prior-weight",
            "0.1",
            "--out",
            str(tmp_path / "out"),
            "--json-errors",
            "--indent",
            "0",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert result.stdout == ""
    payload = json.loads(result.stderr)
    assert payload["report_kind"] == "motif_source_error"
    assert payload["error_type"] == "MotifExportError"
    assert "missing.txt" in payload["message"]
    assert str(tmp_path) not in payload["message"]


def test_export_jaspar_counts_cli_uses_sqrt_n_conversion(tmp_path: Path) -> None:
    source = tmp_path / "sources/databases/jaspar/2026/CORE-counts/MA0001.1.jaspar"
    source.parent.mkdir(parents=True)
    source.write_text(
        ">MA0001.1 Example\nA [ 4 ]\nC [ 0 ]\nG [ 0 ]\nT [ 0 ]\n",
        encoding="utf-8",
    )
    output = tmp_path / "model-export"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dnadesign_data.motifs.cli",
            "export-jaspar-counts",
            str(source),
            "--motif-id",
            "Example",
            "--source-motif-id",
            "MA0001.1",
            "--source-descriptor-id",
            "jaspar_2026_core_counts",
            "--data-root",
            str(tmp_path),
            "--background",
            "0.25,0.25,0.25,0.25",
            "--out",
            str(output),
            "--indent",
            "0",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout)["output_schema"] == "motif-model/v2"
    artifact = json.loads((output / "artifact.json").read_text())
    assert artifact["conversion"]["method"] == "count_matrix_sqrt_n_background_prior_v1"
    assert artifact["conversion"]["schema_version"] == "motif-conversion/v2"
    assert artifact["conversion"]["position_observed_counts"] == [4.0]
    assert artifact["conversion"]["position_prior_masses"] == [2.0]
    assert artifact["conversion"]["position_denominators"] == [6.0]


def test_build_pool_cli_emits_path_free_sealed_inventory(tmp_path: Path) -> None:
    request = Path("generated/motif_models/pools/development-exposed-v2.request.json")
    output = tmp_path / "pool.json"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dnadesign_data.motifs.cli",
            "build-pool",
            str(request),
            "--repository-root",
            str(Path.cwd()),
            "--out",
            str(output),
            "--indent",
            "0",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout)["admission_status"] == "development_only"
    payload = json.loads(output.read_text())
    assert payload["seal_sha256"]
    assert all("bundle_path" not in model for model in payload["models"])
