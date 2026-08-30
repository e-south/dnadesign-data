"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/functional/table_io.py

Provides shared table, manifest, and file I/O helpers for functional adapters.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path


def write_tsv(
    path: Path,
    fieldnames: Sequence[str],
    rows: Iterable[Mapping[str, object]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            delimiter="\t",
            lineterminator="\n",
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    path.chmod(0o644)


def source_file_manifest(
    source: object,
    path: Path,
    *,
    downloaded_now: bool | None = None,
) -> dict[str, object]:
    if not hasattr(source, "as_dict"):
        raise TypeError(f"source descriptor lacks as_dict(): {source!r}")
    payload = source.as_dict()
    if not isinstance(payload, dict):
        raise TypeError(f"source descriptor as_dict() returned non-dict: {source!r}")
    manifest = {
        **payload,
        "absolute_path": str(path),
        "sha256": sha256(path),
        "byte_count": path.stat().st_size,
    }
    if downloaded_now is not None:
        manifest["downloaded_now"] = downloaded_now
    return manifest


def file_manifest(path: Path) -> dict[str, object]:
    return {
        "path": str(path),
        "sha256": sha256(path),
        "byte_count": path.stat().st_size,
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_file(path: Path, source_id: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing required source {source_id}: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"Required source is not a file {source_id}: {path}")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
