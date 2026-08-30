"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/catalog/cli.py

Provides a machine-readable source-catalog CLI for downstream tooling.

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

from dnadesign_data.catalog.sources import (
    SOURCE_KIND_CHOICES,
    SourceCatalogError,
    build_source_catalog_payload,
    check_source_catalog_payload,
    resolve_source_record,
    source_catalog_schema_payload,
)

FORMAT_CHOICES = ("json",)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect dnadesign-data public source descriptors."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser(
        "list",
        help="List source descriptors as JSON for downstream tooling.",
    )
    _add_root_argument(list_parser)
    list_parser.add_argument(
        "--kind",
        choices=SOURCE_KIND_CHOICES,
        default="all",
        help="Descriptor kind to list.",
    )
    list_parser.add_argument(
        "--include-missing",
        action="store_true",
        help="Include known descriptors even when the backing local file is absent.",
    )
    _add_output_arguments(list_parser)
    resolve_parser = subparsers.add_parser(
        "resolve",
        help="Resolve one source descriptor by source_id as JSON.",
    )
    _add_root_argument(resolve_parser)
    resolve_parser.add_argument("source_id", help="Source ID to resolve.")
    resolve_parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Return known descriptors even when the backing local file is absent.",
    )
    _add_output_arguments(resolve_parser)

    check_parser = subparsers.add_parser(
        "check",
        help="Check source availability and exit nonzero when contracts fail.",
    )
    _add_root_argument(check_parser)
    check_parser.add_argument(
        "--kind",
        choices=SOURCE_KIND_CHOICES,
        default="all",
        help="Descriptor kind to check.",
    )
    check_parser.add_argument(
        "--require-source",
        action="append",
        default=[],
        metavar="SOURCE_ID",
        help="Source ID that must be known and locally available. Repeatable.",
    )
    check_parser.add_argument(
        "--require-all-known",
        action="store_true",
        help="Require every known local-file descriptor for the selected kind.",
    )
    check_parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Omit descriptor records from the readiness JSON payload.",
    )
    _add_output_arguments(check_parser)

    schema_parser = subparsers.add_parser(
        "schema",
        help="Emit the source-catalog JSON contract.",
    )
    _add_output_arguments(schema_parser)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "list":
            payload = build_source_catalog_payload(
                Path(args.root),
                kind=args.kind,
                include_missing=args.include_missing,
            )
            _write_payload(payload, args)
            return 0
        if args.command == "resolve":
            payload = resolve_source_record(
                args.source_id,
                Path(args.root),
                allow_missing=args.allow_missing,
            )
            _write_payload(payload, args)
            return 0
        if args.command == "check":
            payload = check_source_catalog_payload(
                Path(args.root),
                kind=args.kind,
                required_source_ids=args.require_source,
                require_all_known=args.require_all_known,
                include_records=not args.summary_only,
            )
            _write_payload(payload, args)
            return 0 if payload["ok"] else 1
        if args.command == "schema":
            _write_payload(source_catalog_schema_payload(), args)
            return 0
    except SourceCatalogError as exc:
        if getattr(args, "json_errors", False):
            _write_json(
                {
                    "schema_version": "dnadesign_data.source_catalog.v1",
                    "report_kind": "source_catalog_error",
                    "ok": False,
                    "error_type": exc.__class__.__name__,
                    "message": str(exc),
                },
                sys.stderr,
                getattr(args, "indent", 2),
            )
        else:
            sys.stderr.write(f"dnadesign-data-sources: {exc}\n")
        return 2
    raise ValueError(f"Unsupported command: {args.command!r}")


def _add_root_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--root",
        default=".",
        help="Data repository root. Defaults to the current working directory.",
    )


def _add_output_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--format",
        choices=FORMAT_CHOICES,
        default="json",
        help="Output format. JSON is the stable machine-readable contract.",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation. Use 0 for compact output.",
    )
    parser.add_argument(
        "--json-errors",
        action="store_true",
        help="Emit contract errors as JSON to stderr.",
    )


def _write_payload(payload: dict[str, object], args: argparse.Namespace) -> None:
    if args.format != "json":
        raise ValueError(f"Unsupported output format: {args.format!r}")
    _write_json(payload, sys.stdout, args.indent)


def _write_json(
    payload: dict[str, object],
    stream: TextIO,
    indent_value: int,
) -> None:
    indent = None if indent_value == 0 else indent_value
    json.dump(payload, stream, indent=indent, sort_keys=True)
    stream.write("\n")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
