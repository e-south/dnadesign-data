"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/motifs/io.py

Publishes deterministic motif-source export bundles with create-only semantics.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from dnadesign_data.motifs.contracts import (
    MotifExportError,
    canonical_json_bytes,
    read_source_bytes,
    reject_symbolic_link_ancestors,
)

MAX_JSON_BYTES = 16 * 1024 * 1024


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise MotifExportError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _load_json_object(path: Path) -> tuple[dict[str, Any], bytes]:
    _source, raw = read_source_bytes(
        path, max_bytes=MAX_JSON_BYTES, label="export file"
    )
    try:
        value = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
    except MotifExportError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise MotifExportError(f"export file {path.name!r} is invalid") from exc
    if not isinstance(value, dict):
        raise MotifExportError(f"export file {path.name!r} must contain one object")
    if raw != canonical_json_bytes(value):
        raise MotifExportError(
            f"export file {path.name!r} does not contain canonical JSON bytes"
        )
    return value, raw


def write_motif_source_export(
    export: dict[str, dict[str, Any]], output_dir: str | Path
) -> Path:
    """Atomically publish artifact.json and manifest.json to a new directory."""

    output = Path(output_dir)
    reject_symbolic_link_ancestors(output)
    if output.exists() or output.is_symlink():
        raise MotifExportError(f"output directory {output.name!r} already exists")
    parent = output.parent
    parent.mkdir(parents=True, exist_ok=True)
    reject_symbolic_link_ancestors(output)
    with tempfile.TemporaryDirectory(
        prefix=f".{output.name}.", dir=parent
    ) as temporary:
        staging = Path(temporary)
        (staging / "artifact.json").write_bytes(
            canonical_json_bytes(export["artifact"])
        )
        (staging / "manifest.json").write_bytes(
            canonical_json_bytes(export["manifest"])
        )
        try:
            staging.replace(output)
        except OSError as exc:
            raise MotifExportError(
                f"unable to publish output directory {output.name!r}"
            ) from exc
    return output


def load_motif_source_export(input_dir: str | Path) -> dict[str, dict[str, Any]]:
    """Load one export bundle without following symbolic links."""

    result, _artifact_bytes = load_motif_source_export_for_receipt(input_dir)
    return result


def load_motif_source_export_for_receipt(
    input_dir: str | Path,
) -> tuple[dict[str, dict[str, Any]], bytes]:
    """Load one canonical export and retain its admitted artifact bytes."""

    source = Path(input_dir)
    reject_symbolic_link_ancestors(source)
    if source.is_symlink() or not source.is_dir():
        raise MotifExportError(f"export directory {source.name!r} is unavailable")
    result: dict[str, dict[str, Any]] = {}
    artifact_bytes = b""
    for key, filename in (("artifact", "artifact.json"), ("manifest", "manifest.json")):
        path = source / filename
        if path.is_symlink() or not path.is_file():
            raise MotifExportError(f"export file {filename!r} is unavailable")
        result[key], raw = _load_json_object(path)
        if key == "artifact":
            artifact_bytes = raw
    return result, artifact_bytes


def write_json_create_only(value: object, output_path: str | Path) -> Path:
    """Write one canonical JSON file without replacing an existing path."""

    output = Path(output_path)
    reject_symbolic_link_ancestors(output)
    if output.exists() or output.is_symlink():
        raise MotifExportError(f"output file {output.name!r} already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    reject_symbolic_link_ancestors(output)
    try:
        with output.open("xb") as handle:
            handle.write(canonical_json_bytes(value))
    except OSError as exc:
        raise MotifExportError(
            f"unable to publish output file {output.name!r}"
        ) from exc
    return output
