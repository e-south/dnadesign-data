"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/functional/ecocyc_go.py

Builds EcoCyc/GO functional annotation artifacts with source provenance.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from collections.abc import Sequence
from pathlib import Path

from dnadesign_data.catalog.functional_annotations import (
    FunctionalAnnotationSourceFile,
    iter_regulator_identity_source_files,
    known_functional_annotation_source_files,
)
from dnadesign_data.core.layout import gene_ontology_release_path
from dnadesign_data.functional.go_parsers import parse_gaf, parse_go_basic_obo
from dnadesign_data.functional.regulator_identities import (
    RegulatorIdentity,
    load_regulator_identities,
)
from dnadesign_data.functional.table_io import (
    require_file,
    source_file_manifest,
    utc_now_iso,
    write_json,
    write_tsv,
)

PathLike = str | Path

SCHEMA_VERSION = "ecocyc_go_functional_annotations.v1"

GO_TERM_FIELDS = ("go_id", "go_name", "go_namespace", "is_obsolete")
GAF_FIELDS = (
    "db",
    "db_object_id",
    "db_object_symbol",
    "qualifier",
    "go_id",
    "db_reference",
    "evidence_code",
    "with_or_from",
    "go_aspect",
    "db_object_name",
    "db_object_synonym",
    "db_object_type",
    "taxon",
    "date",
    "assigned_by",
    "annotation_extension",
    "gene_product_form_id",
    "go_name",
    "go_namespace",
    "source_annotation_file",
    "source_ontology_file",
)
REGULATOR_ANNOTATION_FIELDS = (
    "regulator_id",
    "regulator_name",
    "regulator_gene_name",
    "gene_symbol",
    "db_object_id",
    "db_object_symbol",
    "go_id",
    "go_name",
    "go_namespace",
    "go_aspect",
    "qualifier",
    "evidence_code",
    "db_reference",
    "with_or_from",
    "assigned_by",
    "date",
    "source_route",
    "identity_source_id",
    "annotation_source_id",
    "ontology_source_id",
)
REGULATOR_COVERAGE_FIELDS = (
    "regulator_id",
    "regulator_name",
    "regulator_gene_name",
    "gene_symbol_count",
    "matched_annotation_count",
    "matched_go_term_count",
    "mapping_status",
    "identity_source_id",
)


def build_ecocyc_go_artifacts(
    root: PathLike | None = None,
    *,
    output_dir: PathLike | None = None,
    allow_missing_terms: bool = False,
    require_regulator_annotations: bool = True,
) -> dict[str, object]:
    """Build parsed EcoCyc GO annotations and regulator-to-GO join artifacts."""

    base = Path.cwd() if root is None else Path(root)
    annotation_source = _known_functional_source_by_role(
        "ecocyc_gene_product_go_annotation"
    )
    ontology_source = _known_functional_source_by_role("go_term_ontology")
    annotation_path = annotation_source.absolute_path(base)
    ontology_path = ontology_source.absolute_path(base)
    target_dir = (
        Path(output_dir)
        if output_dir is not None
        else base / gene_ontology_release_path(annotation_source.release, "processed")
    )

    require_file(annotation_path, annotation_source.source_id)
    require_file(ontology_path, ontology_source.source_id)

    go_terms = parse_go_basic_obo(ontology_path)
    annotation_rows = parse_gaf(annotation_path, annotation_source, ontology_source)
    missing_go_ids = sorted(
        {row["go_id"] for row in annotation_rows if row["go_id"] not in go_terms}
    )
    if missing_go_ids and not allow_missing_terms:
        preview = ", ".join(missing_go_ids[:10])
        raise ValueError(f"GO IDs absent from ontology: {preview}")

    enriched_annotations = [
        {
            **row,
            "go_name": go_terms.get(row["go_id"], {}).get("go_name", ""),
            "go_namespace": go_terms.get(row["go_id"], {}).get("go_namespace", ""),
        }
        for row in annotation_rows
    ]

    identity_sources = tuple(iter_regulator_identity_source_files(base))
    if not identity_sources:
        raise FileNotFoundError(
            "No regulator identity source found. Expected "
            "sources/databases/regulondb/13.0/network_interactions/NetworkRegulatorGene.tsv or "
            "sources/databases/regulondb/11.0/transcription_factors/TFSet.txt."
        )
    identities = load_regulator_identities(base, identity_sources)
    if not identities:
        raise ValueError("No regulator identities parsed from available sources")

    regulator_annotations, coverage_rows = _join_regulators_to_annotations(
        identities,
        enriched_annotations,
        annotation_source_id=annotation_source.source_id,
        ontology_source_id=ontology_source.source_id,
    )
    if require_regulator_annotations and not regulator_annotations:
        raise ValueError("No regulator GO annotations matched regulator gene symbols")

    target_dir.mkdir(parents=True, exist_ok=True)
    write_tsv(target_dir / "go_terms.tsv", GO_TERM_FIELDS, go_terms.values())
    write_tsv(
        target_dir / "ecocyc_go_gene_product_annotations.tsv",
        GAF_FIELDS,
        enriched_annotations,
    )
    write_tsv(
        target_dir / "regulator_go_annotations.tsv",
        REGULATOR_ANNOTATION_FIELDS,
        regulator_annotations,
    )
    write_tsv(
        target_dir / "regulator_go_coverage.tsv",
        REGULATOR_COVERAGE_FIELDS,
        coverage_rows,
    )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "created_at": utc_now_iso(),
        "sources": {
            "annotation": source_file_manifest(annotation_source, annotation_path),
            "ontology": source_file_manifest(ontology_source, ontology_path),
            "regulator_identity": [
                source_file_manifest(source, source.absolute_path(base))
                for source in identity_sources
            ],
        },
        "row_counts": {
            "go_terms": len(go_terms),
            "ecocyc_go_annotations": len(enriched_annotations),
            "regulator_identities": len(identities),
            "regulator_go_annotations": len(regulator_annotations),
            "regulator_go_coverage": len(coverage_rows),
        },
        "contracts": {
            "allow_missing_terms": allow_missing_terms,
            "require_regulator_annotations": require_regulator_annotations,
            "join_key": "case-insensitive regulator gene symbol to GAF DB Object Symbol",
            "regulator_membership": "binary source identity rows, not interaction counts",
        },
        "outputs": {
            "go_terms": str(target_dir / "go_terms.tsv"),
            "ecocyc_go_annotations": str(
                target_dir / "ecocyc_go_gene_product_annotations.tsv"
            ),
            "regulator_go_annotations": str(
                target_dir / "regulator_go_annotations.tsv"
            ),
            "regulator_go_coverage": str(target_dir / "regulator_go_coverage.tsv"),
        },
    }
    write_json(target_dir / "manifest.json", manifest)
    return manifest


def download_raw_sources(
    root: PathLike | None = None,
    *,
    method: str = "urllib",
    overwrite: bool = False,
) -> dict[str, object]:
    base = Path.cwd() if root is None else Path(root)
    if method not in {"urllib", "curl"}:
        raise ValueError(f"Unsupported download method: {method!r}")

    downloaded: list[dict[str, object]] = []
    raw_go_sources = _known_raw_go_source_files()
    for source in raw_go_sources:
        target = source.absolute_path(base)
        if target.exists() and not overwrite:
            downloaded.append(
                source_file_manifest(source, target, downloaded_now=False)
            )
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if method == "curl":
            _download_with_curl(source.url, target)
        else:
            _download_with_urllib(source.url, target)
        downloaded.append(source_file_manifest(source, target, downloaded_now=True))

    manifest = {
        "schema_version": f"{SCHEMA_VERSION}.raw_sources",
        "created_at": utc_now_iso(),
        "download_method": method,
        "sources": downloaded,
    }
    release = raw_go_sources[0].release
    write_json(
        base / gene_ontology_release_path(release, "raw_manifest.json"), manifest
    )
    return manifest


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download and build EcoCyc/GO functional annotation artifacts."
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Data repository root. Defaults to the current working directory.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    download = subparsers.add_parser("download", help="Download raw GO source files.")
    download.add_argument(
        "--download-method",
        choices=("urllib", "curl"),
        default="urllib",
        help="Downloader to use. urllib verifies TLS and curl uses the local CLI.",
    )
    download.add_argument("--overwrite", action="store_true")

    build = subparsers.add_parser("build", help="Build processed artifacts.")
    _add_build_args(build)

    run = subparsers.add_parser("run", help="Download raw files then build artifacts.")
    run.add_argument(
        "--download-method",
        choices=("urllib", "curl"),
        default="urllib",
        help="Downloader to use. urllib verifies TLS and curl uses the local CLI.",
    )
    run.add_argument("--overwrite", action="store_true")
    _add_build_args(run)

    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.root)
    if args.command == "download":
        manifest = download_raw_sources(
            root,
            method=args.download_method,
            overwrite=args.overwrite,
        )
    elif args.command == "build":
        manifest = build_ecocyc_go_artifacts(
            root,
            allow_missing_terms=args.allow_missing_go_terms,
            require_regulator_annotations=not args.allow_empty_regulator_annotations,
        )
    elif args.command == "run":
        download_raw_sources(
            root,
            method=args.download_method,
            overwrite=args.overwrite,
        )
        manifest = build_ecocyc_go_artifacts(
            root,
            allow_missing_terms=args.allow_missing_go_terms,
            require_regulator_annotations=not args.allow_empty_regulator_annotations,
        )
    else:  # pragma: no cover - argparse enforces command choices.
        raise AssertionError(f"Unexpected command: {args.command!r}")

    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


def _add_build_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--allow-missing-go-terms",
        action="store_true",
        help="Do not fail if a GAF GO ID is absent from go-basic.obo.",
    )
    parser.add_argument(
        "--allow-empty-regulator-annotations",
        action="store_true",
        help="Do not fail when no regulator gene symbols match EcoCyc GO rows.",
    )


def _known_functional_source_by_role(role: str) -> FunctionalAnnotationSourceFile:
    matches = tuple(
        source
        for source in known_functional_annotation_source_files()
        if source.role == role
    )
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one functional annotation source with role {role!r}; "
            f"found {len(matches)}"
        )
    return matches[0]


def _known_raw_go_source_files() -> tuple[FunctionalAnnotationSourceFile, ...]:
    return tuple(
        source
        for source in known_functional_annotation_source_files()
        if source.source == "gene_ontology"
    )


def _join_regulators_to_annotations(
    identities: Sequence[RegulatorIdentity],
    annotations: Sequence[dict[str, str]],
    *,
    annotation_source_id: str,
    ontology_source_id: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    annotations_by_symbol: dict[str, list[dict[str, str]]] = {}
    for annotation in annotations:
        symbol = annotation["db_object_symbol"].lower()
        annotations_by_symbol.setdefault(symbol, []).append(annotation)

    regulator_rows: list[dict[str, str]] = []
    coverage_rows: list[dict[str, str]] = []
    emitted: set[tuple[str, str, str, str, str]] = set()
    for identity in identities:
        matched_annotations: list[dict[str, str]] = []
        matched_go_ids: set[str] = set()
        for gene_symbol in identity.gene_symbols:
            for annotation in annotations_by_symbol.get(gene_symbol.lower(), []):
                key = (
                    identity.regulator_id,
                    gene_symbol.lower(),
                    annotation["go_id"],
                    annotation["evidence_code"],
                    annotation["db_reference"],
                )
                if key in emitted:
                    continue
                emitted.add(key)
                matched_annotations.append(annotation)
                matched_go_ids.add(annotation["go_id"])
                regulator_rows.append(
                    {
                        "regulator_id": identity.regulator_id,
                        "regulator_name": identity.regulator_name,
                        "regulator_gene_name": identity.regulator_gene_name,
                        "gene_symbol": gene_symbol,
                        "db_object_id": annotation["db_object_id"],
                        "db_object_symbol": annotation["db_object_symbol"],
                        "go_id": annotation["go_id"],
                        "go_name": annotation["go_name"],
                        "go_namespace": annotation["go_namespace"],
                        "go_aspect": annotation["go_aspect"],
                        "qualifier": annotation["qualifier"],
                        "evidence_code": annotation["evidence_code"],
                        "db_reference": annotation["db_reference"],
                        "with_or_from": annotation["with_or_from"],
                        "assigned_by": annotation["assigned_by"],
                        "date": annotation["date"],
                        "source_route": "regulondb_regulator_gene_to_ecocyc_go",
                        "identity_source_id": identity.source_id,
                        "annotation_source_id": annotation_source_id,
                        "ontology_source_id": ontology_source_id,
                    }
                )
        coverage_rows.append(
            {
                "regulator_id": identity.regulator_id,
                "regulator_name": identity.regulator_name,
                "regulator_gene_name": identity.regulator_gene_name,
                "gene_symbol_count": str(len(identity.gene_symbols)),
                "matched_annotation_count": str(len(matched_annotations)),
                "matched_go_term_count": str(len(matched_go_ids)),
                "mapping_status": _mapping_status(identity, matched_annotations),
                "identity_source_id": identity.source_id,
            }
        )
    return regulator_rows, coverage_rows


def _mapping_status(
    identity: RegulatorIdentity,
    matched_annotations: Sequence[dict[str, str]],
) -> str:
    if not identity.gene_symbols:
        return "missing_regulator_gene"
    if matched_annotations:
        return "matched"
    return "unmatched_gene_symbol"


def _download_with_urllib(url: str, target: Path) -> None:
    with tempfile.NamedTemporaryFile(
        dir=str(target.parent),
        prefix=f".{target.name}.",
        delete=False,
    ) as tmp:
        tmp_path = Path(tmp.name)
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                shutil.copyfileobj(response, tmp)
            tmp_path.replace(target)
            target.chmod(0o644)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise


def _download_with_curl(url: str, target: Path) -> None:
    with tempfile.NamedTemporaryFile(
        dir=str(target.parent),
        prefix=f".{target.name}.",
        delete=False,
    ) as tmp:
        tmp_path = Path(tmp.name)
    try:
        subprocess.run(
            [
                "curl",
                "--fail",
                "--location",
                "--silent",
                "--show-error",
                "--connect-timeout",
                "30",
                "--max-time",
                "600",
                "--proto",
                "=https",
                "--tlsv1.2",
                "--output",
                str(tmp_path),
                url,
            ],
            check=True,
        )
        tmp_path.replace(target)
        target.chmod(0o644)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
