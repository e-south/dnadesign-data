"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/motifs/cli.py

Provides explicit machine-readable commands for canonical motif-source exports.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from dnadesign_data.motifs.contracts import MotifExportError
from dnadesign_data.motifs.io import (
    write_json_create_only,
    write_motif_source_export,
)
from dnadesign_data.motifs.jaspar import build_jaspar_count_motif_export
from dnadesign_data.motifs.meme import build_meme_motif_export
from dnadesign_data.motifs.pool import (
    build_task_model_pool,
    load_task_model_pool_request,
)
from dnadesign_data.motifs.providers import list_motif_source_providers
from dnadesign_data.motifs.receipts import build_motif_export_receipt
from dnadesign_data.motifs.regulondb import build_regulondb_site_export


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export named TFBS sources through explicit versioned contracts."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    providers = subparsers.add_parser(
        "providers", help="List the bounded adapter capability catalog."
    )
    _add_output_arguments(providers)

    meme = subparsers.add_parser(
        "export-meme", help="Export one named MEME probability matrix."
    )
    meme.add_argument("source", type=Path)
    meme.add_argument("--motif-id", required=True)
    meme.add_argument("--source-motif-id", required=True)
    _add_source_identity_arguments(meme)
    meme.add_argument("--prior-weight", required=True, type=float)
    meme.add_argument("--out", required=True, type=Path)
    _add_output_arguments(meme)

    jaspar = subparsers.add_parser(
        "export-jaspar-counts", help="Export one named JASPAR count matrix."
    )
    jaspar.add_argument("source", type=Path)
    jaspar.add_argument("--motif-id", required=True)
    jaspar.add_argument("--source-motif-id", required=True)
    _add_source_identity_arguments(jaspar)
    jaspar.add_argument(
        "--background",
        required=True,
        help="Comma-separated A,C,G,T background probabilities.",
    )
    jaspar.add_argument("--out", required=True, type=Path)
    _add_output_arguments(jaspar)

    regulondb = subparsers.add_parser(
        "export-regulondb-sites",
        help="Export one regulator's TF-RISet rows as a typed site set.",
    )
    regulondb.add_argument("source", type=Path)
    regulondb.add_argument("--regulator-name", required=True)
    _add_source_identity_arguments(regulondb)
    regulondb.add_argument("--orientation", choices=("genomic_forward",), required=True)
    regulondb.add_argument("--out", required=True, type=Path)
    _add_output_arguments(regulondb)

    receipt = subparsers.add_parser(
        "receipt", help="Bind one model export to an immutable owner artifact."
    )
    receipt.add_argument("export_dir", type=Path)
    receipt.add_argument("--owner-revision", required=True)
    receipt.add_argument("--owner-repository-path", required=True, type=Path)
    receipt.add_argument("--data-root", required=True, type=Path)
    receipt.add_argument("--canonical-artifact-ref", required=True)
    receipt.add_argument("--out", required=True, type=Path)
    _add_output_arguments(receipt)

    pool = subparsers.add_parser(
        "build-pool", help="Build an exposure-bound model qualification inventory."
    )
    pool.add_argument("request", type=Path)
    pool.add_argument("--repository-root", required=True, type=Path)
    pool.add_argument("--out", required=True, type=Path)
    _add_output_arguments(pool)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "providers":
            providers = list_motif_source_providers()
            _write_payload(
                {
                    "schema_version": (
                        "dnadesign-data.motif-source-provider-catalog/v1"
                    ),
                    "provider_count": len(providers),
                    "providers": providers,
                },
                sys.stdout,
                args.indent,
            )
            return 0
        if args.command == "export-meme":
            export = build_meme_motif_export(
                args.source,
                motif_id=args.motif_id,
                source_motif_id=args.source_motif_id,
                source_descriptor_id=args.source_descriptor_id,
                prior_weight=args.prior_weight,
                data_root=args.data_root,
            )
            output = write_motif_source_export(export, args.out)
            _write_export_report(export, output, args.indent)
            return 0
        if args.command == "export-jaspar-counts":
            export = build_jaspar_count_motif_export(
                args.source,
                motif_id=args.motif_id,
                source_motif_id=args.source_motif_id,
                source_descriptor_id=args.source_descriptor_id,
                background=_parse_background_argument(args.background),
                data_root=args.data_root,
            )
            output = write_motif_source_export(export, args.out)
            _write_export_report(export, output, args.indent)
            return 0
        if args.command == "export-regulondb-sites":
            export = build_regulondb_site_export(
                args.source,
                regulator_name=args.regulator_name,
                source_descriptor_id=args.source_descriptor_id,
                orientation=args.orientation,
                data_root=args.data_root,
            )
            output = write_motif_source_export(export, args.out)
            _write_export_report(export, output, args.indent)
            return 0
        if args.command == "receipt":
            receipt = build_motif_export_receipt(
                args.export_dir,
                owner_revision=args.owner_revision,
                canonical_artifact_ref=args.canonical_artifact_ref,
                owner_repository_path=args.owner_repository_path,
                data_root=args.data_root,
            )
            output = write_json_create_only(receipt, args.out)
            _write_payload(
                {
                    "schema_version": receipt["schema"],
                    "report_kind": "motif_export_receipt_written",
                    "output_name": output.name,
                    "motif_id": receipt["motif_id"],
                    "model_digest": receipt["model_digest"],
                },
                sys.stdout,
                args.indent,
            )
            return 0
        if args.command == "build-pool":
            request = load_task_model_pool_request(args.request)
            pool = build_task_model_pool(request, repository_root=args.repository_root)
            output = write_json_create_only(pool, args.out)
            _write_payload(
                {
                    "schema_version": pool["schema_version"],
                    "report_kind": "motif_task_pool_written",
                    "output_name": output.name,
                    "pool_id": pool["pool_id"],
                    "admission_status": pool["admission_status"],
                    "seal_sha256": pool["seal_sha256"],
                },
                sys.stdout,
                args.indent,
            )
            return 0
    except MotifExportError as exc:
        if getattr(args, "json_errors", False):
            _write_payload(
                {
                    "schema_version": "dnadesign-data.motif-source-error/v1",
                    "report_kind": "motif_source_error",
                    "ok": False,
                    "error_type": exc.__class__.__name__,
                    "message": str(exc),
                },
                sys.stderr,
                getattr(args, "indent", 2),
            )
        else:
            sys.stderr.write(f"dnadesign-data-motifs: {exc}\n")
        return 2
    raise ValueError(f"unsupported command: {args.command!r}")


def _add_source_identity_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source-descriptor-id", required=True)
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="Optional mirror root; descriptor path, release, and rights remain catalog-owned.",
    )


def _add_output_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--indent", type=int, default=2)
    parser.add_argument("--json-errors", action="store_true")


def _parse_background_argument(value: str) -> list[float]:
    parts = value.split(",")
    if len(parts) != 4:
        raise MotifExportError("background must contain comma-separated A,C,G,T values")
    try:
        return [float(part) for part in parts]
    except ValueError as exc:
        raise MotifExportError("background contains a nonnumeric value") from exc


def _write_export_report(
    export: dict[str, dict[str, object]], output: Path, indent: int
) -> None:
    manifest = export["manifest"]
    _write_payload(
        {
            "schema_version": manifest["schema_version"],
            "report_kind": "motif_source_export_written",
            "output_name": output.name,
            "output_schema": manifest["output_schema"],
            "artifact_sha256": manifest["artifact_sha256"],
        },
        sys.stdout,
        indent,
    )


def _write_payload(payload: object, stream: TextIO, indent_value: int) -> None:
    indent = None if indent_value == 0 else indent_value
    json.dump(payload, stream, indent=indent, sort_keys=True)
    stream.write("\n")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
