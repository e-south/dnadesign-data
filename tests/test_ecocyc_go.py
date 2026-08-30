from __future__ import annotations

import csv
import gzip
from pathlib import Path

import pytest

from dnadesign_data.catalog.functional_annotations import GO_RELEASE
from dnadesign_data.functional import ecocyc_go
from dnadesign_data.functional.ecocyc_go import (
    build_ecocyc_go_artifacts,
    download_raw_sources,
)


def _write_gaf(path: Path, rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
        handle.write("!gaf-version: 2.2\n")
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerows(rows)


def _write_obo(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(  # noqa: FLY002 - fixture lines mirror the source format
            [
                "format-version: 1.2",
                "",
                "[Term]",
                "id: GO:0003700",
                "name: DNA-binding transcription factor activity",
                "namespace: molecular_function",
                "",
                "[Term]",
                "id: GO:0006355",
                "name: regulation of DNA-templated transcription",
                "namespace: biological_process",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_network_regulator_gene(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(  # noqa: FLY002 - fixture lines are intentionally tabular
            [
                "# fixture",
                (
                    "1)regulatorId\t2)regulatorName\t3)RegulatorGeneName"
                    "\t4)regulatedId\t5)regulatedName\t6)function\t7)confidenceLevel "
                ),
                "RDBECOLITFC00001\tCpxR\tcpxR\tRDBECOLIGNC00001\tspy\t+\tS ",
                "RDBECOLITFC00002\tComposite\tfoo, cpxR\tRDBECOLIGNC00002\tbar\t-\tW ",
                "RDBECOLICNC00063\tppGpp\t\tRDBECOLIGNC00003\thisM\t-\tW ",
            ]
        ),
        encoding="utf-8",
    )


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _gaf_row(symbol: str, go_id: str) -> list[str]:
    return [
        "EcoCyc",
        f"ECOLI:{symbol}",
        symbol,
        "",
        go_id,
        "PMID:123",
        "IDA",
        "",
        "F",
        f"{symbol} annotation",
        "",
        "protein",
        "taxon:511145",
        "20260402",
        "EcoCyc",
        "",
        "",
    ]


def test_download_raw_sources_limits_downloads_to_raw_go_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    downloaded_urls: list[str] = []

    def fake_download(url: str, target: Path) -> None:
        downloaded_urls.append(url)
        target.write_text("downloaded\n", encoding="utf-8")

    monkeypatch.setattr(ecocyc_go, "_download_with_urllib", fake_download)

    manifest = download_raw_sources(tmp_path)

    source_ids = [source["source_id"] for source in manifest["sources"]]
    assert source_ids == [
        "gene_ontology_2026_03_25_ecocyc_gaf",
        "gene_ontology_2026_03_25_go_basic_obo",
    ]
    assert len(downloaded_urls) == 2
    assert not (
        tmp_path / "generated/functional_annotations/biocyc/29.6/smarttables/"
        "regulator_go_terms/processed/regulator_go_terms.tsv"
    ).exists()


def test_build_ecocyc_go_artifacts_joins_regulators_to_go_terms(
    tmp_path: Path,
) -> None:
    _write_gaf(
        tmp_path
        / f"generated/functional_annotations/gene_ontology/{GO_RELEASE}/annotations/ecocyc.gaf.gz",
        [
            _gaf_row("cpxR", "GO:0003700"),
            _gaf_row("cpxR", "GO:0006355"),
            _gaf_row("nonTF", "GO:0006355"),
        ],
    )
    _write_obo(
        tmp_path
        / f"generated/functional_annotations/gene_ontology/{GO_RELEASE}/ontology/go-basic.obo"
    )
    _write_network_regulator_gene(
        tmp_path
        / "sources/databases/regulondb/13.0/network_interactions/NetworkRegulatorGene.tsv"
    )

    manifest = build_ecocyc_go_artifacts(tmp_path)

    processed = (
        tmp_path
        / f"generated/functional_annotations/gene_ontology/{GO_RELEASE}/processed"
    )
    regulator_rows = _read_tsv(processed / "regulator_go_annotations.tsv")
    coverage_rows = _read_tsv(processed / "regulator_go_coverage.tsv")
    annotation_rows = _read_tsv(processed / "ecocyc_go_gene_product_annotations.tsv")

    assert manifest["row_counts"]["go_terms"] == 2
    assert manifest["row_counts"]["ecocyc_go_annotations"] == 3
    assert manifest["row_counts"]["regulator_identities"] == 3
    assert manifest["row_counts"]["regulator_go_annotations"] == 4
    assert len(annotation_rows) == 3
    assert {row["go_namespace"] for row in regulator_rows} == {
        "biological_process",
        "molecular_function",
    }
    assert {row["regulator_name"] for row in regulator_rows} == {"Composite", "CpxR"}
    assert {row["mapping_status"] for row in coverage_rows} == {
        "matched",
        "missing_regulator_gene",
    }


def test_build_ecocyc_go_artifacts_fails_on_malformed_gaf_rows(
    tmp_path: Path,
) -> None:
    _write_gaf(
        tmp_path
        / f"generated/functional_annotations/gene_ontology/{GO_RELEASE}/annotations/ecocyc.gaf.gz",
        [["EcoCyc", "too", "short"]],
    )
    _write_obo(
        tmp_path
        / f"generated/functional_annotations/gene_ontology/{GO_RELEASE}/ontology/go-basic.obo"
    )
    _write_network_regulator_gene(
        tmp_path
        / "sources/databases/regulondb/13.0/network_interactions/NetworkRegulatorGene.tsv"
    )

    with pytest.raises(ValueError, match="Expected 17 GAF columns"):
        build_ecocyc_go_artifacts(tmp_path)


def test_build_ecocyc_go_artifacts_fails_on_missing_go_terms(
    tmp_path: Path,
) -> None:
    _write_gaf(
        tmp_path
        / f"generated/functional_annotations/gene_ontology/{GO_RELEASE}/annotations/ecocyc.gaf.gz",
        [_gaf_row("cpxR", "GO:9999999")],
    )
    _write_obo(
        tmp_path
        / f"generated/functional_annotations/gene_ontology/{GO_RELEASE}/ontology/go-basic.obo"
    )
    _write_network_regulator_gene(
        tmp_path
        / "sources/databases/regulondb/13.0/network_interactions/NetworkRegulatorGene.tsv"
    )

    with pytest.raises(ValueError, match="GO IDs absent from ontology"):
        build_ecocyc_go_artifacts(tmp_path)


def test_build_ecocyc_go_artifacts_fails_when_no_regulator_annotations_match(
    tmp_path: Path,
) -> None:
    _write_gaf(
        tmp_path
        / f"generated/functional_annotations/gene_ontology/{GO_RELEASE}/annotations/ecocyc.gaf.gz",
        [_gaf_row("unrelated", "GO:0003700")],
    )
    _write_obo(
        tmp_path
        / f"generated/functional_annotations/gene_ontology/{GO_RELEASE}/ontology/go-basic.obo"
    )
    _write_network_regulator_gene(
        tmp_path
        / "sources/databases/regulondb/13.0/network_interactions/NetworkRegulatorGene.tsv"
    )

    with pytest.raises(ValueError, match="No regulator GO annotations matched"):
        build_ecocyc_go_artifacts(tmp_path)
