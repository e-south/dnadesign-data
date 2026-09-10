"""Source metadata is distinct from model qualification and biological replication."""

import csv
from pathlib import Path


def test_named_plant_count_sources_have_distinct_assay_and_validation_provenance():
    root = Path("sources/databases/jaspar/2026/CORE-counts")
    with (root / "records.tsv").open(newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    names = {
        "ARF1",
        "FUS3",
        "AGL16",
        "AGL27",
        "DREB2A",
        "ERF4",
        "MYB46",
        "MYB83",
        "NAC019",
        "NAC055",
        "WRKY33",
        "WRKY70",
    }
    selected = [r for r in rows if r["motif_id"] in names]
    assert len(selected) == 12
    assert "mean_sequence_count" not in rows[0]
    assert all(float(r["mean_column_total"]) > 0 for r in rows)
    assert {r["source_type"] for r in selected} == {"PBM", "DAP-seq", "ChIP-seq"}
    assert {r["tax_id"] for r in selected} == {"3702"}
    for row in selected:
        assert row["matrix_source_pmid"].isdecimal()
        assert row["validation_pmids"]
        assert row["uniprot_accession"]
        assert row["source_record"].startswith("MA")
        assert row["retrieved_on"] == "2026-09-09"
    arf = next(r for r in selected if r["motif_id"] == "ARF1")
    assert arf["matrix_source_pmid"] == "24485461"
    assert arf["validation_pmids"] == "9188533"
