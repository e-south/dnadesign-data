from __future__ import annotations

from pathlib import Path

from dnadesign_data.catalog.functional_annotations import (
    BIOCYC_SMARTTABLE_KB_VERSION,
    GO_RELEASE,
    FunctionalAnnotationServiceSource,
    FunctionalAnnotationSourceFile,
    RegulatorIdentitySourceFile,
    iter_functional_annotation_source_files,
    iter_regulator_identity_source_files,
    known_functional_annotation_service_sources,
)


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("fixture\n", encoding="utf-8")


def test_iter_functional_annotation_source_files_reports_existing_go_sources(
    tmp_path: Path,
) -> None:
    _touch(
        tmp_path
        / f"generated/functional_annotations/gene_ontology/{GO_RELEASE}/annotations/ecocyc.gaf.gz"
    )
    _touch(
        tmp_path
        / f"generated/functional_annotations/gene_ontology/{GO_RELEASE}/ontology/go-basic.obo"
    )
    _touch(
        tmp_path
        / (
            "generated/functional_annotations/biocyc/"
            f"{BIOCYC_SMARTTABLE_KB_VERSION}/smarttables/regulator_go_terms/"
            "processed/regulator_go_terms.tsv"
        )
    )
    _touch(
        tmp_path
        / (
            "generated/functional_annotations/biocyc/"
            f"{BIOCYC_SMARTTABLE_KB_VERSION}/smarttables/regulator_go_terms/"
            "processed/regulator_go_coverage.tsv"
        )
    )

    sources = tuple(iter_functional_annotation_source_files(tmp_path))
    by_id = {source.source_id: source for source in sources}

    assert set(by_id) == {
        "biocyc_29_6_smarttable_regulator_go_coverage",
        "biocyc_29_6_smarttable_regulator_go_terms",
        "gene_ontology_2026_03_25_ecocyc_gaf",
        "gene_ontology_2026_03_25_go_basic_obo",
    }
    assert by_id["gene_ontology_2026_03_25_ecocyc_gaf"].role == (
        "ecocyc_gene_product_go_annotation"
    )
    assert by_id["gene_ontology_2026_03_25_go_basic_obo"].role == "go_term_ontology"
    assert by_id["gene_ontology_2026_03_25_ecocyc_gaf"].parser_hint == "go_gaf_2_2"
    assert by_id["biocyc_29_6_smarttable_regulator_go_terms"].role == (
        "regulator_go_terms_primary"
    )
    assert by_id["biocyc_29_6_smarttable_regulator_go_coverage"].role == (
        "regulator_go_coverage"
    )


def test_iter_regulator_identity_source_files_prefers_current_regulondb_source(
    tmp_path: Path,
) -> None:
    _touch(
        tmp_path
        / "sources/databases/regulondb/13.0/network_interactions/NetworkRegulatorGene.tsv"
    )
    _touch(
        tmp_path / "sources/databases/regulondb/11.0/transcription_factors/TFSet.txt"
    )

    sources = tuple(iter_regulator_identity_source_files(tmp_path))

    assert [source.source_id for source in sources] == [
        "regulondb_13_network_regulator_gene"
    ]
    assert sources[0].role == "regulator_gene_identity_overlay"
    assert sources[0].parser_hint == "regulondb_network_regulator_gene"


def test_iter_regulator_identity_source_files_uses_tfset_as_fallback(
    tmp_path: Path,
) -> None:
    _touch(
        tmp_path / "sources/databases/regulondb/11.0/transcription_factors/TFSet.txt"
    )

    sources = tuple(iter_regulator_identity_source_files(tmp_path))

    assert [source.source_id for source in sources] == ["regulondb_11_tf_set"]
    assert sources[0].parser_hint == "regulondb_tf_set"


def test_functional_annotation_source_descriptor_round_trips() -> None:
    source = FunctionalAnnotationSourceFile(
        source_id="fixture_gaf",
        source="gene_ontology",
        release="current",
        path="generated/functional_annotations/gene_ontology/current/annotations/ecocyc.gaf.gz",
        table="ecocyc.gaf.gz",
        stratum="current_source_release",
        role="ecocyc_gene_product_go_annotation",
        file_format="gaf_gzip",
        parser_hint="go_gaf_2_2",
        url="https://current.geneontology.org/annotations/ecocyc.gaf.gz",
    )

    assert source.as_dict()["url"] == (
        "https://current.geneontology.org/annotations/ecocyc.gaf.gz"
    )


def test_functional_annotation_service_source_descriptor_round_trips() -> None:
    source = FunctionalAnnotationServiceSource(
        source_id="fixture_service",
        source="biocyc",
        release="runtime_reported_kb_version",
        base_url="https://websvc.biocyc.org",
        stratum="authenticated_live_web_service",
        role="gene_product_go_annotation_smarttable",
        response_format="tsv",
        parser_hint="biocyc_smarttable_go_terms",
        auth_required=True,
    )

    assert source.as_dict()["auth_required"] is True


def test_known_functional_annotation_service_sources_include_biocyc_smarttables() -> (
    None
):
    sources = tuple(known_functional_annotation_service_sources())

    assert [source.source_id for source in sources] == ["biocyc_smarttable_go_terms"]
    assert sources[0].auth_required is True
    assert sources[0].parser_hint == "biocyc_smarttable_go_terms"


def test_regulator_identity_source_descriptor_round_trips() -> None:
    source = RegulatorIdentitySourceFile(
        source_id="fixture_regulators",
        source="regulondb",
        release="13.0",
        path="sources/databases/regulondb/13.0/network_interactions/NetworkRegulatorGene.tsv",
        table="NetworkRegulatorGene.tsv",
        stratum="current_curated_regulator_gene_identity",
        role="regulator_gene_identity_overlay",
        file_format="tsv",
        parser_hint="regulondb_network_regulator_gene",
    )

    assert source.as_dict()["parser_hint"] == "regulondb_network_regulator_gene"
