"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/functional/regulator_identities.py

Parses regulator identities shared by functional annotation builders.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import csv
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from dnadesign_data.catalog.functional_annotations import RegulatorIdentitySourceFile


@dataclass(frozen=True)
class RegulatorIdentity:
    regulator_id: str
    regulator_name: str
    regulator_gene_name: str
    gene_symbols: tuple[str, ...]
    source_id: str


def load_regulator_identities(
    root: Path,
    sources: Sequence[RegulatorIdentitySourceFile],
) -> list[RegulatorIdentity]:
    identities: dict[tuple[str, str, str], RegulatorIdentity] = {}
    for source in sources:
        path = source.absolute_path(root)
        _require_file(path, source.source_id)
        if source.parser_hint == "regulondb_network_regulator_gene":
            parsed = _parse_network_regulator_gene(path, source.source_id)
        elif source.parser_hint == "regulondb_tf_set":
            parsed = _parse_tf_set(path, source.source_id)
        else:
            raise ValueError(
                f"Unsupported regulator identity parser: {source.parser_hint}"
            )
        for identity in parsed:
            key = (
                identity.regulator_id,
                identity.regulator_name.lower(),
                identity.regulator_gene_name.lower(),
            )
            identities.setdefault(key, identity)
    return list(identities.values())


def _parse_network_regulator_gene(
    path: Path, source_id: str
) -> list[RegulatorIdentity]:
    rows: list[RegulatorIdentity] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        header: list[str] | None = None
        for raw in reader:
            if not raw:
                continue
            first = raw[0].strip().strip('"')
            if first.startswith("#"):
                continue
            if header is None:
                header = [_clean_header(cell) for cell in raw]
                continue
            row = {
                header[index]: value.strip().strip('"')
                for index, value in enumerate(raw[: len(header)])
            }
            regulator_id = row.get("regulatorid", "")
            regulator_name = row.get("regulatorname", "")
            regulator_gene_name = row.get("regulatorgenename", "")
            if not regulator_id or not regulator_name:
                continue
            rows.append(
                RegulatorIdentity(
                    regulator_id=regulator_id,
                    regulator_name=regulator_name,
                    regulator_gene_name=regulator_gene_name,
                    gene_symbols=split_gene_symbols(regulator_gene_name),
                    source_id=source_id,
                )
            )
    if not rows:
        raise ValueError(f"No regulator identity rows parsed from {path}")
    return rows


def _parse_tf_set(path: Path, source_id: str) -> list[RegulatorIdentity]:
    rows: list[RegulatorIdentity] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for raw in reader:
            if not raw or raw[0].strip().startswith("#"):
                continue
            if len(raw) < 3:
                raise ValueError(f"Expected at least 3 TFSet columns in {path}")
            regulator_id = raw[0].strip().strip('"')
            regulator_name = raw[1].strip().strip('"')
            regulator_gene_name = raw[2].strip().strip('"')
            if not regulator_id or not regulator_name:
                continue
            rows.append(
                RegulatorIdentity(
                    regulator_id=regulator_id,
                    regulator_name=regulator_name,
                    regulator_gene_name=regulator_gene_name,
                    gene_symbols=split_gene_symbols(regulator_gene_name),
                    source_id=source_id,
                )
            )
    if not rows:
        raise ValueError(f"No TFSet identity rows parsed from {path}")
    return rows


def split_gene_symbols(raw: str) -> tuple[str, ...]:
    genes = []
    for token in re.split(r"[,;]", raw.strip().strip('"')):
        gene = token.strip().strip('"')
        if gene:
            genes.append(gene)
    return tuple(dict.fromkeys(genes))


def _clean_header(value: str) -> str:
    cleaned = value.strip().strip('"')
    if ")" in cleaned and cleaned.split(")", 1)[0].isdigit():
        cleaned = cleaned.split(")", 1)[1]
    return re.sub(r"[^a-z0-9]", "", cleaned.lower())


def _require_file(path: Path, source_id: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing required source {source_id}: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"Required source is not a file {source_id}: {path}")
