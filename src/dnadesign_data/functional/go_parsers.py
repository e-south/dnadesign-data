"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/functional/go_parsers.py

Parses GO annotation, ontology, and BioCyc SmartTable rows.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import csv
import gzip
import re
from pathlib import Path
from typing import TextIO

from dnadesign_data.catalog.functional_annotations import FunctionalAnnotationSourceFile

GAF_COLUMN_COUNT = 17
GO_COLUMN_ASPECTS = {
    "go terms (molecular function)": "molecular_function",
    "go terms (biological process)": "biological_process",
    "go terms (cellular component)": "cellular_component",
}
GO_ID_PATTERN = re.compile(r"(GO:\d{7})")
SMARTTABLE_GENE_SYMBOL_COLUMNS = ("common-name", "gene symbol", "gene_symbol")


def parse_gaf(
    path: Path,
    annotation_source: FunctionalAnnotationSourceFile,
    ontology_source: FunctionalAnnotationSourceFile,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with _open_text(path) as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip() or line.startswith("!"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) != GAF_COLUMN_COUNT:
                raise ValueError(
                    f"Expected 17 GAF columns at {path}:{line_number}, "
                    f"found {len(parts)}"
                )
            rows.append(
                {
                    "db": parts[0].strip(),
                    "db_object_id": parts[1].strip(),
                    "db_object_symbol": parts[2].strip(),
                    "qualifier": parts[3].strip(),
                    "go_id": parts[4].strip(),
                    "db_reference": parts[5].strip(),
                    "evidence_code": parts[6].strip(),
                    "with_or_from": parts[7].strip(),
                    "go_aspect": parts[8].strip(),
                    "db_object_name": parts[9].strip(),
                    "db_object_synonym": parts[10].strip(),
                    "db_object_type": parts[11].strip(),
                    "taxon": parts[12].strip(),
                    "date": parts[13].strip(),
                    "assigned_by": parts[14].strip(),
                    "annotation_extension": parts[15].strip(),
                    "gene_product_form_id": parts[16].strip(),
                    "source_annotation_file": annotation_source.source_id,
                    "source_ontology_file": ontology_source.source_id,
                }
            )
    if not rows:
        raise ValueError(f"No GAF annotation rows parsed from {path}")
    return rows


def parse_go_basic_obo(path: Path) -> dict[str, dict[str, str]]:
    terms: dict[str, dict[str, str]] = {}
    current: dict[str, str] = {}
    in_term = False
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if line == "[Term]":
                _store_obo_term(terms, current)
                current = {}
                in_term = True
                continue
            if line.startswith("[") and line.endswith("]"):
                _store_obo_term(terms, current)
                current = {}
                in_term = False
                continue
            if not in_term or not line or ": " not in line:
                continue
            key, value = line.split(": ", 1)
            if key in {"id", "name", "namespace", "is_obsolete"}:
                current[key] = value
    _store_obo_term(terms, current)
    if not terms:
        raise ValueError(f"No GO terms parsed from {path}")
    return terms


def parse_smarttable_go_tsv(payload: bytes) -> list[dict[str, str]]:
    text = payload.decode("utf-8-sig")
    reader = csv.DictReader(text.splitlines(), delimiter="\t")
    if not reader.fieldnames:
        raise ValueError("BioCyc SmartTable TSV lacked a header")
    gene_column = _select_smarttable_gene_symbol_column(reader.fieldnames)
    go_columns = [
        column
        for column in reader.fieldnames
        if column.strip().lower() in GO_COLUMN_ASPECTS
    ]
    if not go_columns:
        raise ValueError("BioCyc SmartTable TSV lacked GO transform columns")

    rows: list[dict[str, str]] = []
    emitted: set[tuple[str, str, str]] = set()
    for raw_row in reader:
        gene_symbol = _clean_smarttable_cell(raw_row.get(gene_column, ""))
        if not gene_symbol:
            continue
        for column in go_columns:
            aspect = GO_COLUMN_ASPECTS[column.strip().lower()]
            for go_id, go_name in _parse_go_cell(raw_row.get(column, "")):
                key = (gene_symbol.lower(), aspect, go_id)
                if key in emitted:
                    continue
                emitted.add(key)
                rows.append(
                    {
                        "gene_symbol": gene_symbol,
                        "go_aspect": aspect,
                        "go_id": go_id,
                        "go_name": go_name,
                        "source_column": column,
                    }
                )
    return rows


def _store_obo_term(
    terms: dict[str, dict[str, str]],
    current: dict[str, str],
) -> None:
    go_id = current.get("id", "")
    if not go_id:
        return
    if go_id in terms:
        raise ValueError(f"Duplicate GO term id in ontology: {go_id}")
    terms[go_id] = {
        "go_id": go_id,
        "go_name": current.get("name", ""),
        "go_namespace": current.get("namespace", ""),
        "is_obsolete": current.get("is_obsolete", "false"),
    }


def _parse_go_cell(raw: str) -> list[tuple[str, str]]:
    text = _clean_smarttable_cell(raw)
    if not text:
        return []
    chunks = [
        chunk.strip() for chunk in re.split(r"\s*//\s*|;|\n|\|", text) if chunk.strip()
    ]
    parsed: list[tuple[str, str]] = []
    for chunk in chunks:
        for match in GO_ID_PATTERN.finditer(chunk):
            go_id = match.group(1)
            go_name = chunk[match.end() :].strip(" -:/()[]")
            if GO_ID_PATTERN.search(go_name):
                go_name = ""
            parsed.append((go_id, go_name))
    return parsed


def _clean_smarttable_cell(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value).strip()


def _select_smarttable_gene_symbol_column(fieldnames: list[str]) -> str:
    normalized = {field.strip().lower(): field for field in fieldnames}
    for candidate in SMARTTABLE_GENE_SYMBOL_COLUMNS:
        if candidate in normalized:
            return normalized[candidate]
    return fieldnames[0]


def _open_text(path: Path) -> TextIO:
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", newline="")
    return path.open("r", encoding="utf-8", newline="")
