from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from dnadesign_data.catalog import sources as catalog_sources
from dnadesign_data.catalog.regulatory_parts import PromoterSourceFile
from dnadesign_data.catalog.sources import (
    SourceCatalogError,
    build_source_catalog_payload,
    check_source_catalog_payload,
)


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("fixture\n", encoding="utf-8")


def test_build_source_catalog_payload_lists_available_sources(tmp_path: Path) -> None:
    _touch(tmp_path / "sources/databases/regulondb/13.0/promoters/PromoterSet.tsv")

    payload = build_source_catalog_payload(tmp_path, kind="promoter")

    assert payload["schema_version"] == "dnadesign_data.source_catalog.v1"
    assert payload["record_count"] == 1
    assert payload["local_file_available_count"] == 1
    assert payload["service_available_count"] == 0
    records = payload["records"]
    assert isinstance(records, list)
    assert records[0]["source_id"] == "regulondb_13_promoter_set"
    assert records[0]["available"] is True


def test_build_source_catalog_payload_can_include_missing_sources(
    tmp_path: Path,
) -> None:
    payload = build_source_catalog_payload(
        tmp_path,
        kind="regulator-identity",
        include_missing=True,
    )

    assert payload["record_count"] == 2
    assert {record["available"] for record in payload["records"]} == {False}


def test_source_catalog_cli_emits_json(tmp_path: Path) -> None:
    _touch(
        tmp_path
        / "sources/databases/regulondb/11.0/network_associations/network_tf_tu.txt"
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dnadesign_data.catalog.cli",
            "list",
            "--root",
            str(tmp_path),
            "--kind",
            "promoter-association",
            "--format",
            "json",
            "--indent",
            "0",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["record_count"] == 1
    assert payload["records"][0]["source_id"] == "regulondb_11_network_tf_tu"


def test_source_catalog_cli_emits_schema_json() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dnadesign_data.catalog.cli",
            "schema",
            "--format",
            "json",
            "--indent",
            "0",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["report_kind"] == "source_catalog_schema"
    assert "promoter-association" in payload["source_kind_choices"]
    assert "motif-source" in payload["source_kind_choices"]
    assert payload["commands"]["check"]["exit_codes"]["1"] == (
        "readiness contract failed"
    )
    assert (
        "local_file_available_count" in payload["payload_fields"]["readiness_metrics"]
    )
    assert payload["payload_fields"]["motif_source_record_fields"] == [
        "source_kind",
        "output_capability",
        "redistribution_status",
        "retrieval_url",
        "rights_url",
        "retrieved_on",
    ]


def test_source_catalog_lists_motif_source_capabilities(tmp_path: Path) -> None:
    _touch(
        tmp_path / "sources/literature/OMalley_et_al/escherichia_coli_motifs/cpxR.txt"
    )

    payload = build_source_catalog_payload(tmp_path, kind="motif-source")

    assert payload["record_count"] == 1
    record = payload["records"][0]
    assert record["source_id"] == "omalley_2021_ecoli_meme"
    assert record["output_capability"] == "motif-model/v2"
    assert record["redistribution_status"] == "private_storage"


def test_source_catalog_resolve_fails_fast_on_missing_source(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dnadesign_data.catalog.cli",
            "resolve",
            "--root",
            str(tmp_path),
            "regulondb_13_promoter_set",
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
    assert payload["report_kind"] == "source_catalog_error"
    assert payload["ok"] is False
    assert "unavailable" in payload["message"]


def test_source_catalog_resolve_can_allow_missing(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dnadesign_data.catalog.cli",
            "resolve",
            "--root",
            str(tmp_path),
            "regulondb_13_promoter_set",
            "--allow-missing",
            "--indent",
            "0",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["source_id"] == "regulondb_13_promoter_set"
    assert payload["available"] is False


def test_source_catalog_check_summary_only_reports_required_sources(
    tmp_path: Path,
) -> None:
    _touch(tmp_path / "sources/databases/regulondb/13.0/binding_sites/TF-RISet.tsv")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dnadesign_data.catalog.cli",
            "check",
            "--root",
            str(tmp_path),
            "--kind",
            "promoter-association",
            "--require-source",
            "regulondb_13_tf_riset",
            "--summary-only",
            "--indent",
            "0",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["records_included"] is False
    assert payload["records"] == []
    assert payload["required_source_ids"] == ["regulondb_13_tf_riset"]


def test_source_catalog_check_exits_nonzero_when_required_source_is_missing(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dnadesign_data.catalog.cli",
            "check",
            "--root",
            str(tmp_path),
            "--kind",
            "promoter-association",
            "--require-source",
            "regulondb_13_tf_riset",
            "--summary-only",
            "--indent",
            "0",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert result.returncode == 1
    assert payload["ok"] is False
    assert payload["missing_required_source_ids"] == ["regulondb_13_tf_riset"]


def test_source_catalog_check_does_not_treat_services_as_local_data(
    tmp_path: Path,
) -> None:
    payload = check_source_catalog_payload(tmp_path, kind="all")

    assert payload["ok"] is False
    assert payload["available_count"] == 1
    assert payload["known_local_file_count"] > 1
    assert payload["local_file_available_count"] == 0


def test_source_catalog_check_requires_materialized_local_file_sources(
    tmp_path: Path,
) -> None:
    payload = check_source_catalog_payload(
        tmp_path,
        kind="all",
        required_source_ids=["biocyc_smarttable_go_terms"],
    )

    assert payload["ok"] is False
    assert payload["available_count"] == 1
    assert payload["local_file_available_count"] == 0
    assert payload["missing_required_source_ids"] == ["biocyc_smarttable_go_terms"]


def test_source_catalog_fails_fast_on_duplicate_source_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = PromoterSourceFile(
        source_id="duplicate_source",
        source="fixture",
        release="1.0",
        path="sources/databases/fixture/1.0/table.tsv",
        table="table.tsv",
        stratum="fixture",
        role="fixture",
        file_format="tsv",
        parser_hint="fixture",
        creates_base_rows=True,
    )
    monkeypatch.setattr(
        catalog_sources,
        "known_promoter_source_files",
        lambda: (source, source),
    )

    with pytest.raises(SourceCatalogError, match="duplicate source IDs"):
        list(
            catalog_sources.iter_source_records(
                tmp_path,
                kind="promoter",
                include_missing=True,
            )
        )


def test_source_catalog_list_fails_fast_on_missing_root(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dnadesign_data.catalog.cli",
            "list",
            "--root",
            str(tmp_path / "missing"),
            "--json-errors",
            "--indent",
            "0",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stderr)

    assert result.returncode == 2
    assert payload["error_type"] == "SourceCatalogError"
    assert "root does not exist" in payload["message"]
