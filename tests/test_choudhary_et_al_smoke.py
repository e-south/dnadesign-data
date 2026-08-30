from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from dnadesign_data.literature import choudhary_et_al as hydrate


def test_baer_adapter_with_caller_supplied_inputs(tmp_path: Path) -> None:
    xlsx_path = tmp_path / "supplement.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "BaeR"
    sheet.append(["peak_start", "peak_end", "strand", "peak_ID"])
    sheet.append([1, 5, "+", "peak-1"])
    sheet.append([5, 9, "-", "peak-2"])
    workbook.save(xlsx_path)

    fasta_path = tmp_path / "genome.fasta"
    fasta_path.write_text(">NC_000913.3\nAACCGGTTAACC\n", encoding="utf-8")

    rows = hydrate.load_sheet_rows(xlsx_path, "BaeR")
    genome = hydrate.load_genome_sequence(fasta_path, "NC_000913.3")
    output_rows = hydrate.build_output_rows(
        rows, genome, "BaeR", "NC_000913.3", buffer=0
    )

    assert len(rows) == 2
    assert [row["sequence"] for row in output_rows] == ["ACCG", "TAAC"]
    for row in output_rows:
        assert row["length"] == row["end"] - row["start"]
