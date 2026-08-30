"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/catalog/functional_annotations.py

Describes functional-annotation sources and service descriptors.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from dnadesign_data.core.layout import (
    biocyc_kb_path,
    default_data_root,
    gene_ontology_release_path,
    regulondb_release_path,
)

PathLike = str | Path


GO_RELEASE = "2026-03-25"
GO_ECOCYC_GAF_URL = (
    f"https://release.geneontology.org/{GO_RELEASE}/annotations/ecocyc.gaf.gz"
)
GO_BASIC_OBO_URL = (
    f"https://release.geneontology.org/{GO_RELEASE}/ontology/go-basic.obo"
)
BIOCYC_SMARTTABLE_KB_VERSION = "29.6"


@dataclass(frozen=True)
class FunctionalAnnotationSourceFile:
    source_id: str
    source: str
    release: str
    path: str
    table: str
    stratum: str
    role: str
    file_format: str
    parser_hint: str
    url: str

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
            "url": self.url,
        }


@dataclass(frozen=True)
class RegulatorIdentitySourceFile:
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
class FunctionalAnnotationServiceSource:
    source_id: str
    source: str
    release: str
    base_url: str
    stratum: str
    role: str
    response_format: str
    parser_hint: str
    auth_required: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "source": self.source,
            "release": self.release,
            "base_url": self.base_url,
            "stratum": self.stratum,
            "role": self.role,
            "response_format": self.response_format,
            "parser_hint": self.parser_hint,
            "auth_required": self.auth_required,
        }


_FUNCTIONAL_ANNOTATION_SOURCES: tuple[FunctionalAnnotationSourceFile, ...] = (
    FunctionalAnnotationSourceFile(
        source_id="gene_ontology_2026_03_25_ecocyc_gaf",
        source="gene_ontology",
        release=GO_RELEASE,
        path=gene_ontology_release_path(GO_RELEASE, "annotations", "ecocyc.gaf.gz"),
        table="ecocyc.gaf.gz",
        stratum="release_pinned_go_bulk_annotation",
        role="ecocyc_gene_product_go_annotation",
        file_format="gaf_gzip",
        parser_hint="go_gaf_2_2",
        url=GO_ECOCYC_GAF_URL,
    ),
    FunctionalAnnotationSourceFile(
        source_id="gene_ontology_2026_03_25_go_basic_obo",
        source="gene_ontology",
        release=GO_RELEASE,
        path=gene_ontology_release_path(GO_RELEASE, "ontology", "go-basic.obo"),
        table="go-basic.obo",
        stratum="release_pinned_go_bulk_ontology",
        role="go_term_ontology",
        file_format="obo",
        parser_hint="go_basic_obo",
        url=GO_BASIC_OBO_URL,
    ),
    FunctionalAnnotationSourceFile(
        source_id="biocyc_29_6_smarttable_regulator_go_terms",
        source="biocyc",
        release=BIOCYC_SMARTTABLE_KB_VERSION,
        path=biocyc_kb_path(
            BIOCYC_SMARTTABLE_KB_VERSION,
            "smarttables",
            "regulator_go_terms",
            "processed",
            "regulator_go_terms.tsv",
        ),
        table="regulator_go_terms.tsv",
        stratum="authenticated_biocyc_smarttable_current_kb",
        role="regulator_go_terms_primary",
        file_format="tsv",
        parser_hint="biocyc_smarttable_regulator_go_terms",
        url="https://websvc.biocyc.org/st-get",
    ),
    FunctionalAnnotationSourceFile(
        source_id="biocyc_29_6_smarttable_regulator_go_coverage",
        source="biocyc",
        release=BIOCYC_SMARTTABLE_KB_VERSION,
        path=biocyc_kb_path(
            BIOCYC_SMARTTABLE_KB_VERSION,
            "smarttables",
            "regulator_go_terms",
            "processed",
            "regulator_go_coverage.tsv",
        ),
        table="regulator_go_coverage.tsv",
        stratum="authenticated_biocyc_smarttable_current_kb",
        role="regulator_go_coverage",
        file_format="tsv",
        parser_hint="biocyc_smarttable_regulator_go_coverage",
        url="https://websvc.biocyc.org/st-get",
    ),
)


_REGULATOR_IDENTITY_SOURCES: tuple[RegulatorIdentitySourceFile, ...] = (
    RegulatorIdentitySourceFile(
        source_id="regulondb_13_network_regulator_gene",
        source="regulondb",
        release="13.0",
        path=regulondb_release_path(
            "13.0", "network_interactions", "NetworkRegulatorGene.tsv"
        ),
        table="NetworkRegulatorGene.tsv",
        stratum="current_curated_regulator_gene_identity",
        role="regulator_gene_identity_overlay",
        file_format="tsv",
        parser_hint="regulondb_network_regulator_gene",
    ),
    RegulatorIdentitySourceFile(
        source_id="regulondb_11_tf_set",
        source="regulondb",
        release="11.0",
        path=regulondb_release_path("11.0", "transcription_factors", "TFSet.txt"),
        table="TFSet.txt",
        stratum="historical_curated_tf_catalog",
        role="regulator_gene_identity_catalog",
        file_format="tsv",
        parser_hint="regulondb_tf_set",
    ),
)


_FUNCTIONAL_ANNOTATION_SERVICE_SOURCES: tuple[
    FunctionalAnnotationServiceSource, ...
] = (
    FunctionalAnnotationServiceSource(
        source_id="biocyc_smarttable_go_terms",
        source="biocyc",
        release="runtime_reported_kb_version",
        base_url="https://websvc.biocyc.org",
        stratum="authenticated_live_web_service",
        role="gene_product_go_annotation_smarttable",
        response_format="tsv",
        parser_hint="biocyc_smarttable_go_terms",
        auth_required=True,
    ),
)


def known_functional_annotation_source_files() -> tuple[
    FunctionalAnnotationSourceFile, ...
]:
    return _FUNCTIONAL_ANNOTATION_SOURCES


def known_regulator_identity_source_files() -> tuple[RegulatorIdentitySourceFile, ...]:
    return _REGULATOR_IDENTITY_SOURCES


def known_functional_annotation_service_sources() -> tuple[
    FunctionalAnnotationServiceSource, ...
]:
    return _FUNCTIONAL_ANNOTATION_SERVICE_SOURCES


def iter_functional_annotation_source_files(
    root: PathLike | None = None,
) -> Iterable[FunctionalAnnotationSourceFile]:
    base = default_data_root() if root is None else Path(root)
    for source in _FUNCTIONAL_ANNOTATION_SOURCES:
        if source.absolute_path(base).exists():
            yield source


def iter_regulator_identity_source_files(
    root: PathLike | None = None,
) -> Iterable[RegulatorIdentitySourceFile]:
    base = default_data_root() if root is None else Path(root)
    existing = tuple(
        source
        for source in _REGULATOR_IDENTITY_SOURCES
        if source.absolute_path(base).exists()
    )
    current = tuple(
        source
        for source in existing
        if source.source_id == "regulondb_13_network_regulator_gene"
    )
    yield from current or existing
