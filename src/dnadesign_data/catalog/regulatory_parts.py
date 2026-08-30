"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/catalog/regulatory_parts.py

Describes promoter and regulatory-association source files.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from dnadesign_data.core.layout import (
    default_data_root,
    ecocyc_release_path,
    regulondb_release_path,
)

PathLike = str | Path


@dataclass(frozen=True)
class PromoterSourceFile:
    source_id: str
    source: str
    release: str
    path: str
    table: str
    stratum: str
    role: str
    file_format: str
    parser_hint: str
    creates_base_rows: bool

    def absolute_path(self, root: PathLike | None = None) -> Path:
        base = default_data_root() if root is None else Path(root)
        return base / self.path

    def as_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "source": self.source,
            "release": self.release,
            "path": self.path,
            "table": self.table,
            "stratum": self.stratum,
            "role": self.role,
            "file_format": self.file_format,
            "parser_hint": self.parser_hint,
            "creates_base_rows": self.creates_base_rows,
        }


@dataclass(frozen=True)
class PromoterAssociationSourceFile:
    source_id: str
    source: str
    release: str
    path: str
    table: str
    stratum: str
    role: str
    file_format: str
    parser_hint: str

    def absolute_path(self, root: PathLike | None = None) -> Path:
        base = default_data_root() if root is None else Path(root)
        return base / self.path

    def as_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "source": self.source,
            "release": self.release,
            "path": self.path,
            "table": self.table,
            "stratum": self.stratum,
            "role": self.role,
            "file_format": self.file_format,
            "parser_hint": self.parser_hint,
        }


@dataclass(frozen=True)
class MotifSourceFile:
    source_id: str
    source: str
    release: str
    path: str
    table: str
    stratum: str
    role: str
    file_format: str
    parser_hint: str
    source_kind: str
    output_capability: str
    redistribution_status: str
    retrieval_url: str
    rights_url: str
    retrieved_on: str | None

    def absolute_path(self, root: PathLike | None = None) -> Path:
        base = default_data_root() if root is None else Path(root)
        return base / self.path

    def as_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "source": self.source,
            "release": self.release,
            "path": self.path,
            "table": self.table,
            "stratum": self.stratum,
            "role": self.role,
            "file_format": self.file_format,
            "parser_hint": self.parser_hint,
            "source_kind": self.source_kind,
            "output_capability": self.output_capability,
            "redistribution_status": self.redistribution_status,
            "retrieval_url": self.retrieval_url,
            "rights_url": self.rights_url,
            "retrieved_on": self.retrieved_on,
        }


_PROMOTER_SOURCES: tuple[PromoterSourceFile, ...] = (
    PromoterSourceFile(
        source_id="regulondb_13_promoter_set",
        source="regulondb",
        release="13.0",
        path=regulondb_release_path("13.0", "promoters", "PromoterSet.tsv"),
        table="PromoterSet.tsv",
        stratum="local_release_pinned_curated",
        role="curated_base",
        file_format="tsv",
        parser_hint="regulondb_promoter_set",
        creates_base_rows=True,
    ),
    PromoterSourceFile(
        source_id="regulondb_13_sigmulon",
        source="regulondb",
        release="13.0",
        path=regulondb_release_path("13.0", "promoters"),
        table="*_SigmulonPromoters.csv",
        stratum="local_release_pinned_sigma_supplement",
        role="sigma_affiliation_overlay",
        file_format="csv_glob",
        parser_hint="regulondb_sigmulon_promoters",
        creates_base_rows=False,
    ),
    PromoterSourceFile(
        source_id="regulondb_11_promoter_set",
        source="regulondb",
        release="11.0",
        path=regulondb_release_path("11.0", "promoters", "PromoterSet.csv"),
        table="PromoterSet.csv",
        stratum="historical_curated_release",
        role="historical_curated_comparison",
        file_format="csv",
        parser_hint="regulondb_promoter_set",
        creates_base_rows=True,
    ),
    PromoterSourceFile(
        source_id="regulondb_11_race_promoters",
        source="regulondb",
        release="11.0",
        path=regulondb_release_path(
            "11.0", "promoters", "Promoter_from_RACE_Dataset.csv"
        ),
        table="Promoter_from_RACE_Dataset.csv",
        stratum="historical_ht_tss_evidence",
        role="experimental_tss_evidence",
        file_format="csv",
        parser_hint="regulondb_ht_promoter_tss",
        creates_base_rows=False,
    ),
    PromoterSourceFile(
        source_id="regulondb_11_454_promoters",
        source="regulondb",
        release="11.0",
        path=regulondb_release_path(
            "11.0", "promoters", "Promoter_from_454_Dataset.csv"
        ),
        table="Promoter_from_454_Dataset.csv",
        stratum="historical_ht_tss_evidence",
        role="experimental_tss_evidence",
        file_format="csv",
        parser_hint="regulondb_ht_promoter_tss",
        creates_base_rows=False,
    ),
    PromoterSourceFile(
        source_id="regulondb_11_prediction_set",
        source="regulondb",
        release="11.0",
        path=regulondb_release_path("11.0", "promoters", "PromoterPredictionSet.csv"),
        table="PromoterPredictionSet.csv",
        stratum="historical_computational_prediction",
        role="prediction_overlay",
        file_format="csv",
        parser_hint="regulondb_promoter_prediction_set",
        creates_base_rows=False,
    ),
    PromoterSourceFile(
        source_id="ecocyc_28_promoters",
        source="ecocyc",
        release="28.0",
        path=ecocyc_release_path("28.0", "SmartTable_All_Promoters.txt"),
        table="SmartTable_All_Promoters.txt",
        stratum="independent_curated_cross_check",
        role="curated_window_cross_check",
        file_format="tsv",
        parser_hint="ecocyc_promoter_smarttable",
        creates_base_rows=False,
    ),
)


_PROMOTER_ASSOCIATION_SOURCES: tuple[PromoterAssociationSourceFile, ...] = (
    PromoterAssociationSourceFile(
        source_id="regulondb_13_tf_riset",
        source="regulondb",
        release="13.0",
        path=regulondb_release_path("13.0", "binding_sites", "TF-RISet.tsv"),
        table="TF-RISet.tsv",
        stratum="current_curated_regulatory_interaction",
        role="tf_promoter_association_overlay",
        file_format="tsv",
        parser_hint="regulondb_tf_riset",
    ),
    PromoterAssociationSourceFile(
        source_id="regulondb_11_network_tf_tu",
        source="regulondb",
        release="11.0",
        path=regulondb_release_path(
            "11.0", "network_associations", "network_tf_tu.txt"
        ),
        table="network_tf_tu.txt",
        stratum="historical_curated_network_association",
        role="tf_promoter_association_overlay",
        file_format="tsv",
        parser_hint="regulondb_network_tf_tu",
    ),
)


_MOTIF_SOURCES: tuple[MotifSourceFile, ...] = (
    MotifSourceFile(
        source_id="jaspar_2026_core_counts",
        source="jaspar",
        release="2026",
        path="sources/databases/jaspar/2026/CORE-counts",
        table="*.jaspar",
        stratum="release_pinned_core_count_matrices",
        role="motif_model_source",
        file_format="jaspar_count_glob",
        parser_hint="jaspar_count_matrix_v1",
        source_kind="count_matrix_collection",
        output_capability="motif-model/v2",
        redistribution_status="redistributable",
        retrieval_url="https://jaspar.elixir.no/api/v1/matrix/",
        rights_url="https://jaspar.elixir.no/about/",
        retrieved_on="2026-08-29",
    ),
    MotifSourceFile(
        source_id="omalley_2021_ecoli_meme",
        source="omalley_et_al",
        release="s41592-021-01312-2-supplementary-data-2",
        path="sources/literature/OMalley_et_al/escherichia_coli_motifs",
        table="*.txt",
        stratum="publication_supplement_probability_matrices",
        role="motif_model_source",
        file_format="meme_report_glob",
        parser_hint="meme_probability_matrix_v1",
        source_kind="probability_matrix_collection",
        output_capability="motif-model/v2",
        redistribution_status="review_blocked",
        retrieval_url="https://www.nature.com/articles/s41592-021-01312-2",
        rights_url="https://www.nature.com/articles/s41592-021-01312-2",
        retrieved_on=None,
    ),
    MotifSourceFile(
        source_id="jaspar_2026_core_meme",
        source="jaspar",
        release="2026",
        path="sources/databases/jaspar/2026/CORE",
        table="*.meme",
        stratum="release_pinned_core_probability_matrices",
        role="motif_model_source",
        file_format="meme_report_glob",
        parser_hint="meme_probability_matrix_v1",
        source_kind="probability_matrix_collection",
        output_capability="motif-model/v2",
        redistribution_status="redistributable",
        retrieval_url="https://jaspar.elixir.no/api/v1/matrix/",
        rights_url="https://jaspar.elixir.no/about/",
        retrieved_on="2026-08-27",
    ),
    MotifSourceFile(
        source_id="hocomoco_14_core_meme",
        source="hocomoco",
        release="14",
        path="sources/databases/hocomoco/14/CORE",
        table="*.meme",
        stratum="release_pinned_core_probability_matrices",
        role="motif_model_source",
        file_format="meme_report_glob",
        parser_hint="meme_probability_matrix_v1",
        source_kind="probability_matrix_collection",
        output_capability="motif-model/v2",
        redistribution_status="redistributable",
        retrieval_url="https://hocomoco14.autosome.org/downloads_v14",
        rights_url="https://hocomoco14.autosome.org/downloads_v14",
        retrieved_on="2026-08-28",
    ),
    MotifSourceFile(
        source_id="regulondb_13_tf_riset_sites",
        source="regulondb",
        release="13.0",
        path=regulondb_release_path("13.0", "binding_sites", "TF-RISet.tsv"),
        table="TF-RISet.tsv",
        stratum="current_curated_binding_site_evidence",
        role="binding_site_source",
        file_format="tsv",
        parser_hint="regulondb_tf_riset_sites_v1",
        source_kind="binding_site_table",
        output_capability="dnadesign-data.binding-site-set/v1",
        redistribution_status="private_storage",
        retrieval_url="https://regulondb.ccg.unam.mx/menu/download/datasets/index.jsp",
        rights_url="https://testregulondb.ccg.unam.mx/menu/download/full_version/terms_and_conditions.jsp",
        retrieved_on=None,
    ),
)


def known_promoter_source_files() -> tuple[PromoterSourceFile, ...]:
    return _PROMOTER_SOURCES


def known_promoter_association_source_files() -> tuple[
    PromoterAssociationSourceFile, ...
]:
    return _PROMOTER_ASSOCIATION_SOURCES


def known_motif_source_files() -> tuple[MotifSourceFile, ...]:
    return _MOTIF_SOURCES


def iter_promoter_source_files(
    root: PathLike | None = None,
) -> Iterable[PromoterSourceFile]:
    base = default_data_root() if root is None else Path(root)
    for source in _PROMOTER_SOURCES:
        candidate = source.absolute_path(base)
        if source.file_format == "csv_glob":
            if candidate.exists() and any(candidate.glob(source.table)):
                yield source
            continue
        if candidate.exists():
            yield source


def iter_promoter_association_source_files(
    root: PathLike | None = None,
) -> Iterable[PromoterAssociationSourceFile]:
    base = default_data_root() if root is None else Path(root)
    existing = tuple(
        source
        for source in _PROMOTER_ASSOCIATION_SOURCES
        if source.absolute_path(base).exists()
    )
    current_direct = tuple(
        source for source in existing if source.source_id == "regulondb_13_tf_riset"
    )
    yield from current_direct or existing
