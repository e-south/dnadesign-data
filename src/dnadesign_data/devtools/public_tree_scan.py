"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/devtools/public_tree_scan.py

Scans every tracked repository member for public-tree privacy hazards.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import os
import re
import stat
import subprocess
import zipfile
from collections.abc import Iterator
from pathlib import Path, PurePosixPath

_OFFICE_SUFFIXES = {".docx", ".xlsx", ".pptx"}
_MACHINE_PATH = re.compile(
    rb"(?:file:/+)?/" + rb"Users/[^/\x00\s<]+/"
    rb"|[A-Za-z]:[\\/]+" + rb"Users[\\/]+[^\\/\x00\s<]+[\\/]"
)
_FORBIDDEN_PAYLOAD_TOKENS = (
    "ecocyc",
    "o-malley",
    "o_malley",
    "omalley",
    "regulondb",
)
_PAYLOAD_SUFFIXES = {
    ".csv",
    ".fa",
    ".fasta",
    ".jaspar",
    ".json",
    ".meme",
    ".parquet",
    ".pdf",
    ".tsv",
    ".xls",
    ".xlsx",
    ".zip",
}
_FORBIDDEN_POSTURE = re.compile(
    rb"(?i)(?:redistribution[_ -]?status\s*[:=\t,]\s*)"
    rb"(?:private_storage|review_blocked|review_required|legacy_unclassified|unclassified)"
)
_IGNORED_WALK_NAMES = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
}
_MAX_OFFICE_MEMBERS = 10_000
_MAX_OFFICE_MEMBER_BYTES = 16 * 1024 * 1024


class TrackedTreeError(ValueError):
    """Raised when tracked-tree state cannot be read safely."""


def _read_regular(path: Path, *, limit: int, label: str) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise TrackedTreeError(
            f"{label}: cannot open bounded regular file: {exc}"
        ) from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise TrackedTreeError(
                f"{label}: tracked tree members must be regular files"
            )
        if metadata.st_size > limit:
            raise TrackedTreeError(
                f"{label}: tracked tree member exceeds its byte bound"
            )
        raw = b""
        while len(raw) <= metadata.st_size:
            chunk = os.read(descriptor, min(64 * 1024, metadata.st_size + 1 - len(raw)))
            if not chunk:
                break
            raw += chunk
        if len(raw) != metadata.st_size:
            raise TrackedTreeError(
                f"{label}: tracked tree member changed while reading"
            )
        return raw
    finally:
        os.close(descriptor)


def _fallback_entries(root: Path) -> Iterator[tuple[PurePosixPath, str]]:
    pending = [root]
    while pending:
        directory = pending.pop()
        for entry in sorted(os.scandir(directory), key=lambda item: item.name):
            if entry.name in _IGNORED_WALK_NAMES:
                continue
            path = Path(entry.path)
            relative = PurePosixPath(path.relative_to(root).as_posix())
            if entry.is_symlink():
                yield relative, "120000"
            elif entry.is_dir(follow_symlinks=False):
                pending.append(path)
            elif entry.is_file(follow_symlinks=False):
                yield relative, "100644"
            else:
                yield relative, "000000"


def _tracked_entries(root: Path) -> tuple[tuple[PurePosixPath, str], ...]:
    tracked = subprocess.run(
        ["git", "ls-files", "--stage", "-z"],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if tracked.returncode != 0:
        return tuple(_fallback_entries(root))
    entries: list[tuple[PurePosixPath, str]] = []
    for record in tracked.stdout.split(b"\0"):
        if not record:
            continue
        try:
            metadata, raw_path = record.split(b"\t", 1)
            mode = metadata.split(b" ", 1)[0].decode("ascii")
            path = PurePosixPath(raw_path.decode("utf-8", errors="surrogateescape"))
        except (ValueError, UnicodeError) as exc:
            raise TrackedTreeError(f"cannot parse tracked-tree entry: {exc}") from exc
        entries.append((path, mode))
    return tuple(entries)


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
                if _MACHINE_PATH.search(archive.read(member)):
                    errors.append(
                        f"{relative}: Office member {member.filename!r} contains an embedded local machine path"
                    )
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        errors.append(f"{relative}: cannot inspect Office archive: {exc}")
    return errors


def scan_tracked_tree(root: Path, *, max_file_bytes: int) -> list[str]:
    """Return path, type, posture, and machine-path errors for the tracked tree."""

    errors: list[str] = []
    try:
        entries = _tracked_entries(root)
    except TrackedTreeError as exc:
        return [str(exc)]
    for relative, mode in entries:
        label = relative.as_posix()
        path = root.joinpath(*relative.parts)
        if mode == "120000" or path.is_symlink():
            errors.append(f"{label}: symbolic links are forbidden")
            continue
        if mode not in {"100644", "100755"}:
            errors.append(f"{label}: tracked tree entries must be regular files")
            continue
        try:
            raw = _read_regular(path, limit=max_file_bytes, label=label)
        except TrackedTreeError as exc:
            errors.append(str(exc))
            continue
        suffix = relative.suffix.lower()
        if suffix in _PAYLOAD_SUFFIXES and any(
            token in label.lower() for token in _FORBIDDEN_PAYLOAD_TOKENS
        ):
            errors.append(f"{label}: forbidden private source payload name")
        if suffix in _PAYLOAD_SUFFIXES and _FORBIDDEN_POSTURE.search(raw):
            errors.append(f"{label}: forbidden nonpublic redistribution posture")
        if _MACHINE_PATH.search(raw):
            errors.append(f"{label}: contains a local machine path")
        if suffix in _OFFICE_SUFFIXES:
            errors.extend(_check_office_archive(root, path))
    return errors
