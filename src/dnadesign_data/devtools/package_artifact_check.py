"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/devtools/package_artifact_check.py

Checks built distribution inventories for private or repository-owned data.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import argparse
import os
import re
import stat
import sys
import tarfile
import zipfile
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[3]
_MAX_MEMBERS = 10_000
_MAX_MEMBER_BYTES = 16 * 1024 * 1024
_MAX_TOTAL_BYTES = 128 * 1024 * 1024
_MACHINE_PATH = re.compile(
    rb"(?:file:/+)?/" + rb"Users/[^/\x00\s<]+/"
    rb"|[A-Za-z]:[\\/]+" + rb"Users[\\/]+[^\\/\x00\s<]+[\\/]"
)
_PRIVATE_KEY = re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?" + rb"PRIVATE KEY-----")
_ACCESS_TOKEN = re.compile(
    rb"(?:AKIA[A-Z0-9]{16}|gh[pousr]_[A-Za-z0-9]{20,}|sk-(?:proj-)?[A-Za-z0-9_-]{20,})"
)
_PRIVATE_SHELF_COMPONENTS = {
    ".git",
    ".local",
    ".private",
    "generated",
    "local",
    "primary_literature",
    "private",
    "sources",
}
_PRIVATE_SHELF_PREFIXES = ("ecocyc_", "regulondb_")
_CREDENTIAL_NAMES = {".env", "credentials.json", "credentials.toml", "secrets.json"}
_CREDENTIAL_SUFFIXES = {".key", ".p12", ".pem"}
_BUILD_TOOL_MARKERS = {".gitignore": b"*"}
_DATA_SUFFIXES = {
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
_NONPUBLIC_POSTURE = re.compile(
    rb"(?i)redistribution[_ -]?status[\"']?\s*(?::|=|\t|,)\s*[\"']?"
    rb"(?:private_storage|review_blocked|review_required|legacy_unclassified|unclassified)"
)


@dataclass(frozen=True)
class ProjectIdentity:
    name: str
    normalized_name: str
    package_name: str
    version: str


def _parse_project(raw: bytes, *, label: str) -> ProjectIdentity:
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeError as exc:
        raise ValueError(f"{label}: pyproject.toml is not UTF-8: {exc}") from exc
    section = ""
    fields: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped
            continue
        if section != "[project]":
            continue
        match = re.fullmatch(r'(name|version)\s*=\s*"([^"\s]+)"', stripped)
        if match:
            fields[match.group(1)] = match.group(2)
    if set(fields) != {"name", "version"}:
        raise ValueError(f"{label}: [project] must declare literal name and version")
    normalized = re.sub(r"[-_.]+", "_", fields["name"]).lower()
    return ProjectIdentity(
        name=fields["name"],
        normalized_name=normalized,
        package_name=normalized,
        version=fields["version"],
    )


def _read_project_identity(
    project_root: Path,
) -> tuple[ProjectIdentity | None, list[str]]:
    path = project_root / "pyproject.toml"
    try:
        raw = path.read_bytes()
        return _parse_project(raw, label="pyproject.toml"), []
    except (OSError, ValueError) as exc:
        return None, [f"cannot resolve package identity: {exc}"]


def _safe_member_path(
    name: str, *, artifact: str
) -> tuple[PurePosixPath | None, list[str]]:
    path = PurePosixPath(name)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        return None, [f"{artifact}:{name}: archive member path is unsafe"]
    return path, []


def _check_member(artifact: str, path: PurePosixPath, raw: bytes) -> list[str]:
    errors: list[str] = []
    lowered = tuple(part.lower() for part in path.parts)
    if any(part in _PRIVATE_SHELF_COMPONENTS for part in lowered) or any(
        part.startswith(_PRIVATE_SHELF_PREFIXES) for part in lowered[:-1]
    ):
        errors.append(
            f"{artifact}:{path}: private or repository data shelf is packaged"
        )
    name = path.name.lower()
    if (
        name in _CREDENTIAL_NAMES
        or name.startswith(".env.")
        or path.suffix.lower() in _CREDENTIAL_SUFFIXES
    ):
        errors.append(f"{artifact}:{path}: credential-bearing member name is packaged")
    if _MACHINE_PATH.search(raw):
        errors.append(f"{artifact}:{path}: local machine home path is packaged")
    if _PRIVATE_KEY.search(raw) or _ACCESS_TOKEN.search(raw):
        errors.append(f"{artifact}:{path}: credential material is packaged")
    is_data_like = path.suffix.lower() in _DATA_SUFFIXES
    if is_data_like:
        errors.append(f"{artifact}:{path}: data-like member is not allowed in package")
    if is_data_like and _NONPUBLIC_POSTURE.search(raw):
        errors.append(
            f"{artifact}:{path}: nonpublic redistribution posture is packaged"
        )
    return errors


def _wheel_members(path: Path) -> Iterator[tuple[str, bytes, list[str]]]:
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > _MAX_MEMBERS:
            raise ValueError("archive exceeds its member bound")
        for member in members:
            member_errors: list[str] = []
            mode = (member.external_attr >> 16) & 0xFFFF
            file_type = stat.S_IFMT(mode)
            if member.is_dir() or file_type not in {0, stat.S_IFREG}:
                member_errors.append(
                    f"{path.name}:{member.filename}: member is not a regular file"
                )
                yield member.filename, b"", member_errors
                continue
            if member.file_size > _MAX_MEMBER_BYTES:
                member_errors.append(
                    f"{path.name}:{member.filename}: member exceeds its byte bound"
                )
                yield member.filename, b"", member_errors
                continue
            yield member.filename, archive.read(member), member_errors


def _sdist_members(path: Path) -> Iterator[tuple[str, bytes, list[str]]]:
    with tarfile.open(path, mode="r:gz") as archive:
        members = archive.getmembers()
        if len(members) > _MAX_MEMBERS:
            raise ValueError("archive exceeds its member bound")
        for member in members:
            if member.isdir():
                continue
            member_errors: list[str] = []
            if not member.isfile():
                member_errors.append(
                    f"{path.name}:{member.name}: member is not a regular file"
                )
                yield member.name, b"", member_errors
                continue
            if member.size > _MAX_MEMBER_BYTES:
                member_errors.append(
                    f"{path.name}:{member.name}: member exceeds its byte bound"
                )
                yield member.name, b"", member_errors
                continue
            handle = archive.extractfile(member)
            if handle is None:
                member_errors.append(
                    f"{path.name}:{member.name}: member cannot be read"
                )
                yield member.name, b"", member_errors
                continue
            yield member.name, handle.read(), member_errors


def _metadata_errors(
    artifact: str, path: PurePosixPath, raw: bytes, identity: ProjectIdentity
) -> list[str]:
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeError as exc:
        return [f"{artifact}:{path}: package metadata is not UTF-8: {exc}"]
    fields: dict[str, str] = {}
    for line in lines:
        if ": " in line:
            key, value = line.split(": ", 1)
            if key in {"Name", "Version"} and key not in fields:
                fields[key] = value
    errors: list[str] = []
    if fields.get("Name") != identity.name:
        errors.append(f"{artifact}:{path}: metadata Name does not match pyproject")
    if fields.get("Version") != identity.version:
        errors.append(f"{artifact}:{path}: metadata Version does not match pyproject")
    return errors


def _structure_errors(
    artifact: str,
    members: dict[PurePosixPath, bytes],
    *,
    wheel: bool,
    identity: ProjectIdentity,
) -> list[str]:
    if wheel:
        metadata_root = f"{identity.normalized_name}-{identity.version}.dist-info"
        required = {
            PurePosixPath(identity.package_name, "__init__.py"),
            PurePosixPath(metadata_root, "METADATA"),
            PurePosixPath(metadata_root, "RECORD"),
            PurePosixPath(metadata_root, "WHEEL"),
        }
        metadata_path = PurePosixPath(metadata_root, "METADATA")
        pyproject_path = None
    else:
        root = f"{identity.normalized_name}-{identity.version}"
        required = {
            PurePosixPath(root, "PKG-INFO"),
            PurePosixPath(root, "pyproject.toml"),
            PurePosixPath(root, "src", identity.package_name, "__init__.py"),
        }
        metadata_path = PurePosixPath(root, "PKG-INFO")
        pyproject_path = PurePosixPath(root, "pyproject.toml")
    errors = [
        f"{artifact}:{path}: required package member is missing"
        for path in sorted(required - set(members), key=str)
    ]
    if metadata_path in members:
        errors.extend(
            _metadata_errors(artifact, metadata_path, members[metadata_path], identity)
        )
    if pyproject_path is not None and pyproject_path in members:
        try:
            embedded = _parse_project(
                members[pyproject_path], label=f"{artifact}:{pyproject_path}"
            )
        except ValueError as exc:
            errors.append(str(exc))
        else:
            if embedded != identity:
                errors.append(
                    f"{artifact}:{pyproject_path}: embedded project identity does not match"
                )
    if not wheel:
        expected_root = f"{identity.normalized_name}-{identity.version}"
        for path in members:
            if not path.parts or path.parts[0] != expected_root:
                errors.append(
                    f"{artifact}:{path}: sdist member is outside canonical root"
                )
    return errors


def _check_archive(path: Path, *, wheel: bool, identity: ProjectIdentity) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    member_payloads: dict[PurePosixPath, bytes] = {}
    total = 0
    try:
        iterator = _wheel_members(path) if wheel else _sdist_members(path)
        for name, raw, member_errors in iterator:
            errors.extend(member_errors)
            if name in seen:
                errors.append(f"{path.name}:{name}: archive member path is duplicated")
            seen.add(name)
            total += len(raw)
            if total > _MAX_TOTAL_BYTES:
                errors.append(f"{path.name}: archive exceeds its expanded byte bound")
                break
            member_path, path_errors = _safe_member_path(name, artifact=path.name)
            errors.extend(path_errors)
            if member_path is not None:
                errors.extend(_check_member(path.name, member_path, raw))
                member_payloads[member_path] = raw
    except (
        OSError,
        tarfile.TarError,
        zipfile.BadZipFile,
        RuntimeError,
        ValueError,
    ) as exc:
        errors.append(f"{path.name}: cannot inspect distribution archive: {exc}")
    errors.extend(
        _structure_errors(path.name, member_payloads, wheel=wheel, identity=identity)
    )
    return errors


def check_package_artifacts(
    dist_dir: Path, *, project_root: Path | None = None
) -> list[str]:
    """Require and inspect exactly one wheel and one source distribution."""

    identity, identity_errors = _read_project_identity(project_root or dist_dir.parent)
    if identity is None:
        return identity_errors
    try:
        entries = sorted(os.scandir(dist_dir), key=lambda entry: entry.name)
    except OSError as exc:
        return [f"{dist_dir}: cannot enumerate distribution directory: {exc}"]
    errors: list[str] = list(identity_errors)
    files: list[Path] = []
    for entry in entries:
        if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
            errors.append(
                f"{entry.name}: distribution directory entries must be regular files"
            )
            continue
        path = Path(entry.path)
        if entry.name in _BUILD_TOOL_MARKERS:
            try:
                marker = path.read_bytes()
            except OSError as exc:
                errors.append(f"{entry.name}: cannot read build-tool marker: {exc}")
            else:
                if marker != _BUILD_TOOL_MARKERS[entry.name]:
                    errors.append(
                        f"{entry.name}: build-tool marker bytes are unexpected"
                    )
            continue
        files.append(path)
    wheels = [path for path in files if path.name.endswith(".whl")]
    sdists = [path for path in files if path.name.endswith(".tar.gz")]
    if len(wheels) != 1 or len(sdists) != 1 or len(files) != 2:
        errors.append(
            "distribution directory must contain exactly one wheel and one .tar.gz sdist"
        )
    for wheel in wheels:
        expected_prefix = f"{identity.normalized_name}-{identity.version}-"
        if not wheel.name.startswith(expected_prefix):
            errors.append(f"{wheel.name}: wheel filename does not match pyproject")
        errors.extend(_check_archive(wheel, wheel=True, identity=identity))
    for sdist in sdists:
        expected_name = f"{identity.normalized_name}-{identity.version}.tar.gz"
        if sdist.name != expected_name:
            errors.append(f"{sdist.name}: sdist filename does not match pyproject")
        errors.extend(_check_archive(sdist, wheel=False, identity=identity))
    return sorted(set(errors))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect built package artifacts.")
    parser.add_argument("--dist-dir", type=Path, default=ROOT / "dist")
    parser.add_argument("--project-root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    errors = check_package_artifacts(args.dist_dir, project_root=args.project_root)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("package artifact check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
