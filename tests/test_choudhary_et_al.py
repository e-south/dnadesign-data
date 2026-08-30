from __future__ import annotations

import argparse
import tempfile
import unittest
import warnings
from pathlib import Path

from dnadesign_data.literature import choudhary_et_al as hydrate


class TestHydrateChipExoPeaks(unittest.TestCase):
    def test_reverse_complement(self):
        self.assertEqual(hydrate.reverse_complement("ACGTN"), "NACGT")

    def test_slice_sequence_end_exclusive(self):
        genome = "ACGTACGT"
        self.assertEqual(hydrate.slice_sequence(genome, 1, 3, "+"), "CG")

    def test_slice_sequence_minus_strand(self):
        genome = "AACGTT"
        self.assertEqual(hydrate.slice_sequence(genome, 1, 4, "-"), "CGT")

    def test_apply_buffer(self):
        start, end, clipped = hydrate.apply_buffer(2, 4, 2, genome_length=8)
        self.assertEqual((start, end, clipped), (0, 6, False))

    def test_dedupe_peak_id(self):
        rows = [
            {"peak_id": "peak_1", "start": 10, "end": 20, "strand": "+"},
            {"peak_id": "peak_1", "start": 10, "end": 20, "strand": "+"},
            {"peak_id": "peak_2", "start": 30, "end": 40, "strand": "-"},
        ]
        deduped = hydrate.dedupe_rows(rows, mode="peak_id")
        self.assertEqual(len(deduped), 2)

    def test_write_provenance_no_deprecation_warning(self):
        args = argparse.Namespace(genome_accession="NC_000913.3", dedupe="none")
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            xlsx_path = tmp_path / "input.xlsx"
            fasta_path = tmp_path / "genome.fasta"
            provenance_path = tmp_path / "provenance.json"
            xlsx_path.write_bytes(b"test")
            fasta_path.write_text(">NC_000913.3\nACGT\n")
            with warnings.catch_warnings():
                warnings.filterwarnings("error", category=DeprecationWarning)
                hydrate.write_provenance(
                    provenance_path,
                    args,
                    xlsx_path,
                    fasta_path,
                    total_rows=1,
                    output_rows=[{"peak_id": "peak_1"}],
                )

    def test_write_tsv_uses_lf(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            output_path = tmp_path / "output.tsv"
            rows = [{"a": "1", "b": "2"}]
            hydrate.write_tsv(output_path, rows, fieldnames=["a", "b"])
            content = output_path.read_bytes()
            self.assertNotIn(b"\r\n", content)


if __name__ == "__main__":
    unittest.main()
