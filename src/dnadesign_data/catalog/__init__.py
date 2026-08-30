"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/catalog/__init__.py

Exposes public source-catalog descriptors for downstream data consumers.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from dnadesign_data.catalog.functional_annotations import (
    BIOCYC_SMARTTABLE_KB_VERSION,
    GO_BASIC_OBO_URL,
    GO_ECOCYC_GAF_URL,
    GO_RELEASE,
    FunctionalAnnotationServiceSource,
    FunctionalAnnotationSourceFile,
    RegulatorIdentitySourceFile,
    iter_functional_annotation_source_files,
    iter_regulator_identity_source_files,
    known_functional_annotation_service_sources,
    known_functional_annotation_source_files,
    known_regulator_identity_source_files,
)
from dnadesign_data.catalog.regulatory_parts import (
    MotifSourceFile,
    PromoterAssociationSourceFile,
    PromoterSourceFile,
    iter_promoter_association_source_files,
    iter_promoter_source_files,
    known_motif_source_files,
    known_promoter_association_source_files,
    known_promoter_source_files,
)
from dnadesign_data.catalog.sources import (
    SCHEMA_VERSION,
    SOURCE_KIND_CHOICES,
    SourceCatalogError,
    build_source_catalog_payload,
    check_source_catalog_payload,
    iter_source_records,
    resolve_source_record,
    source_catalog_schema_payload,
)

__all__ = [
    "BIOCYC_SMARTTABLE_KB_VERSION",
    "GO_BASIC_OBO_URL",
    "GO_ECOCYC_GAF_URL",
    "GO_RELEASE",
    "SCHEMA_VERSION",
    "SOURCE_KIND_CHOICES",
    "FunctionalAnnotationServiceSource",
    "FunctionalAnnotationSourceFile",
    "MotifSourceFile",
    "PromoterAssociationSourceFile",
    "PromoterSourceFile",
    "RegulatorIdentitySourceFile",
    "SourceCatalogError",
    "build_source_catalog_payload",
    "check_source_catalog_payload",
    "iter_functional_annotation_source_files",
    "iter_promoter_association_source_files",
    "iter_promoter_source_files",
    "iter_regulator_identity_source_files",
    "iter_source_records",
    "known_functional_annotation_service_sources",
    "known_functional_annotation_source_files",
    "known_motif_source_files",
    "known_promoter_association_source_files",
    "known_promoter_source_files",
    "known_regulator_identity_source_files",
    "resolve_source_record",
    "source_catalog_schema_payload",
]
