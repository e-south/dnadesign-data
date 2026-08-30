"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/functional/biocyc_smarttables.py

Builds regulator GO-term artifacts through authenticated BioCyc SmartTables.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from dnadesign_data.catalog.functional_annotations import (
    FunctionalAnnotationSourceFile,
    iter_regulator_identity_source_files,
    known_functional_annotation_source_files,
)
from dnadesign_data.core.layout import biocyc_kb_path
from dnadesign_data.functional.biocyc_client import (
    PROPERTY_IDS,
    TRANSFORM_ASPECTS,
    TRANSFORM_IDS,
    BioCycSmartTableClient,
)
from dnadesign_data.functional.go_parsers import (
    parse_go_basic_obo,
    parse_smarttable_go_tsv,
)
from dnadesign_data.functional.regulator_identities import (
    RegulatorIdentity,
    load_regulator_identities,
)
from dnadesign_data.functional.table_io import (
    file_manifest,
    sha256,
    source_file_manifest,
    utc_now_iso,
    write_bytes,
    write_json,
    write_tsv,
)

PathLike = str | Path

SCHEMA_VERSION = "biocyc_smarttable_regulator_go_terms.v2"
REGULATOR_GO_FIELDS = (
    "regulator_id",
    "regulator_name",
    "regulator_gene_name",
    "gene_symbol",
    "go_aspect",
    "go_id",
    "go_name",
    "go_namespace",
    "source_column",
    "source_route",
    "identity_source_id",
    "biocyc_kb_version",
    "smarttable_id",
)
REGULATOR_COVERAGE_FIELDS = (
    "regulator_id",
    "regulator_name",
    "regulator_gene_name",
    "gene_symbol_count",
    "matched_go_term_count",
    "mapping_status",
    "identity_source_id",
    "biocyc_kb_version",
    "smarttable_id",
)


def build_biocyc_smarttable_artifacts(
    root: PathLike | None = None,
    *,
    client: BioCycSmartTableClient,
    orgid: str = "ECOLI",
    allow_empty_go_terms: bool = False,
    require_go_ontology: bool = True,
) -> dict[str, object]:
    """Create a regulator SmartTable, retrieve GO transforms, and persist artifacts."""

    base = Path.cwd() if root is None else Path(root)
    identity_sources = tuple(iter_regulator_identity_source_files(base))
    if not identity_sources:
        raise FileNotFoundError(
            "No regulator identity source found. Expected "
            "sources/databases/regulondb/13.0/network_interactions/NetworkRegulatorGene.tsv or "
            "sources/databases/regulondb/11.0/transcription_factors/TFSet.txt."
        )
    identities = load_regulator_identities(base, identity_sources)
    gene_symbols = sorted(
        {
            gene_symbol
            for identity in identities
            for gene_symbol in identity.gene_symbols
        },
        key=str.lower,
    )
    if not gene_symbols:
        raise ValueError("Regulator identity sources did not expose gene symbols")
    ontology_source = _known_functional_source_by_role("go_term_ontology")
    ontology_path = ontology_source.absolute_path(base)
    go_terms = {}
    if ontology_path.exists():
        go_terms = parse_go_basic_obo(ontology_path)
    elif require_go_ontology:
        raise FileNotFoundError(
            "Missing GO ontology required to name BioCyc SmartTable GO terms: "
            f"{ontology_path}"
        )

    kb_version = client.kb_version(orgid=orgid)
    output_root = base / biocyc_kb_path(kb_version, "smarttables", "regulator_go_terms")
    raw_dir = output_root / "raw"
    processed_dir = output_root / "processed"
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    request_payload = {
        "name": f"dnadesign regulator GO terms {kb_version}",
        "description": (
            "RegulonDB regulator coding genes for dnadesign functional "
            "annotation enrichment; created by dnadesign-data."
        ),
        "pgdb": orgid,
        "type": "Genes",
        "values": gene_symbols,
    }
    write_json(raw_dir / "create_request.json", request_payload)
    smarttable_id, create_response = client.create_gene_smarttable(
        gene_symbols=gene_symbols,
        name=str(request_payload["name"]),
        description=str(request_payload["description"]),
        orgid=orgid,
    )
    sanitized_create_response = _redact_biocyc_create_response(create_response)
    write_json(raw_dir / "create_response.json", sanitized_create_response)
    property_responses = {}
    for property_id in PROPERTY_IDS:
        response = client.add_property(smarttable_id, property_id)
        filename = f"property_{property_id}.bin"
        write_bytes(raw_dir / filename, response)
        property_responses[property_id] = {
            "path": str(raw_dir / filename),
            "sha256": sha256(raw_dir / filename),
            "byte_count": len(response),
        }
    transform_responses = {}
    for transform_id in TRANSFORM_IDS:
        response = client.add_transform(smarttable_id, transform_id)
        filename = f"transform_{transform_id}.bin"
        write_bytes(raw_dir / filename, response)
        transform_responses[transform_id] = {
            "path": str(raw_dir / filename),
            "sha256": sha256(raw_dir / filename),
            "byte_count": len(response),
            "aspect": TRANSFORM_ASPECTS[transform_id],
        }
    tsv_response = client.get_tsv(smarttable_id, orgid=orgid)
    write_bytes(raw_dir / "st_get.tsv", tsv_response)

    smarttable_go_rows = _enrich_smarttable_go_terms(
        parse_smarttable_go_tsv(tsv_response),
        go_terms,
    )
    if not smarttable_go_rows and not allow_empty_go_terms:
        raise ValueError("No GO terms parsed from BioCyc SmartTable TSV")

    regulator_rows, coverage_rows = _join_identities_to_smarttable_terms(
        identities,
        smarttable_go_rows,
        kb_version=kb_version,
        smarttable_id=smarttable_id,
    )
    if not regulator_rows and not allow_empty_go_terms:
        raise ValueError("No regulator GO terms matched BioCyc SmartTable genes")

    write_tsv(
        processed_dir / "regulator_go_terms.tsv",
        REGULATOR_GO_FIELDS,
        regulator_rows,
    )
    write_tsv(
        processed_dir / "regulator_go_coverage.tsv",
        REGULATOR_COVERAGE_FIELDS,
        coverage_rows,
    )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "created_at": utc_now_iso(),
        "sources": {
            "biocyc": {
                "source_id": "biocyc_smarttable_go_terms",
                "source": "biocyc",
                "kb_version": kb_version,
                "orgid": orgid,
                "base_url": client.base_url,
                "auth_required": True,
                "credentials_persisted": False,
                "smarttable_id": smarttable_id,
                "transforms": list(TRANSFORM_IDS),
            },
            "ontology": (
                source_file_manifest(ontology_source, ontology_path)
                if ontology_path.exists()
                else None
            ),
            "regulator_identity": [
                source_file_manifest(source, source.absolute_path(base))
                for source in identity_sources
            ],
        },
        "raw_artifacts": {
            "create_request": file_manifest(raw_dir / "create_request.json"),
            "create_response": file_manifest(raw_dir / "create_response.json"),
            "st_get_tsv": file_manifest(raw_dir / "st_get.tsv"),
            "property_responses": property_responses,
            "transform_responses": transform_responses,
        },
        "row_counts": {
            "regulator_identities": len(identities),
            "smarttable_genes": len(gene_symbols),
            "smarttable_go_terms": len(smarttable_go_rows),
            "regulator_go_terms": len(regulator_rows),
            "regulator_go_coverage": len(coverage_rows),
        },
        "contracts": {
            "smarttable_gene_column_index": 0,
            "gene_symbol_column": "Common-Name",
            "transform_ids": list(TRANSFORM_IDS),
            "property_ids": list(PROPERTY_IDS),
            "credentials_persisted": False,
            "require_go_ontology": require_go_ontology,
            "go_name_source": (
                ontology_source.source_id if ontology_path.exists() else "smarttable"
            ),
            "regulator_membership": "binary source identity rows, not interaction counts",
        },
        "outputs": {
            "regulator_go_terms": str(processed_dir / "regulator_go_terms.tsv"),
            "regulator_go_coverage": str(processed_dir / "regulator_go_coverage.tsv"),
        },
    }
    write_json(processed_dir / "manifest.json", manifest)
    return manifest


def _redact_biocyc_create_response(response: bytes) -> dict[str, object]:
    text = response.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {"response_preview": text[:200], "redacted": True}
    if not isinstance(parsed, dict):
        return {"response_type": type(parsed).__name__, "redacted": True}
    sanitized = dict(parsed)
    if "login-token" in sanitized:
        sanitized["login-token"] = "<redacted>"
    return sanitized


def _known_functional_source_by_role(role: str) -> FunctionalAnnotationSourceFile:
    matches = [
        source
        for source in known_functional_annotation_source_files()
        if source.role == role
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one functional source with role {role!r}")
    return matches[0]


def _enrich_smarttable_go_terms(
    rows: Sequence[dict[str, str]],
    go_terms: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    enriched = []
    for row in rows:
        term = go_terms.get(row["go_id"], {})
        enriched.append(
            {
                **row,
                "go_name": term.get("go_name", row.get("go_name", "")),
                "go_namespace": term.get("go_namespace", ""),
            }
        )
    return enriched


def _join_identities_to_smarttable_terms(
    identities: Sequence[RegulatorIdentity],
    smarttable_go_rows: Sequence[dict[str, str]],
    *,
    kb_version: str,
    smarttable_id: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    go_rows_by_symbol: dict[str, list[dict[str, str]]] = {}
    for row in smarttable_go_rows:
        go_rows_by_symbol.setdefault(row["gene_symbol"].lower(), []).append(row)

    regulator_rows: list[dict[str, str]] = []
    coverage_rows: list[dict[str, str]] = []
    emitted: set[tuple[str, str, str, str]] = set()
    for identity in identities:
        matched_go_ids: set[str] = set()
        for gene_symbol in identity.gene_symbols:
            for go_row in go_rows_by_symbol.get(gene_symbol.lower(), []):
                key = (
                    identity.regulator_id,
                    gene_symbol.lower(),
                    go_row["go_aspect"],
                    go_row["go_id"],
                )
                if key in emitted:
                    continue
                emitted.add(key)
                matched_go_ids.add(go_row["go_id"])
                regulator_rows.append(
                    {
                        "regulator_id": identity.regulator_id,
                        "regulator_name": identity.regulator_name,
                        "regulator_gene_name": identity.regulator_gene_name,
                        "gene_symbol": gene_symbol,
                        "go_aspect": go_row["go_aspect"],
                        "go_id": go_row["go_id"],
                        "go_name": go_row["go_name"],
                        "go_namespace": go_row["go_namespace"],
                        "source_column": go_row["source_column"],
                        "source_route": "biocyc_smarttable_gene_go_terms",
                        "identity_source_id": identity.source_id,
                        "biocyc_kb_version": kb_version,
                        "smarttable_id": smarttable_id,
                    }
                )
        coverage_rows.append(
            {
                "regulator_id": identity.regulator_id,
                "regulator_name": identity.regulator_name,
                "regulator_gene_name": identity.regulator_gene_name,
                "gene_symbol_count": str(len(identity.gene_symbols)),
                "matched_go_term_count": str(len(matched_go_ids)),
                "mapping_status": _mapping_status(identity, matched_go_ids),
                "identity_source_id": identity.source_id,
                "biocyc_kb_version": kb_version,
                "smarttable_id": smarttable_id,
            }
        )
    return regulator_rows, coverage_rows


def _mapping_status(identity: RegulatorIdentity, matched_go_ids: set[str]) -> str:
    if not identity.gene_symbols:
        return "missing_regulator_gene"
    if matched_go_ids:
        return "matched"
    return "unmatched_gene_symbol"
