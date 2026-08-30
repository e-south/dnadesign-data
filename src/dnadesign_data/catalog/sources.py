"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/catalog/sources.py

Builds public source-catalog payloads for CLI and downstream tools.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from dnadesign_data.catalog.functional_annotations import (
    known_functional_annotation_service_sources,
    known_functional_annotation_source_files,
    known_regulator_identity_source_files,
)
from dnadesign_data.catalog.regulatory_parts import (
    known_motif_source_files,
    known_promoter_association_source_files,
    known_promoter_source_files,
)
from dnadesign_data.core.layout import default_data_root

PathLike = str | Path

SCHEMA_VERSION = "dnadesign_data.source_catalog.v1"
SOURCE_KIND_CHOICES = (
    "all",
    "promoter",
    "promoter-association",
    "motif-source",
    "functional-annotation",
    "regulator-identity",
    "functional-service",
)


class SourceCatalogError(ValueError):
    """Raised when a source-catalog contract cannot be satisfied."""


@runtime_checkable
class FileSourceDescriptor(Protocol):
    source_id: str
    file_format: str
    table: str

    def absolute_path(self, root: PathLike | None = None) -> Path: ...

    def as_dict(self) -> dict[str, object]: ...


@runtime_checkable
class ServiceSourceDescriptor(Protocol):
    source_id: str
    auth_required: bool

    def as_dict(self) -> dict[str, object]: ...


def build_source_catalog_payload(
    root: PathLike | None = None,
    *,
    kind: str = "all",
    include_missing: bool = False,
) -> dict[str, object]:
    """Build the machine-readable source descriptor catalog."""

    base = _resolve_root(root)
    records = tuple(
        iter_source_records(base, kind=kind, include_missing=include_missing)
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "root": str(base),
        "kind": kind,
        "include_missing": include_missing,
        "record_count": len(records),
        "available_count": sum(1 for record in records if record["available"]),
        "service_available_count": sum(
            1
            for record in records
            if record["available"] and record["kind"] == "functional_service"
        ),
        "local_file_available_count": sum(
            1
            for record in records
            if record["available"] and record["kind"] != "functional_service"
        ),
        "missing_count": sum(1 for record in records if not record["available"]),
        "records": list(records),
    }


def source_catalog_schema_payload() -> dict[str, object]:
    """Return the stable JSON contract for source-catalog CLI consumers."""

    return {
        "schema_version": SCHEMA_VERSION,
        "report_kind": "source_catalog_schema",
        "source_kind_choices": list(SOURCE_KIND_CHOICES),
        "commands": {
            "list": {
                "exit_codes": {"0": "payload emitted", "2": "catalog contract error"},
                "record_policy": "available records by default; --include-missing emits known unavailable descriptors",
            },
            "resolve": {
                "exit_codes": {
                    "0": "source resolved",
                    "2": "unknown or unavailable source",
                },
                "record_policy": "known local-file sources must exist unless --allow-missing is explicit",
            },
            "check": {
                "exit_codes": {
                    "0": "readiness contract satisfied",
                    "1": "readiness contract failed",
                    "2": "catalog contract error",
                },
                "record_policy": "always evaluates known descriptors; --summary-only suppresses record payloads",
            },
            "schema": {
                "exit_codes": {"0": "schema payload emitted"},
                "record_policy": "no repository files are inspected",
            },
        },
        "payload_fields": {
            "common_record_fields": [
                "kind",
                "available",
                "source_id",
                "source",
                "release",
                "stratum",
                "role",
                "parser_hint",
            ],
            "local_file_record_fields": [
                "absolute_path",
                "path",
                "table",
                "file_format",
            ],
            "motif_source_record_fields": [
                "source_kind",
                "output_capability",
                "redistribution_status",
                "retrieval_url",
                "rights_url",
                "retrieved_on",
            ],
            "service_record_fields": [
                "availability",
                "base_url",
                "response_format",
                "auth_required",
            ],
            "readiness_metrics": [
                "known_count",
                "known_local_file_count",
                "available_count",
                "local_file_available_count",
                "missing_known_source_ids",
                "missing_required_source_ids",
                "unknown_required_source_ids",
            ],
        },
        "availability_semantics": {
            "available_count": "all currently usable records, including authenticated service descriptors",
            "local_file_available_count": "materialized local files only",
            "functional_service": "live service descriptor; may require runtime credentials",
        },
    }


def resolve_source_record(
    source_id: str,
    root: PathLike | None = None,
    *,
    allow_missing: bool = False,
) -> dict[str, object]:
    """Resolve one source descriptor by source ID.

    Missing local files are hard errors unless ``allow_missing`` is explicit.
    """

    if not source_id.strip():
        raise SourceCatalogError("source_id must be a non-empty string")

    base = _resolve_root(root)
    matches = [
        record
        for record in iter_source_records(base, kind="all", include_missing=True)
        if record["source_id"] == source_id
    ]
    if len(matches) > 1:
        raise SourceCatalogError(f"Duplicate source_id in catalog: {source_id!r}")
    if not matches:
        raise SourceCatalogError(f"Unknown source_id: {source_id!r}")

    record = matches[0]
    if not allow_missing and not record["available"]:
        raise SourceCatalogError(
            f"Source {source_id!r} is known but unavailable at "
            f"{record.get('absolute_path', '<no path>')}"
        )
    return record


def check_source_catalog_payload(
    root: PathLike | None = None,
    *,
    kind: str = "all",
    required_source_ids: Sequence[str] = (),
    require_all_known: bool = False,
    include_records: bool = True,
) -> dict[str, object]:
    """Build a fail-fast readiness report for source availability."""

    base = _resolve_root(root)
    records = tuple(iter_source_records(base, kind=kind, include_missing=True))
    file_records = tuple(
        record for record in records if record["kind"] != "functional_service"
    )
    known_ids = {str(record["source_id"]) for record in records}
    available_ids = {
        str(record["source_id"]) for record in records if record["available"]
    }
    available_file_ids = {
        str(record["source_id"]) for record in file_records if record["available"]
    }
    missing_known_ids = [
        str(record["source_id"])
        for record in records
        if not record["available"] and record["kind"] != "functional_service"
    ]
    cleaned_required_ids = _normalize_required_source_ids(required_source_ids)
    unknown_required_ids = [
        source_id for source_id in cleaned_required_ids if source_id not in known_ids
    ]
    missing_required_ids = [
        source_id
        for source_id in cleaned_required_ids
        if source_id in known_ids and source_id not in available_file_ids
    ]
    has_available_source = bool(available_file_ids) or (
        kind == "functional-service" and bool(available_ids)
    )
    ok = (
        not unknown_required_ids
        and not missing_required_ids
        and (not require_all_known or not missing_known_ids)
        and (bool(cleaned_required_ids) or require_all_known or has_available_source)
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "report_kind": "source_catalog_check",
        "root": str(base),
        "kind": kind,
        "ok": ok,
        "require_all_known": require_all_known,
        "required_source_ids": cleaned_required_ids,
        "known_count": len(records),
        "known_local_file_count": len(file_records),
        "available_count": len(available_ids),
        "local_file_available_count": len(available_file_ids),
        "missing_known_source_ids": missing_known_ids,
        "missing_required_source_ids": missing_required_ids,
        "unknown_required_source_ids": unknown_required_ids,
        "records_included": include_records,
        "records": list(records) if include_records else [],
    }


def iter_source_records(
    root: PathLike | None = None,
    *,
    kind: str,
    include_missing: bool,
) -> Iterable[dict[str, object]]:
    """Iterate source descriptor records for one catalog kind."""

    _validate_kind(kind)
    base = _resolve_root(root)
    records = tuple(_iter_source_records_unchecked(base, kind, include_missing))
    _require_unique_source_ids(records)
    yield from records


def _iter_source_records_unchecked(
    base: Path,
    kind: str,
    include_missing: bool,
) -> Iterable[dict[str, object]]:
    if kind in {"all", "promoter"}:
        yield from _file_source_records(
            known_promoter_source_files(),
            base,
            kind="promoter",
            include_missing=include_missing,
        )
    if kind in {"all", "promoter-association"}:
        yield from _file_source_records(
            known_promoter_association_source_files(),
            base,
            kind="promoter_association",
            include_missing=include_missing,
        )
    if kind in {"all", "motif-source"}:
        yield from _file_source_records(
            known_motif_source_files(),
            base,
            kind="motif_source",
            include_missing=include_missing,
        )
    if kind in {"all", "functional-annotation"}:
        yield from _file_source_records(
            known_functional_annotation_source_files(),
            base,
            kind="functional_annotation",
            include_missing=include_missing,
        )
    if kind in {"all", "regulator-identity"}:
        yield from _file_source_records(
            known_regulator_identity_source_files(),
            base,
            kind="regulator_identity",
            include_missing=include_missing,
        )
    if kind in {"all", "functional-service"}:
        for source in known_functional_annotation_service_sources():
            yield _service_source_record(source)


def _file_source_records(
    sources: Iterable[FileSourceDescriptor],
    root: Path,
    *,
    kind: str,
    include_missing: bool,
) -> Iterable[dict[str, object]]:
    for source in sources:
        record = _source_file_record(
            source,
            root,
            kind=kind,
            include_missing=include_missing,
        )
        if record is not None:
            yield record


def _source_file_record(
    source: FileSourceDescriptor,
    root: Path,
    *,
    kind: str,
    include_missing: bool,
) -> dict[str, object] | None:
    if not isinstance(source, FileSourceDescriptor):
        raise TypeError(f"source descriptor lacks file-source protocol: {source!r}")
    path = source.absolute_path(root)
    available = _is_available(source, path)
    if not available and not include_missing:
        return None
    return {
        "kind": kind,
        "available": available,
        "absolute_path": str(path),
        **_descriptor_dict(source),
    }


def _service_source_record(source: ServiceSourceDescriptor) -> dict[str, object]:
    if not isinstance(source, ServiceSourceDescriptor):
        raise TypeError(f"source descriptor lacks service-source protocol: {source!r}")
    return {
        "kind": "functional_service",
        "available": True,
        "availability": "live_service_requires_runtime_auth"
        if source.auth_required
        else "live_service",
        **_descriptor_dict(source),
    }


def _resolve_root(root: PathLike | None) -> Path:
    resolved = default_data_root() if root is None else Path(root).resolve()
    if not resolved.exists():
        raise SourceCatalogError(f"Data repository root does not exist: {resolved}")
    if not resolved.is_dir():
        raise SourceCatalogError(f"Data repository root is not a directory: {resolved}")
    return resolved


def _validate_kind(kind: str) -> None:
    if kind not in SOURCE_KIND_CHOICES:
        raise SourceCatalogError(f"Unsupported source kind: {kind!r}")


def _normalize_required_source_ids(source_ids: Sequence[str]) -> list[str]:
    normalized: list[str] = []
    for source_id in source_ids:
        cleaned = source_id.strip()
        if not cleaned:
            raise SourceCatalogError("required source IDs must be non-empty strings")
        normalized.append(cleaned)
    duplicates = sorted(
        {source_id for source_id in normalized if normalized.count(source_id) > 1}
    )
    if duplicates:
        raise SourceCatalogError(
            "duplicate required source IDs: " + ", ".join(duplicates)
        )
    return normalized


def _require_unique_source_ids(records: Sequence[dict[str, object]]) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for record in records:
        source_id = str(record.get("source_id", "")).strip()
        if not source_id:
            raise SourceCatalogError("source records must include non-empty source_id")
        if source_id in seen:
            duplicates.add(source_id)
        seen.add(source_id)
    if duplicates:
        raise SourceCatalogError(
            "duplicate source IDs in catalog: " + ", ".join(sorted(duplicates))
        )


def _is_available(source: FileSourceDescriptor, path: Path) -> bool:
    if source.file_format in {"csv_glob", "meme_report_glob"}:
        return path.exists() and any(path.glob(source.table))
    return path.exists()


def _descriptor_dict(source: object) -> dict[str, object]:
    if hasattr(source, "as_dict"):
        result = source.as_dict()
        if not isinstance(result, dict):
            raise TypeError(f"as_dict() did not return a dict: {source!r}")
        return result
    if is_dataclass(source):
        return asdict(source)
    raise TypeError(f"Unsupported source descriptor: {source!r}")
