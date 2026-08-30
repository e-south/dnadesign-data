"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/core/__init__.py

Exposes core repository-layout primitives.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from dnadesign_data.core.layout import (
    DATABASE_SOURCES_ROOT,
    FUNCTIONAL_ANNOTATIONS_ROOT,
    GENERATED_ROOT,
    LITERATURE_SOURCES_ROOT,
    SOURCES_ROOT,
    biocyc_kb_path,
    database_release_path,
    default_data_root,
    ecocyc_release_path,
    gene_ontology_release_path,
    literature_path,
    posix_path,
    regulondb_release_path,
)

__all__ = [
    "DATABASE_SOURCES_ROOT",
    "FUNCTIONAL_ANNOTATIONS_ROOT",
    "GENERATED_ROOT",
    "LITERATURE_SOURCES_ROOT",
    "SOURCES_ROOT",
    "biocyc_kb_path",
    "database_release_path",
    "default_data_root",
    "ecocyc_release_path",
    "gene_ontology_release_path",
    "literature_path",
    "posix_path",
    "regulondb_release_path",
]
