from __future__ import annotations

from pathlib import Path

from dnadesign_data.catalog.regulatory_parts import (
    MotifSourceFile,
    PromoterAssociationSourceFile,
    PromoterSourceFile,
    iter_promoter_association_source_files,
    iter_promoter_source_files,
    known_motif_source_files,
)


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("fixture\n", encoding="utf-8")


def test_iter_promoter_source_files_reports_existing_promoter_sources(
    tmp_path: Path,
) -> None:
    _touch(tmp_path / "sources/databases/regulondb/13.0/promoters/PromoterSet.tsv")
    _touch(
        tmp_path
        / "sources/databases/regulondb/13.0/promoters/RpoD_RDBECOLISFC00003_SigmulonPromoters.csv"
    )
    _touch(
        tmp_path
        / "sources/databases/regulondb/11.0/promoters/PromoterPredictionSet.csv"
    )
    _touch(tmp_path / "sources/databases/ecocyc/28.0/SmartTable_All_Promoters.txt")

    sources = tuple(iter_promoter_source_files(tmp_path))
    by_id = {source.source_id: source for source in sources}

    assert set(by_id) == {
        "regulondb_13_promoter_set",
        "regulondb_13_sigmulon",
        "regulondb_11_prediction_set",
        "ecocyc_28_promoters",
    }
    assert by_id["regulondb_13_promoter_set"].creates_base_rows is True
    assert by_id["regulondb_11_prediction_set"].creates_base_rows is False
    assert (
        by_id["regulondb_11_prediction_set"].stratum
        == "historical_computational_prediction"
    )


def test_promoter_source_file_resolves_relative_path(tmp_path: Path) -> None:
    source = PromoterSourceFile(
        source_id="fixture",
        source="regulondb",
        release="13.0",
        path="sources/databases/regulondb/13.0/promoters/PromoterSet.tsv",
        table="PromoterSet.tsv",
        stratum="local_release_pinned_curated",
        role="curated_base",
        file_format="tsv",
        parser_hint="regulondb_promoter_set",
        creates_base_rows=True,
    )

    assert (
        source.absolute_path(tmp_path)
        == tmp_path / "sources/databases/regulondb/13.0/promoters/PromoterSet.tsv"
    )


def test_iter_promoter_association_source_files_prefers_current_direct_tf_promoter_sources(
    tmp_path: Path,
) -> None:
    _touch(tmp_path / "sources/databases/regulondb/13.0/binding_sites/TF-RISet.tsv")
    _touch(
        tmp_path
        / "sources/databases/regulondb/11.0/network_associations/network_tf_tu.txt"
    )

    sources = tuple(iter_promoter_association_source_files(tmp_path))

    assert [source.source_id for source in sources] == ["regulondb_13_tf_riset"]
    source = sources[0]
    assert source.source == "regulondb"
    assert source.release == "13.0"
    assert source.parser_hint == "regulondb_tf_riset"
    assert source.role == "tf_promoter_association_overlay"


def test_iter_promoter_association_source_files_uses_historical_network_as_fallback(
    tmp_path: Path,
) -> None:
    _touch(
        tmp_path
        / "sources/databases/regulondb/11.0/network_associations/network_tf_tu.txt"
    )

    sources = tuple(iter_promoter_association_source_files(tmp_path))

    assert [source.source_id for source in sources] == ["regulondb_11_network_tf_tu"]
    assert sources[0].parser_hint == "regulondb_network_tf_tu"


def test_promoter_association_source_file_resolves_relative_path(
    tmp_path: Path,
) -> None:
    source = PromoterAssociationSourceFile(
        source_id="fixture",
        source="regulondb",
        release="11.0",
        path="sources/databases/regulondb/11.0/network_associations/network_tf_tu.txt",
        table="network_tf_tu.txt",
        stratum="historical_curated_network_association",
        role="tf_promoter_association_overlay",
        file_format="tsv",
        parser_hint="regulondb_network_tf_tu",
    )

    assert (
        source.absolute_path(tmp_path)
        == tmp_path
        / "sources/databases/regulondb/11.0/network_associations/network_tf_tu.txt"
    )


def test_motif_source_descriptors_distinguish_models_from_site_evidence() -> None:
    sources = {source.source_id: source for source in known_motif_source_files()}

    assert set(sources) == {
        "hocomoco_14_core_meme",
        "jaspar_2026_core_counts",
        "jaspar_2026_core_meme",
        "omalley_2021_ecoli_meme",
        "regulondb_13_tf_riset_sites",
    }

    omalley = sources["omalley_2021_ecoli_meme"]
    assert isinstance(omalley, MotifSourceFile)
    assert omalley.source_kind == "probability_matrix_collection"
    assert omalley.output_capability == "motif-model/v2"
    assert omalley.redistribution_status == "review_blocked"

    jaspar = sources["jaspar_2026_core_meme"]
    assert jaspar.source == "jaspar"
    assert jaspar.release == "2026"
    assert jaspar.table == "*.meme"
    assert jaspar.output_capability == "motif-model/v2"
    assert jaspar.redistribution_status == "redistributable"
    assert jaspar.retrieval_url == "https://jaspar.elixir.no/api/v1/matrix/"
    assert jaspar.rights_url == "https://jaspar.elixir.no/about/"

    jaspar_counts = sources["jaspar_2026_core_counts"]
    assert jaspar_counts.source == "jaspar"
    assert jaspar_counts.release == "2026"
    assert jaspar_counts.table == "*.jaspar"
    assert jaspar_counts.source_kind == "count_matrix_collection"
    assert jaspar_counts.parser_hint == "jaspar_count_matrix_v1"
    assert jaspar_counts.redistribution_status == "redistributable"

    hocomoco = sources["hocomoco_14_core_meme"]
    assert hocomoco.source == "hocomoco"
    assert hocomoco.release == "14"
    assert hocomoco.table == "*.meme"
    assert hocomoco.parser_hint == "meme_probability_matrix_v1"
    assert hocomoco.output_capability == "motif-model/v2"
    assert hocomoco.redistribution_status == "redistributable"
    assert hocomoco.retrieval_url == "https://hocomoco14.autosome.org/downloads_v14"
    assert hocomoco.rights_url == "https://hocomoco14.autosome.org/downloads_v14"

    regulondb = sources["regulondb_13_tf_riset_sites"]
    assert regulondb.source_kind == "binding_site_table"
    assert regulondb.output_capability == "dnadesign-data.binding-site-set/v1"
    assert regulondb.redistribution_status == "private_storage"


def test_motif_source_descriptors_make_retrieval_and_rights_routes_explicit() -> None:
    sources = known_motif_source_files()

    assert all(source.retrieval_url.startswith("https://") for source in sources)
    assert all(source.rights_url.startswith("https://") for source in sources)
