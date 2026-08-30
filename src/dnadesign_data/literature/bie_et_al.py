"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/literature/bie_et_al.py

Provides utilities for Bie et al. antibiotic-response transcriptomics.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from dnadesign_data.core.layout import default_data_root, literature_path

BIE_DATASET_DIR = default_data_root() / literature_path("Bie_et_al")
DEFAULT_XLSX = BIE_DATASET_DIR / "spectrum.00317-23-s0002.xlsx"
DEFAULT_KAN_OUTPUT = BIE_DATASET_DIR / "output_kanamycin.csv"
DEFAULT_CIPRO_OUTPUT = BIE_DATASET_DIR / "output_ciprofloxacin.csv"
DEFAULT_REFERENCE_OUTPUT = BIE_DATASET_DIR / "top_stable_genes.csv"
DEFAULT_KAN_PLOT = BIE_DATASET_DIR / "kanamycin_plot.pdf"
DEFAULT_CIPRO_PLOT = BIE_DATASET_DIR / "ciprofloxacin_plot.pdf"
DEFAULT_SHEET = "1"
DEFAULT_REPLICATES = ("_2_fpkm", "_3_fpkm", "_4_fpkm")
DEFAULT_REFERENCE_THRESHOLD = 250
DEFAULT_HIGHLIGHT_GENES = ("malK", "cyoA", "nuoA", "rpsL", "fliC")


def _require_pandas():
    try:
        import pandas as pd
    except ImportError as exc:
        raise ImportError(
            "pandas is required for Bie et al. transcriptomics helpers."
        ) from exc
    return pd


def _require_pyplot():
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise ImportError(
            "matplotlib is required for Bie et al. plot helpers."
        ) from exc
    return plt


def load_data(file_path=DEFAULT_XLSX, sheet_name=DEFAULT_SHEET):
    """Load the Bie et al. Excel sheet using the corrected header row."""

    pd = _require_pandas()
    return pd.read_excel(file_path, sheet_name=sheet_name, header=1)


def compute_average_fpkm(
    data: Any, prefix: str, replicates: tuple[str, ...] = DEFAULT_REPLICATES
):
    """Compute average FPKM values across available replicate columns."""

    columns = [f"{prefix}{replicate}" for replicate in replicates]
    valid_columns = [column for column in columns if column in data.columns]
    if not valid_columns:
        raise KeyError(
            f"No valid columns found for prefix {prefix!r} with replicates {replicates!r}"
        )
    return data[valid_columns].mean(axis=1)


def filter_downregulated_genes(
    data: Any,
    *,
    log2_fc_col: str,
    significant_col: str,
    abx_fpkm_col: str,
    h2o_fpkm_col: str,
):
    """Filter and rank downregulated genes for one antibiotic comparison."""

    retained_columns = [
        "Gene_id",
        "Genename",
        log2_fc_col,
        significant_col,
        abx_fpkm_col,
        h2o_fpkm_col,
        "biological_process",
        "biological_process_description",
        "cellular_component",
        "cellular_component_description",
        "molecular_function",
        "molecular_function_description",
        "KEGG AnnotInfo",
        "KEGG url",
        "Description",
    ]
    filtered = data[(data[log2_fc_col] < 0) & (data[significant_col] == "DOWN")][
        retained_columns
    ].copy()
    filtered["FPKM_Difference"] = filtered[abx_fpkm_col] - filtered[h2o_fpkm_col]
    filtered["Rank_FPKM"] = filtered[h2o_fpkm_col].rank(ascending=False)
    filtered["Rank_Log2FC"] = filtered[log2_fc_col].rank(ascending=True)
    filtered["Effect_Size"] = filtered["Rank_FPKM"] + filtered["Rank_Log2FC"]
    return filtered.sort_values(by="Effect_Size", ascending=True)


def build_downregulated_gene_tables(data: Any):
    """Build Kanamycin and Ciprofloxacin downregulated-gene tables."""

    data = data.copy()
    data["KAN_avg_fpkm"] = compute_average_fpkm(data, "KAN")
    data["CIP_avg_fpkm"] = compute_average_fpkm(data, "CIP")
    data["H2O_avg_fpkm"] = compute_average_fpkm(data, "H2O")
    return {
        "kanamycin": filter_downregulated_genes(
            data,
            log2_fc_col="log2FoldChange(KANvsH2O)",
            significant_col="significant(KANvsH2O)",
            abx_fpkm_col="KAN_avg_fpkm",
            h2o_fpkm_col="H2O_avg_fpkm",
        ),
        "ciprofloxacin": filter_downregulated_genes(
            data,
            log2_fc_col="log2FoldChange(CIPvsH2O)",
            significant_col="significant(CIPvsH2O)",
            abx_fpkm_col="CIP_avg_fpkm",
            h2o_fpkm_col="H2O_avg_fpkm",
        ),
    }


def write_downregulated_gene_tables(
    input_file=DEFAULT_XLSX,
    *,
    output_kan_file=DEFAULT_KAN_OUTPUT,
    output_cipro_file=DEFAULT_CIPRO_OUTPUT,
) -> dict:
    """Write Kanamycin and Ciprofloxacin downregulated-gene CSV outputs."""

    tables = build_downregulated_gene_tables(load_data(input_file))
    outputs = {
        "kanamycin": Path(output_kan_file),
        "ciprofloxacin": Path(output_cipro_file),
    }
    for key, output_path in outputs.items():
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tables[key].to_csv(output_path, index=False)
    return outputs


def find_reference_genes(
    input_file=DEFAULT_XLSX,
    *,
    output_csv=DEFAULT_REFERENCE_OUTPUT,
    threshold=DEFAULT_REFERENCE_THRESHOLD,
):
    """Find highly expressed, non-significantly changing reference genes."""

    data = load_data(input_file)
    significant_cols = [column for column in data.columns if "significant" in column]
    log2fc_cols = [column for column in data.columns if "log2FoldChange" in column]
    if not significant_cols or not log2fc_cols:
        raise ValueError(
            "critical column groups are missing: significant/log2FoldChange"
        )

    essential_cols = ["significant(KANvsH2O)", "significant(CIPvsH2O)"]
    while True:
        significant_filtered = data[significant_cols].apply(
            lambda column: (
                column.fillna("MISSING")
                .replace(False, "FALSE")
                .astype(str)
                .str.strip()
                .str.upper()
            )
        )
        filtered_rows = significant_filtered.apply(
            lambda column: (column == "FALSE").all(), axis=1
        )
        stable_genes = data[filtered_rows]
        if len(stable_genes) >= threshold:
            break
        if len(stable_genes) == 0 and len(significant_cols) > len(essential_cols):
            non_essential_cols = [
                column for column in significant_cols if column not in essential_cols
            ]
            if non_essential_cols:
                significant_cols.remove(non_essential_cols[-1])
                continue
        break

    ranking_cols = [
        "padj(CIPvsH2O)",
        "padj(KANvsH2O)",
        "log2FoldChange(CIPvsH2O)",
        "log2FoldChange(KANvsH2O)",
    ]
    for column in ranking_cols:
        if column not in data.columns:
            raise ValueError(
                f"The required ranking column {column} is missing from the dataset."
            )

    stable_genes_sorted = stable_genes.sort_values(
        by=ranking_cols,
        ascending=[False, False, True, True],
    ).copy()
    for condition in ("KAN", "CIP", "H2O"):
        stable_genes_sorted[f"avg_fpkm_{condition}"] = compute_average_fpkm(
            stable_genes_sorted, condition
        )

    top_stable_genes = stable_genes_sorted.sort_values(
        by=["avg_fpkm_KAN", "avg_fpkm_CIP", "avg_fpkm_H2O"],
        ascending=False,
    )
    if output_csv is not None:
        output_path = Path(output_csv)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        top_stable_genes.to_csv(output_path, index=False)
    return top_stable_genes


def load_csv(file_path):
    """Load a ranked fold-change CSV output."""

    pd = _require_pandas()
    return pd.read_csv(file_path)


def get_top_movers(data: Any, effect_size_col: str, top_movers: int = 10):
    """Return top movers sorted by the effect-size ranking column."""

    return data.nsmallest(top_movers, effect_size_col)


def compare_top_movers(
    kan_data: Any, cipro_data: Any, effect_size_col: str, top_movers: int = 15
):
    """Compare top-mover gene names between Kanamycin and Ciprofloxacin tables."""

    kan_top = get_top_movers(kan_data, effect_size_col, top_movers)
    cipro_top = get_top_movers(cipro_data, effect_size_col, top_movers)
    kan_genes = set(kan_top["Genename"])
    cipro_genes = set(cipro_top["Genename"])
    return {
        "shared": sorted(kan_genes & cipro_genes),
        "unique_kanamycin": sorted(kan_genes - cipro_genes),
        "unique_ciprofloxacin": sorted(cipro_genes - kan_genes),
    }


def plot_fold_changes(
    data: Any,
    output_path,
    *,
    title: str,
    highlight_genes: tuple[str, ...] = DEFAULT_HIGHLIGHT_GENES,
    fold_change_col: str,
    effect_size_col: str,
    fpkm_diff_col: str,
    top_movers: int = 15,
) -> None:
    """Plot ranked fold changes with highlighted genes and top movers."""

    plt = _require_pyplot()
    required = {fold_change_col, effect_size_col, fpkm_diff_col, "Genename"}
    missing = required - set(data.columns)
    if missing:
        raise KeyError(f"Required columns not found in the dataset: {sorted(missing)}")

    data = data.copy()
    highlight = {gene.lower() for gene in highlight_genes}
    data["color"] = (
        data["Genename"]
        .str.lower()
        .apply(lambda gene: "blue" if gene in highlight else "gray")
    )
    top_movers_data = data.nsmallest(top_movers, effect_size_col)
    data.loc[top_movers_data.index, "color"] = "red"
    max_abs_difference = data[fpkm_diff_col].abs().max()
    data["PointSize"] = data[fpkm_diff_col].abs() / max_abs_difference * 150
    data = data.sort_values(by=fold_change_col, ascending=True).reset_index(drop=True)

    plt.figure(figsize=(14, 6))
    plt.axhline(0, color="lightgray", linestyle="--", linewidth=1)
    occupied_positions = set()

    def get_adjusted_position(x_value, y_value):
        offset = 0.1
        while (x_value, y_value) in occupied_positions:
            y_value += offset
        occupied_positions.add((x_value, y_value))
        return x_value, y_value

    for index, row in data.iterrows():
        plt.scatter(
            index,
            row[fold_change_col],
            color=row["color"],
            s=row["PointSize"],
            alpha=0.6,
        )
        if row["color"] in {"blue", "red"}:
            x_value, y_value = get_adjusted_position(index, row[fold_change_col])
            plt.text(
                x=x_value,
                y=y_value,
                s=row["Genename"],
                color="red" if row["color"] == "red" else "black",
                fontsize=12,
                fontweight="bold" if row["color"] == "blue" else "normal",
                ha="right",
                va="center",
            )

    plt.title(title, fontsize=16)
    plt.xlabel("Genes", fontsize=12)
    plt.ylabel("Log2 Fold Change", fontsize=12)
    plt.xticks([], [])
    plt.gca().spines["top"].set_visible(False)
    plt.gca().spines["right"].set_visible(False)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output, format="pdf", bbox_inches="tight")
    plt.close()


def plot_downregulated_gene_tables(
    input_kan_csv=DEFAULT_KAN_OUTPUT,
    input_cipro_csv=DEFAULT_CIPRO_OUTPUT,
    *,
    output_kan_pdf=DEFAULT_KAN_PLOT,
    output_cipro_pdf=DEFAULT_CIPRO_PLOT,
):
    """Generate Kanamycin and Ciprofloxacin fold-change plots."""

    kan_data = load_csv(input_kan_csv)
    cipro_data = load_csv(input_cipro_csv)
    plot_fold_changes(
        kan_data,
        output_kan_pdf,
        title="Ranked Fold Changes for Kanamycin (vs Water)",
        fold_change_col="log2FoldChange(KANvsH2O)",
        effect_size_col="Effect_Size",
        fpkm_diff_col="FPKM_Difference",
    )
    plot_fold_changes(
        cipro_data,
        output_cipro_pdf,
        title="Ranked Fold Changes for Ciprofloxacin (vs Water)",
        fold_change_col="log2FoldChange(CIPvsH2O)",
        effect_size_col="Effect_Size",
        fpkm_diff_col="FPKM_Difference",
    )
    return compare_top_movers(
        kan_data, cipro_data, effect_size_col="Effect_Size", top_movers=20
    )


def parse_args(argv: list | None = None):
    parser = argparse.ArgumentParser(
        description="Bie et al. antibiotic-response helpers."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    downregulated = subparsers.add_parser(
        "downregulated", help="write downregulated-gene CSV outputs"
    )
    downregulated.add_argument("--input", default=str(DEFAULT_XLSX))
    downregulated.add_argument("--output-kanamycin", default=str(DEFAULT_KAN_OUTPUT))
    downregulated.add_argument(
        "--output-ciprofloxacin", default=str(DEFAULT_CIPRO_OUTPUT)
    )

    reference = subparsers.add_parser(
        "reference-genes", help="write stable reference-gene CSV output"
    )
    reference.add_argument("--input", default=str(DEFAULT_XLSX))
    reference.add_argument("--output", default=str(DEFAULT_REFERENCE_OUTPUT))
    reference.add_argument("--threshold", type=int, default=DEFAULT_REFERENCE_THRESHOLD)

    plots = subparsers.add_parser("plots", help="write downregulated-gene PDF plots")
    plots.add_argument("--input-kanamycin", default=str(DEFAULT_KAN_OUTPUT))
    plots.add_argument("--input-ciprofloxacin", default=str(DEFAULT_CIPRO_OUTPUT))
    plots.add_argument("--output-kanamycin", default=str(DEFAULT_KAN_PLOT))
    plots.add_argument("--output-ciprofloxacin", default=str(DEFAULT_CIPRO_PLOT))
    return parser.parse_args(argv)


def main(argv: list | None = None) -> int:
    args = parse_args(argv)
    if args.command == "downregulated":
        outputs = write_downregulated_gene_tables(
            args.input,
            output_kan_file=args.output_kanamycin,
            output_cipro_file=args.output_ciprofloxacin,
        )
        print(f"Filtered data for Kanamycin saved to {outputs['kanamycin']}")
        print(f"Filtered data for Ciprofloxacin saved to {outputs['ciprofloxacin']}")
        return 0
    if args.command == "reference-genes":
        output = Path(args.output)
        reference_genes = find_reference_genes(
            args.input, output_csv=output, threshold=args.threshold
        )
        print(f"Top stable genes saved to {output} ({len(reference_genes)} rows)")
        return 0
    if args.command == "plots":
        comparison = plot_downregulated_gene_tables(
            args.input_kanamycin,
            args.input_ciprofloxacin,
            output_kan_pdf=args.output_kanamycin,
            output_cipro_pdf=args.output_ciprofloxacin,
        )
        print(f"Plot for Kanamycin saved to {args.output_kanamycin}")
        print(f"Plot for Ciprofloxacin saved to {args.output_ciprofloxacin}")
        print(f"Shared top movers: {comparison['shared']}")
        print(f"Unique Kanamycin top movers: {comparison['unique_kanamycin']}")
        print(f"Unique Ciprofloxacin top movers: {comparison['unique_ciprofloxacin']}")
        return 0
    raise ValueError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
