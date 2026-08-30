from __future__ import annotations

import pytest

from dnadesign_data.core.layout import (
    biocyc_kb_path,
    ecocyc_release_path,
    gene_ontology_release_path,
    literature_path,
    regulondb_release_path,
)


def test_layout_helpers_emit_semantic_posix_paths() -> None:
    assert (
        regulondb_release_path("13.0", "promoters", "PromoterSet.tsv")
        == "sources/databases/regulondb/13.0/promoters/PromoterSet.tsv"
    )
    assert (
        ecocyc_release_path("28.0", "SmartTable_All_Promoters.txt")
        == "sources/databases/ecocyc/28.0/SmartTable_All_Promoters.txt"
    )
    assert (
        literature_path("Choudhary_et_al", "processed", "BaeR_binding_sites.tsv")
        == "sources/literature/Choudhary_et_al/processed/BaeR_binding_sites.tsv"
    )
    assert (
        gene_ontology_release_path("2026-03-25", "processed", "manifest.json")
        == "generated/functional_annotations/gene_ontology/2026-03-25/processed/manifest.json"
    )
    assert (
        biocyc_kb_path("29.6", "smarttables", "regulator_go_terms")
        == "generated/functional_annotations/biocyc/29.6/smarttables/regulator_go_terms"
    )


def test_layout_helpers_reject_nested_release_segments() -> None:
    with pytest.raises(ValueError, match="release"):
        regulondb_release_path("13/0", "promoters")

    with pytest.raises(ValueError, match="citation_slug"):
        literature_path("Choudhary/et_al")
