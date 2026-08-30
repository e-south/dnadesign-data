"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/devtools/generated_motif_check.py

Validates the closed, bounded generated motif-model repository inventory.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path, PurePosixPath

from dnadesign_data.motifs.contracts import MotifExportError
from dnadesign_data.motifs.pool_validation import (
    validate_task_model_pool_correspondence,
    validate_task_model_pool_inventory_shape,
    validate_task_model_pool_local_bundles,
    validate_task_model_pool_request_shape,
)

GENERATED_MOTIF_PREFIX = PurePosixPath("generated/motif_models")
MAX_GENERATED_MOTIF_FILE_BYTES = 4 * 1024 * 1024
MAX_GENERATED_MOTIF_ENTRIES = 10_000
BUNDLE_MEMBERS = frozenset({"artifact.json", "manifest.json", "receipt.json"})
POOL_FILE = re.compile(r"[a-z0-9][a-z0-9-]*\.(request|inventory)\.json")


class DuplicateGeneratedKeyError(ValueError):
    """Raised when generated motif JSON repeats a key."""


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    payload: dict[str, object] = {}
    for key, value in pairs:
        if key in payload:
            raise DuplicateGeneratedKeyError(f"duplicate key {key!r}")
        payload[key] = value
    return payload


def _read_bounded_regular_file(path: Path, *, label: str) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ValueError(f"{label}: cannot open bounded regular file: {exc}") from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError(f"{label}: generated motif members must be regular files")
        if metadata.st_size > MAX_GENERATED_MOTIF_FILE_BYTES:
            raise ValueError(f"{label}: generated motif member exceeds its byte bound")
        chunks: list[bytes] = []
        remaining = metadata.st_size + 1
        while remaining:
            chunk = os.read(descriptor, min(remaining, 64 * 1024))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        if len(payload) != metadata.st_size:
            raise ValueError(f"{label}: generated motif member changed while reading")
        return payload
    finally:
        os.close(descriptor)


def validate_generated_motif_inventory(base: Path) -> list[str]:
    """Reject files outside the closed generated-motif bundle and pool shapes."""

    root = base.resolve() / GENERATED_MOTIF_PREFIX
    if root.is_symlink():
        return ["generated/motif_models: symbolic links are forbidden"]
    if not root.exists():
        return []
    errors: list[str] = []
    bundle_members: dict[PurePosixPath, set[str]] = {}
    bundle_payloads: dict[str, dict[str, bytes]] = {}
    pool_payloads: dict[str, dict[str, dict[str, object]]] = {}
    pending = [root]
    entry_count = 0
    while pending:
        directory = pending.pop()
        try:
            entries = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as exc:
            relative = directory.relative_to(base).as_posix()
            errors.append(
                f"{relative}: cannot inspect generated motif directory: {exc}"
            )
            continue
        entry_count += len(entries)
        if entry_count > MAX_GENERATED_MOTIF_ENTRIES:
            errors.append(
                "generated/motif_models: generated motif inventory exceeds its entry bound"
            )
            return errors
        for entry in entries:
            path = Path(entry.path)
            relative = PurePosixPath(path.relative_to(base).as_posix())
            tail = relative.parts[len(GENERATED_MOTIF_PREFIX.parts) :]
            if entry.is_symlink():
                errors.append(f"{relative.as_posix()}: symbolic links are forbidden")
                continue
            if entry.is_dir(follow_symlinks=False):
                allowed_directory = len(tail) == 1 or (
                    len(tail) == 2 and tail[0] != "pools"
                )
                if not allowed_directory:
                    errors.append(
                        f"{relative.as_posix()}: not an allowed generated motif path"
                    )
                    continue
                pending.append(path)
                continue
            if not entry.is_file(follow_symlinks=False):
                errors.append(
                    f"{relative.as_posix()}: generated motif entries must be regular files"
                )
                continue
            try:
                raw = _read_bounded_regular_file(path, label=relative.as_posix())
            except ValueError as exc:
                errors.append(str(exc))
                continue
            if len(tail) == 3 and tail[0] != "pools" and tail[2] in BUNDLE_MEMBERS:
                bundle = PurePosixPath(*tail[:2])
                bundle_members.setdefault(bundle, set()).add(tail[2])
                full_bundle = (GENERATED_MOTIF_PREFIX / bundle).as_posix()
                bundle_payloads.setdefault(full_bundle, {})[tail[2]] = raw
                continue
            if len(tail) == 2 and tail[0] == "pools":
                match = POOL_FILE.fullmatch(tail[1])
                if match is None:
                    errors.append(
                        f"{relative.as_posix()}: not an allowed generated motif path"
                    )
                    continue
                kind = match.group(1)
                try:
                    payload = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
                except (
                    UnicodeError,
                    json.JSONDecodeError,
                    DuplicateGeneratedKeyError,
                    RecursionError,
                ) as exc:
                    errors.append(f"{relative.as_posix()}: invalid pool JSON: {exc}")
                    continue
                if not isinstance(payload, dict):
                    errors.append(
                        f"{relative.as_posix()}: pool file must contain one object"
                    )
                    continue
                canonical = (
                    json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
                ).encode()
                if raw != canonical:
                    errors.append(
                        f"{relative.as_posix()}: pool file must use canonical JSON bytes"
                    )
                    continue
                try:
                    if kind == "request":
                        validate_task_model_pool_request_shape(payload)
                    else:
                        validate_task_model_pool_inventory_shape(payload)
                except MotifExportError as exc:
                    errors.append(f"{relative.as_posix()}: {exc}")
                    continue
                stem = tail[1].removesuffix(f".{kind}.json")
                pool_payloads.setdefault(stem, {})[kind] = payload
                continue
            errors.append(f"{relative.as_posix()}: not an allowed generated motif path")
    for bundle, members in sorted(bundle_members.items()):
        if not {"artifact.json", "manifest.json"} <= members:
            errors.append(
                "generated/motif_models/"
                f"{bundle.as_posix()}: motif bundle lacks artifact.json or manifest.json"
            )
    for stem, payloads in sorted(pool_payloads.items()):
        if set(payloads) != {"request", "inventory"}:
            errors.append(
                f"generated/motif_models/pools/{stem}: pool requires one request and one inventory"
            )
            continue
        try:
            validate_task_model_pool_correspondence(
                payloads["request"], payloads["inventory"]
            )
            validate_task_model_pool_local_bundles(
                payloads["request"], payloads["inventory"], bundle_payloads
            )
        except MotifExportError as exc:
            errors.append(f"generated/motif_models/pools/{stem}: {exc}")
    return errors
