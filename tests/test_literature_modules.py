from __future__ import annotations

import importlib.util

import pytest

from dnadesign_data.literature import bie_et_al, choudhary_et_al


def test_choudhary_defaults_resolve_to_literature_data_dir() -> None:
    assert choudhary_et_al.DATASET_DIR.name == "Choudhary_et_al"
    assert (
        "sources/literature/Choudhary_et_al" in choudhary_et_al.DATASET_DIR.as_posix()
    )
    assert choudhary_et_al.DEFAULT_XLSX.name == "mSystems.00980-20-sd002.xlsx"
    assert choudhary_et_al.DEFAULT_FASTA.name == "NC_000913.3.fasta"


def test_choudhary_provenance_paths_are_repo_relative() -> None:
    assert choudhary_et_al.provenance_path(choudhary_et_al.DEFAULT_XLSX) == (
        "sources/literature/Choudhary_et_al/raw/mSystems.00980-20-sd002.xlsx"
    )


def test_bie_cli_subcommands_parse_without_optional_pandas_dependency() -> None:
    args = bie_et_al.parse_args(["downregulated", "--input", "source.xlsx"])

    assert args.command == "downregulated"
    assert args.input == "source.xlsx"


def test_bie_optional_dependencies_fail_fast_when_missing() -> None:
    if importlib.util.find_spec("pandas") is not None:
        pytest.skip("pandas is installed in this environment")

    with pytest.raises(ImportError, match="pandas is required"):
        bie_et_al.load_csv("missing.csv")
