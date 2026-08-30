"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/devtools/public_tree_check.py

Validates the complete public data tree before publication or tagging.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import zipfile
from collections.abc import Iterator, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from dnadesign_data.catalog.regulatory_parts import known_motif_source_files
from dnadesign_data.devtools.generated_motif_check import (
    validate_generated_motif_inventory,
)
from dnadesign_data.motifs.contracts import MotifExportError
from dnadesign_data.motifs.receipt_validation import revalidate_motif_export_receipt
from dnadesign_data.motifs.receipts import validate_motif_export_source_replay

ROOT = Path(__file__).resolve().parents[3]
INVENTORY_PATH = PurePosixPath("PUBLIC_DATA_INVENTORY.json")
INVENTORY_SCHEMA = "dnadesign-data.public-data-inventory/v1"
RIGHTS_SCHEMA = "dnadesign-data.database-rights/v1"
_DATA_PREFIXES = (PurePosixPath("sources"), PurePosixPath("generated/motif_models"))
_OFFICE_SUFFIXES = {".docx", ".xlsx", ".pptx"}
_MACHINE_PATH = re.compile(
    rb"(?:file:/+)?/Users/[^/\x00\s<]+/|[A-Za-z]:[\\/]+Users[\\/]+[^\\/\x00\s<]+[\\/]"
)
_MAX_DATA_FILES = 10_000
_MAX_DATA_FILE_BYTES = 64 * 1024 * 1024
_MAX_OFFICE_MEMBERS = 10_000
_MAX_OFFICE_MEMBER_BYTES = 16 * 1024 * 1024
_IGNORED_WALK_NAMES = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
}


class PublicTreeError(ValueError):
    """Raised when the public tree cannot be represented safely."""


def _canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_regular(path: Path, *, limit: int, label: str) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise PublicTreeError(
            f"{label}: cannot open bounded regular file: {exc}"
        ) from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise PublicTreeError(f"{label}: public tree members must be regular files")
        if metadata.st_size > limit:
            raise PublicTreeError(f"{label}: public tree member exceeds its byte bound")
        chunks: list[bytes] = []
        remaining = metadata.st_size + 1
        while remaining:
            chunk = os.read(descriptor, min(remaining, 64 * 1024))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        if len(raw) != metadata.st_size:
            raise PublicTreeError(f"{label}: public tree member changed while reading")
        return raw
    finally:
        os.close(descriptor)


def _iter_files(
    root: Path, start: PurePosixPath
) -> Iterator[tuple[PurePosixPath, bytes]]:
    target = root.joinpath(*start.parts)
    if not target.exists():
        return
    if target.is_symlink():
        raise PublicTreeError(f"{start.as_posix()}: symbolic links are forbidden")
    pending = [target]
    seen = 0
    while pending:
        directory = pending.pop()
        for entry in sorted(os.scandir(directory), key=lambda item: item.name):
            seen += 1
            if seen > _MAX_DATA_FILES:
                raise PublicTreeError(
                    f"{start.as_posix()}: public data tree exceeds its entry bound"
                )
            path = Path(entry.path)
            relative = PurePosixPath(path.relative_to(root).as_posix())
            if entry.is_symlink():
                raise PublicTreeError(
                    f"{relative.as_posix()}: symbolic links are forbidden"
                )
            if entry.is_dir(follow_symlinks=False):
                pending.append(path)
                continue
            if not entry.is_file(follow_symlinks=False):
                raise PublicTreeError(
                    f"{relative.as_posix()}: public tree entries must be regular files"
                )
            yield (
                relative,
                _read_regular(
                    path,
                    limit=_MAX_DATA_FILE_BYTES,
                    label=relative.as_posix(),
                ),
            )


def _rights_payload(root: Path, rights_ref: PurePosixPath) -> dict[str, Any]:
    path = root.joinpath(*rights_ref.parts)
    try:
        raw = _read_regular(path, limit=64 * 1024, label=rights_ref.as_posix())
        payload = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError, PublicTreeError) as exc:
        raise PublicTreeError(
            f"{rights_ref.as_posix()}: invalid rights metadata: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise PublicTreeError(
            f"{rights_ref.as_posix()}: rights metadata must be an object"
        )
    return payload


def _descriptor_rights() -> dict[str, PurePosixPath]:
    result: dict[str, PurePosixPath] = {}
    for descriptor in known_motif_source_files():
        path = PurePosixPath(descriptor.path)
        if len(path.parts) >= 4 and path.parts[:2] == ("sources", "databases"):
            result[descriptor.source_id] = PurePosixPath(*path.parts[:4], "rights.json")
    return result


def _entry_metadata(
    root: Path,
    relative: PurePosixPath,
    *,
    descriptor_rights: dict[str, PurePosixPath],
) -> tuple[str, str | None, str]:
    parts = relative.parts
    if len(parts) >= 4 and parts[:2] == ("sources", "databases"):
        rights_ref = PurePosixPath(*parts[:4], "rights.json")
        rights = _rights_payload(root, rights_ref)
        return (
            "database_source",
            rights_ref.as_posix(),
            str(rights.get("redistribution_status", "unclassified")),
        )
    if parts[:2] == ("sources", "motif-development"):
        return "project_metadata", None, "project_metadata"
    if parts[:3] == ("generated", "motif_models", "pools"):
        return "project_generated", None, "project_generated"
    if len(parts) == 5 and parts[:2] == ("generated", "motif_models"):
        bundle = root.joinpath(*parts[:4])
        if relative.name == "receipt.json":
            receipt = json.loads((bundle / "receipt.json").read_bytes())
            descriptor_id = (
                receipt.get("source_descriptor_id")
                if isinstance(receipt, dict)
                else None
            )
            status = (
                receipt.get("redistribution_status")
                if isinstance(receipt, dict)
                else None
            )
            kind = "model_receipt"
        else:
            manifest = json.loads((bundle / "manifest.json").read_bytes())
            source = manifest.get("source") if isinstance(manifest, dict) else None
            descriptor_id = (
                source.get("descriptor_id") if isinstance(source, dict) else None
            )
            status = (
                source.get("redistribution_status")
                if isinstance(source, dict)
                else None
            )
            kind = (
                "model_artifact"
                if relative.name == "artifact.json"
                else "model_manifest"
            )
        rights_ref = descriptor_rights.get(str(descriptor_id))
        return (
            kind,
            rights_ref.as_posix() if rights_ref else None,
            str(status or "unclassified"),
        )
    raise PublicTreeError(
        f"{relative.as_posix()}: public data path has no rights classification"
    )


def build_public_data_inventory(root: Path) -> dict[str, object]:
    """Build the canonical, closed inventory for all retained public data bytes."""

    base = root.resolve()
    descriptor_rights = _descriptor_rights()
    entries: list[dict[str, object]] = []
    for prefix in _DATA_PREFIXES:
        for relative, raw in _iter_files(base, prefix):
            kind, rights_ref, status = _entry_metadata(
                base,
                relative,
                descriptor_rights=descriptor_rights,
            )
            entries.append(
                {
                    "kind": kind,
                    "path": relative.as_posix(),
                    "redistribution_status": status,
                    "rights_ref": rights_ref,
                    "sha256": _sha256(raw),
                    "size": len(raw),
                }
            )
    entries.sort(key=lambda item: str(item["path"]))
    return {"schema_version": INVENTORY_SCHEMA, "entries": entries}


def _read_inventory(root: Path) -> tuple[dict[str, object] | None, list[str]]:
    path = root.joinpath(*INVENTORY_PATH.parts)
    try:
        raw = _read_regular(
            path, limit=4 * 1024 * 1024, label=INVENTORY_PATH.as_posix()
        )
        payload = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError, PublicTreeError) as exc:
        return None, [
            f"{INVENTORY_PATH.as_posix()}: cannot read public inventory: {exc}"
        ]
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "entries"}:
        return None, [
            f"{INVENTORY_PATH.as_posix()}: inventory fields are incomplete or unknown"
        ]
    if payload["schema_version"] != INVENTORY_SCHEMA or not isinstance(
        payload["entries"], list
    ):
        return None, [f"{INVENTORY_PATH.as_posix()}: inventory schema is unsupported"]
    if raw != _canonical_json_bytes(payload):
        return None, [
            f"{INVENTORY_PATH.as_posix()}: inventory must use canonical JSON bytes"
        ]
    return payload, []


def _walk_office_archives(root: Path) -> Iterator[Path]:
    pending = [root]
    while pending:
        directory = pending.pop()
        for entry in sorted(os.scandir(directory), key=lambda item: item.name):
            if entry.name in _IGNORED_WALK_NAMES:
                continue
            path = Path(entry.path)
            if entry.is_symlink():
                continue
            if entry.is_dir(follow_symlinks=False):
                pending.append(path)
            elif (
                entry.is_file(follow_symlinks=False)
                and path.suffix.lower() in _OFFICE_SUFFIXES
            ):
                yield path


def _check_office_archive(root: Path, path: Path) -> list[str]:
    relative = path.relative_to(root).as_posix()
    errors: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if len(members) > _MAX_OFFICE_MEMBERS:
                return [f"{relative}: Office archive exceeds its member bound"]
            for member in members:
                if member.file_size > _MAX_OFFICE_MEMBER_BYTES:
                    errors.append(
                        f"{relative}: Office member {member.filename!r} exceeds its byte bound"
                    )
                    continue
                raw = archive.read(member)
                if _MACHINE_PATH.search(raw):
                    errors.append(
                        f"{relative}: Office member {member.filename!r} contains an embedded local machine path"
                    )
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        errors.append(f"{relative}: cannot inspect Office archive: {exc}")
    return errors


def _check_generated_sources(root: Path) -> list[str]:
    errors = validate_generated_motif_inventory(root)
    bundles: set[Path] = set()
    motif_root = root / "generated/motif_models"
    if motif_root.exists():
        for manifest in motif_root.glob("*/*/manifest.json"):
            if manifest.parent.parent.name == "pools":
                continue
            bundles.add(manifest.parent)
    for bundle in sorted(bundles):
        label = bundle.relative_to(root).as_posix()
        try:
            receipt_path = bundle / "receipt.json"
            if receipt_path.is_file():
                receipt = json.loads(receipt_path.read_bytes())
                if not isinstance(receipt, dict):
                    raise MotifExportError("receipt must be a JSON object")
                revalidate_motif_export_receipt(
                    bundle,
                    receipt,
                    owner_repository_path=root,
                    data_root=root,
                )
            else:
                validate_motif_export_source_replay(bundle, data_root=root)
        except (OSError, UnicodeError, json.JSONDecodeError, MotifExportError) as exc:
            errors.append(f"{label}: generated motif source replay failed: {exc}")
    return errors


def check_public_tree(root: Path) -> list[str]:
    """Return complete-tree publication errors without relying on a Git diff."""

    base = root.resolve()
    errors: list[str] = []
    try:
        actual = build_public_data_inventory(base)
    except (OSError, UnicodeError, json.JSONDecodeError, PublicTreeError) as exc:
        actual = None
        errors.append(str(exc))
    expected, inventory_errors = _read_inventory(base)
    errors.extend(inventory_errors)
    if actual is not None and expected is not None:
        expected_by_path: dict[object, dict[str, object]] = {}
        for item in expected["entries"]:
            if not isinstance(item, dict):
                errors.append("PUBLIC_DATA_INVENTORY.json: entries must be objects")
                continue
            path = item.get("path")
            if path in expected_by_path:
                errors.append(f"{path}: public inventory repeats path")
                continue
            expected_by_path[path] = item
        actual_by_path = {
            item["path"]: item for item in actual["entries"] if isinstance(item, dict)
        }
        for path in sorted(set(actual_by_path) - set(expected_by_path)):
            errors.append(f"{path}: not declared in {INVENTORY_PATH.as_posix()}")
        for path in sorted(set(expected_by_path) - set(actual_by_path)):
            errors.append(f"{path}: declared public inventory member is missing")
        for path in sorted(set(actual_by_path) & set(expected_by_path)):
            expected_entry = expected_by_path[path]
            actual_entry = actual_by_path[path]
            if set(expected_entry) != {
                "kind",
                "path",
                "redistribution_status",
                "rights_ref",
                "sha256",
                "size",
            }:
                errors.append(
                    f"{path}: inventory entry fields are incomplete or unknown"
                )
                continue
            if expected_entry.get("sha256") != actual_entry.get("sha256"):
                errors.append(f"{path}: content digest disagrees with public inventory")
            elif expected_entry != actual_entry:
                errors.append(f"{path}: metadata disagrees with public inventory")
    if actual is not None:
        for entry in actual["entries"]:
            if not isinstance(entry, dict):
                continue
            path = str(entry["path"])
            status = entry["redistribution_status"]
            kind = entry["kind"]
            if kind == "database_source" and status != "redistributable":
                errors.append(f"{path}: {status} database payload cannot be published")
            if kind in {"model_artifact", "model_manifest", "model_receipt"}:
                if status != "redistributable":
                    errors.append(
                        f"{path}: generated motif source is not redistributable"
                    )
                if not entry["rights_ref"]:
                    errors.append(
                        f"{path}: generated motif source lacks database rights metadata"
                    )
            rights_ref = entry["rights_ref"]
            if rights_ref:
                try:
                    rights = _rights_payload(base, PurePosixPath(str(rights_ref)))
                except PublicTreeError as exc:
                    errors.append(str(exc))
                    continue
                if rights.get("schema_version") != RIGHTS_SCHEMA:
                    errors.append(
                        f"{rights_ref}: database rights schema is unsupported"
                    )
                if rights.get("redistribution_status") != "redistributable":
                    errors.append(f"{path}: rights metadata is not redistributable")
    errors.extend(_check_generated_sources(base))
    for archive in _walk_office_archives(base):
        errors.extend(_check_office_archive(base, archive))
    return sorted(set(errors))


def check_tag_state(root: Path, tag: str) -> list[str]:
    """Require a clean worktree whose HEAD is exactly the named local tag."""

    if not tag or any(character.isspace() for character in tag):
        return ["tag name must be one non-empty whitespace-free value"]
    head = subprocess.run(
        ["git", "rev-parse", "HEAD^{commit}"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    tagged = subprocess.run(
        ["git", "rev-parse", f"refs/tags/{tag}^{{commit}}"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    errors: list[str] = []
    if head.returncode != 0 or tagged.returncode != 0:
        errors.append(f"cannot resolve HEAD and local tag {tag!r}")
    elif head.stdout.strip() != tagged.stdout.strip():
        errors.append(f"HEAD is not exactly local tag {tag!r}")
    if status.returncode != 0 or status.stdout:
        errors.append("tag publication requires a clean closed worktree")
    return errors


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the complete public data tree."
    )
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--require-tag")
    args = parser.parse_args(argv)
    errors = check_public_tree(args.repo_root)
    if args.require_tag:
        errors.extend(check_tag_state(args.repo_root, args.require_tag))
    if errors:
        for error in sorted(set(errors)):
            print(error, file=sys.stderr)
        return 1
    print("public tree check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
