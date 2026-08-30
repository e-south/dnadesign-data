"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/motifs/regulondb.py

Exports release-pinned RegulonDB TF-RISet records as typed binding-site sets.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import csv
import io
import re
from collections import Counter
from pathlib import Path
from typing import Any

from dnadesign_data.motifs.contracts import (
    DNA_ALPHABET,
    SITE_SET_SCHEMA,
    MotifExportError,
    build_manifest,
    read_source_bytes,
    sha256_bytes,
    validate_identity,
)
from dnadesign_data.motifs.providers import resolve_catalog_source

PROVIDER_ID = "regulondb_tf_riset_sites_v1"
_HEADER_PREFIX = re.compile(r"^\d+\)")
_UPPERCASE_RUN = re.compile(r"[A-Z]+")


def _normalize_header(value: str) -> str:
    return _HEADER_PREFIX.sub("", value.strip()).strip().lower()


def _find_table_lines(text: str) -> tuple[list[str], list[list[str]]]:
    lines = [line for line in text.splitlines() if line and not line.startswith("#")]
    if not lines:
        raise MotifExportError("RegulonDB TF-RISet source contains no table")
    reader = csv.reader(io.StringIO("\n".join(lines)), delimiter="\t")
    rows = list(reader)
    if not rows:
        raise MotifExportError("RegulonDB TF-RISet source contains no table")
    header = [_normalize_header(value) for value in rows[0]]
    duplicate_headers = sorted(
        name for name, count in Counter(header).items() if count > 1
    )
    if duplicate_headers:
        raise MotifExportError(
            f"RegulonDB TF-RISet has duplicate normalized columns: {duplicate_headers}"
        )
    required = {
        "riid",
        "regulatorname",
        "regulatorid",
        "tfrsid",
        "tfrsleft",
        "tfrsright",
        "strand",
        "tfrsseq",
        "confidencelevel",
        "tfrspmids",
    }
    missing = sorted(required - set(header))
    if missing:
        raise MotifExportError(f"RegulonDB TF-RISet columns are missing: {missing}")
    return header, rows[1:]


def _parse_positive_int(value: str, *, field: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise MotifExportError(f"RegulonDB {field} must be an integer") from exc
    if parsed <= 0:
        raise MotifExportError(f"RegulonDB {field} must be positive")
    return parsed


def _extract_core(value: str) -> str:
    runs = _UPPERCASE_RUN.findall(value)
    if len(runs) != 1:
        raise MotifExportError(
            "RegulonDB tfrsSeq must contain exactly one uppercase binding-site core"
        )
    sequence = runs[0]
    if set(sequence) - set(DNA_ALPHABET):
        raise MotifExportError(
            "RegulonDB uppercase binding-site core must contain only A/C/G/T"
        )
    return sequence


def _strand(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"forward", "+", "plus"}:
        return "+"
    if normalized in {"reverse", "-", "minus"}:
        return "-"
    raise MotifExportError(f"unrecognized RegulonDB strand value {value!r}")


def _genomic_forward(sequence: str, strand: str) -> str:
    if strand == "+":
        return sequence
    return sequence.translate(str.maketrans("ACGT", "TGCA"))[::-1]


def _split_semicolon(value: str) -> list[str]:
    return sorted({item.strip() for item in value.split(";") if item.strip()})


def build_regulondb_site_export(
    source_path: str | Path,
    *,
    regulator_name: str,
    source_descriptor_id: str,
    orientation: str,
    data_root: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Build a deterministic, as-recorded binding-site export for one regulator."""

    requested_name = validate_identity(regulator_name, label="regulator_name")
    if orientation != "genomic_forward":
        raise MotifExportError("orientation must be exactly 'genomic_forward'")
    source_path, descriptor = resolve_catalog_source(
        source_path,
        source_descriptor_id=source_descriptor_id,
        expected_parser_hint=PROVIDER_ID,
        data_root=data_root,
    )
    source, raw = read_source_bytes(source_path)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise MotifExportError(
            f"RegulonDB source {source.name!r} must be UTF-8 text"
        ) from exc
    header, values = _find_table_lines(text)
    indexes = {name: index for index, name in enumerate(header)}
    matched: list[dict[str, str]] = []
    for line_number, row in enumerate(values, start=2):
        if len(row) != len(header):
            raise MotifExportError(
                f"RegulonDB TF-RISet row {line_number} has {len(row)} columns; "
                f"expected {len(header)}"
            )
        record = {name: row[index].strip() for name, index in indexes.items()}
        if record["regulatorname"].casefold() == requested_name.casefold():
            matched.append(record)
    if not matched:
        raise MotifExportError(
            f"RegulonDB source contains no records for regulator {requested_name!r}"
        )
    regulator_ids = {
        record["regulatorid"] for record in matched if record["regulatorid"]
    }
    if len(regulator_ids) != 1:
        raise MotifExportError(
            f"RegulonDB selection for {requested_name!r} resolves to multiple regulator identifiers"
        )
    canonical_names = {record["regulatorname"] for record in matched}
    if len({name.casefold() for name in canonical_names}) != 1:
        raise MotifExportError(
            f"RegulonDB selection for {requested_name!r} has ambiguous regulator names"
        )

    by_site: dict[str, dict[str, Any]] = {}
    exclusions: Counter[str] = Counter()
    for record in matched:
        if not record["tfrsid"]:
            exclusions["missing_site_identity"] += 1
            continue
        if not record["tfrsseq"]:
            exclusions["missing_site_sequence"] += 1
            continue
        site_id = validate_identity(record["tfrsid"], label="tfrsID")
        source_strand = _strand(record["strand"])
        source_sequence = _extract_core(record["tfrsseq"])
        site = {
            "site_id": site_id,
            "sequence": _genomic_forward(source_sequence, source_strand),
            "source_strands": [source_strand],
            "left": _parse_positive_int(record["tfrsleft"], field="tfrsLeft"),
            "right": _parse_positive_int(record["tfrsright"], field="tfrsRight"),
            "interaction_ids": [validate_identity(record["riid"], label="riId")],
            "confidence_levels": _split_semicolon(record["confidencelevel"]),
            "pmids": _split_semicolon(record["tfrspmids"]),
        }
        if site["right"] < site["left"]:
            raise MotifExportError(
                f"RegulonDB site {site_id!r} has reversed coordinates"
            )
        previous = by_site.get(site_id)
        if previous is None:
            by_site[site_id] = site
            continue
        stable_fields = ("sequence", "left", "right")
        if any(previous[field] != site[field] for field in stable_fields):
            raise MotifExportError(
                f"RegulonDB site {site_id!r} has conflicting duplicate records"
            )
        for list_field in (
            "source_strands",
            "interaction_ids",
            "confidence_levels",
            "pmids",
        ):
            previous[list_field] = sorted(
                set(previous[list_field]) | set(site[list_field])
            )

    sites = [by_site[key] for key in sorted(by_site)]
    if not sites:
        raise MotifExportError(
            f"RegulonDB source contains no usable binding-site sequences for "
            f"regulator {requested_name!r}"
        )
    widths = sorted({len(site["sequence"]) for site in sites})
    model_ready = len(widths) == 1
    readiness_reason = (
        "site sequences have equal widths"
        if model_ready
        else "site sequences have unequal widths; alignment or window policy is required"
    )
    excluded_row_count = sum(exclusions.values())
    usable_observation_count = len(matched) - excluded_row_count
    source_digest = sha256_bytes(raw)
    site_set: dict[str, Any] = {
        "schema_version": SITE_SET_SCHEMA,
        "alphabet": list(DNA_ALPHABET),
        "regulator": {
            "id": next(iter(regulator_ids)),
            "name": min(canonical_names, key=lambda value: value.encode("utf-8")),
        },
        "source_digest": source_digest,
        "source_name": source.name,
        "coordinate_system": "regulondb_1based_inclusive",
        "sequence_semantics": "uppercase_tfrs_core_v1",
        "orientation": "genomic_forward",
        "widths": widths,
        "model_readiness": {"ready": model_ready, "reason": readiness_reason},
        "selection_summary": {
            "matched_row_count": len(matched),
            "usable_observation_count": usable_observation_count,
            "unique_site_count": len(sites),
            "duplicate_observation_count": usable_observation_count - len(sites),
            "excluded_row_count": excluded_row_count,
            "exclusion_reasons": dict(sorted(exclusions.items())),
        },
        "sites": sites,
    }
    manifest = build_manifest(
        provider_id=PROVIDER_ID,
        output_schema=SITE_SET_SCHEMA,
        artifact=site_set,
        source_name=source.name,
        source_digest=source_digest,
        source_descriptor_id=source_descriptor_id,
        source_revision=descriptor.release,
        redistribution_status=descriptor.redistribution_status,
        selection={
            "regulator_name": requested_name,
            "sequence_semantics": "uppercase_tfrs_core_v1",
            "orientation": "genomic_forward",
        },
    )
    return {"artifact": site_set, "manifest": manifest}
