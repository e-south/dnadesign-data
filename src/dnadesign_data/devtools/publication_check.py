"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/devtools/publication_check.py

Fails closed when changed literature payloads lack a publishable rights posture.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

from dnadesign_data.catalog.regulatory_parts import known_motif_source_files
from dnadesign_data.devtools.generated_motif_check import (
    validate_generated_motif_inventory as _validate_generated_motif_inventory,
)
from dnadesign_data.motifs.contracts import MotifExportError
from dnadesign_data.motifs.receipt_validation import revalidate_motif_export_receipt
from dnadesign_data.motifs.receipts import validate_motif_export_source_replay

ROOT = Path(__file__).resolve().parents[3]
_LITERATURE_PREFIX = PurePosixPath("sources/literature")
_DATABASE_PREFIX = PurePosixPath("sources/databases")
_GENERATED_MOTIF_PREFIX = PurePosixPath("generated/motif_models")
_DATABASE_RIGHTS_SCHEMA = "dnadesign-data.database-rights/v1"
_DATABASE_RIGHTS_KEYS = {
    "schema_version",
    "database",
    "release",
    "redistribution_status",
    "rights_url",
    "attribution",
    "reviewed_on",
    "reviewer",
}
_STATUSES = {
    "legacy_unclassified",
    "link_only",
    "redistributable",
    "review_required",
}
_PROVENANCE_NAMES = {"intake.json", "retrieval.json", "source.json"}
_PROVENANCE_KEYS = {
    "content_sha256",
    "license_url",
    "notes",
    "retrieved_at",
    "source_url",
}
_MAX_PROVENANCE_BYTES = 32 * 1024


class DuplicateMetadataKeyError(ValueError):
    """Raised when literature metadata contains an ambiguous JSON key."""


@dataclass(frozen=True)
class ChangedPath:
    """One changed literature path and its Git name-status code."""

    status: str
    path: str


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    payload: dict[str, object] = {}
    for key, value in pairs:
        if key in payload:
            raise DuplicateMetadataKeyError(f"duplicate key {key!r}")
        payload[key] = value
    return payload


def _is_https_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def _is_valid_review_date(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        reviewed_on = datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return reviewed_on <= datetime.datetime.now(datetime.timezone.utc).date()


def _validate_redistribution_evidence(
    relative: str, payload: dict[str, object]
) -> list[str]:
    errors: list[str] = []
    required_strings = (
        "redistribution_basis",
        "redistribution_reviewer",
    )
    for field in required_strings:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{relative}: {field} must be a non-empty string")
    if not _is_https_url(payload.get("redistribution_basis_url")):
        errors.append(f"{relative}: redistribution_basis_url must be an HTTPS URL")
    if not _is_valid_review_date(payload.get("redistribution_reviewed_on")):
        errors.append(
            f"{relative}: redistribution_reviewed_on must be a nonfuture ISO date"
        )
    return errors


def _is_blocked_shelf_metadata(path: PurePosixPath) -> bool:
    if path in {PurePosixPath("metadata.json"), PurePosixPath("README.md")}:
        return True
    return (
        path.parts[:2]
        in {
            ("raw", "provenance"),
            ("processed", "provenance"),
        }
        and path.name in _PROVENANCE_NAMES
    )


def _validate_provenance_descriptor(base: Path, relative: PurePosixPath) -> list[str]:
    source_path = base / relative
    label = relative.as_posix()
    try:
        if source_path.stat().st_size > _MAX_PROVENANCE_BYTES:
            return [
                f"{label}: provenance descriptor exceeds {_MAX_PROVENANCE_BYTES} bytes"
            ]
        payload = json.loads(
            source_path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        DuplicateMetadataKeyError,
    ) as exc:
        return [f"{label}: cannot read provenance descriptor JSON: {exc}"]
    if not isinstance(payload, dict):
        return [f"{label}: provenance descriptor must be a JSON object"]
    unexpected = sorted(set(payload) - _PROVENANCE_KEYS)
    if unexpected:
        return [f"{label}: unsupported provenance fields: {', '.join(unexpected)}"]
    if not _is_https_url(payload.get("source_url")):
        return [f"{label}: source_url must be an HTTPS URL"]
    for field in ("license_url",):
        value = payload.get(field)
        if value is not None and not _is_https_url(value):
            return [f"{label}: {field} must be an HTTPS URL when present"]
    return []


def check_publication(root: Path, *, changed_paths: Sequence[ChangedPath]) -> list[str]:
    """Return publication-contract errors for metadata and changed payloads."""

    base = root.resolve()
    errors = _validate_generated_motif_inventory(base)
    metadata_records: dict[str, dict[str, object]] = {}
    database_rights: dict[tuple[str, str], dict[str, object]] = {}
    checked_generated_bundles: set[Path] = set()
    for rights_path in sorted((base / _DATABASE_PREFIX).glob("*/*/rights.json")):
        relative = rights_path.relative_to(base).as_posix()
        try:
            payload = json.loads(
                rights_path.read_text(encoding="utf-8"),
                object_pairs_hook=_reject_duplicate_keys,
            )
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            DuplicateMetadataKeyError,
        ) as exc:
            errors.append(f"{relative}: cannot read database rights JSON: {exc}")
            continue
        if not isinstance(payload, dict) or set(payload) != _DATABASE_RIGHTS_KEYS:
            errors.append(
                f"{relative}: database rights fields are incomplete or unknown"
            )
            continue
        if payload["schema_version"] != _DATABASE_RIGHTS_SCHEMA:
            errors.append(f"{relative}: database rights schema is unsupported")
            continue
        release_root = rights_path.parent.relative_to(base)
        database_id, release_id = release_root.parts[-2:]
        if payload["release"] != release_id:
            errors.append(f"{relative}: release disagrees with its directory")
            continue
        if payload["redistribution_status"] not in {
            "redistributable",
            "private_storage",
            "review_blocked",
        }:
            errors.append(f"{relative}: database redistribution_status is unsupported")
            continue
        for field in ("database", "attribution", "reviewer"):
            if not isinstance(payload[field], str) or not payload[field].strip():
                errors.append(f"{relative}: {field} must be a non-empty string")
        if not _is_https_url(payload["rights_url"]):
            errors.append(f"{relative}: rights_url must be an HTTPS URL")
        if not _is_valid_review_date(payload["reviewed_on"]):
            errors.append(f"{relative}: reviewed_on must be a nonfuture ISO date")
        database_rights[(database_id, release_id)] = payload
    for metadata_path in sorted((base / _LITERATURE_PREFIX).glob("*/metadata.json")):
        relative = metadata_path.relative_to(base).as_posix()
        try:
            payload = json.loads(
                metadata_path.read_text(encoding="utf-8"),
                object_pairs_hook=_reject_duplicate_keys,
            )
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            DuplicateMetadataKeyError,
        ) as exc:
            errors.append(f"{relative}: cannot read metadata JSON: {exc}")
            continue
        if not isinstance(payload, dict):
            errors.append(f"{relative}: metadata must be a JSON object")
            continue
        status = payload.get("redistribution_status")
        if status not in _STATUSES:
            supported = ", ".join(sorted(_STATUSES))
            errors.append(
                f"{relative}: redistribution_status must be one of {supported}"
            )
            continue
        note = payload.get("redistribution_note")
        if not isinstance(note, str) or not note.strip():
            errors.append(f"{relative}: redistribution_note must be a non-empty string")
            continue
        if status == "redistributable":
            errors.extend(_validate_redistribution_evidence(relative, payload))
        metadata_records[metadata_path.parent.name] = payload

    for change in sorted(set(changed_paths), key=lambda item: (item.path, item.status)):
        path = PurePosixPath(change.path)
        if (
            len(path.parts) >= 5
            and PurePosixPath(*path.parts[:2]) == _GENERATED_MOTIF_PREFIX
            and path.parts[2] != "pools"
        ):
            if change.status == "D":
                continue
            bundle = base.joinpath(*path.parts[:4])
            if bundle not in checked_generated_bundles:
                checked_generated_bundles.add(bundle)
                receipt_path = bundle / "receipt.json"
                try:
                    if receipt_path.is_file():
                        receipt = json.loads(
                            receipt_path.read_text(encoding="utf-8"),
                            object_pairs_hook=_reject_duplicate_keys,
                        )
                        if not isinstance(receipt, dict):
                            raise MotifExportError("receipt must be a JSON object")
                        revalidate_motif_export_receipt(
                            bundle,
                            receipt,
                            owner_repository_path=base,
                            data_root=base,
                        )
                    else:
                        validate_motif_export_source_replay(bundle, data_root=base)
                except (
                    OSError,
                    UnicodeError,
                    json.JSONDecodeError,
                    DuplicateMetadataKeyError,
                    MotifExportError,
                ) as exc:
                    errors.append(
                        f"{path.as_posix()}: generated motif bundle failed source replay "
                        f"or durable receipt validation: {exc}"
                    )
            manifest_path = bundle / "manifest.json"
            try:
                manifest = json.loads(
                    manifest_path.read_text(encoding="utf-8"),
                    object_pairs_hook=_reject_duplicate_keys,
                )
                source = manifest["source"]
                descriptor_id = source["descriptor_id"]
            except (
                OSError,
                UnicodeError,
                json.JSONDecodeError,
                DuplicateMetadataKeyError,
                KeyError,
                TypeError,
            ) as exc:
                errors.append(
                    f"{path.as_posix()}: generated motif bundle has no valid source manifest: {exc}"
                )
                continue
            descriptors = [
                item
                for item in known_motif_source_files()
                if item.source_id == descriptor_id
            ]
            if len(descriptors) != 1:
                errors.append(
                    f"{path.as_posix()}: generated motif source descriptor is unknown"
                )
                continue
            descriptor = descriptors[0]
            if (
                source.get("redistribution_status") != "redistributable"
                or descriptor.redistribution_status != "redistributable"
            ):
                errors.append(
                    f"{path.as_posix()}: generated motif source is not redistributable"
                )
                continue
            descriptor_path = PurePosixPath(descriptor.path)
            if (
                len(descriptor_path.parts) < 4
                or PurePosixPath(*descriptor_path.parts[:2]) != _DATABASE_PREFIX
                or database_rights.get(tuple(descriptor_path.parts[2:4]), {}).get(
                    "redistribution_status"
                )
                != "redistributable"
            ):
                errors.append(
                    f"{path.as_posix()}: generated motif source lacks redistributable database rights"
                )
            continue
        if len(path.parts) >= 4 and PurePosixPath(*path.parts[:2]) == _DATABASE_PREFIX:
            if change.status == "D":
                release_root = base.joinpath(*path.parts[:4])
                if (
                    path.name == "rights.json"
                    and release_root.is_dir()
                    and any(
                        entry.name != "rights.json"
                        for entry in os.scandir(release_root)
                    )
                ):
                    errors.append(
                        f"{path.as_posix()}: rights.json cannot be removed while the database release remains"
                    )
                continue
            database_id, release_id = path.parts[2:4]
            rights = database_rights.get((database_id, release_id))
            if rights is None:
                errors.append(
                    f"{path.as_posix()}: database release is missing rights.json"
                )
                continue
            if (
                path.name != "rights.json"
                and rights["redistribution_status"] != "redistributable"
            ):
                errors.append(
                    f"{path.as_posix()}: {rights['redistribution_status']} database payload cannot be published"
                )
            continue
        if len(path.parts) < 4 or PurePosixPath(*path.parts[:2]) != _LITERATURE_PREFIX:
            continue
        slug = path.parts[2]
        relative = path.as_posix()
        package_root = base / _LITERATURE_PREFIX / slug
        package_relative = PurePosixPath(*path.parts[3:])
        if change.status == "D":
            if package_relative == PurePosixPath("metadata.json") and any(
                item.is_file() for item in package_root.rglob("*")
            ):
                errors.append(
                    f"{relative}: metadata.json cannot be removed while the literature package remains"
                )
            continue
        metadata_path = base / _LITERATURE_PREFIX / slug / "metadata.json"
        if not metadata_path.is_file():
            errors.append(f"{relative}: literature package is missing metadata.json")
            continue
        payload = metadata_records.get(slug)
        if payload is None:
            continue
        status = str(payload["redistribution_status"])
        if status == "legacy_unclassified" and package_relative != PurePosixPath(
            "metadata.json"
        ):
            errors.append(
                f"{relative}: legacy_unclassified literature is frozen until "
                "redistribution_status is promoted"
            )
            continue
        if status in {"link_only", "review_required"} and not (
            _is_blocked_shelf_metadata(package_relative)
        ):
            errors.append(
                f"{relative}: {status} literature may publish only package metadata, "
                "README.md, and text provenance descriptors"
            )
        elif status in {"link_only", "review_required"} and package_relative.parts[
            :2
        ] in {("raw", "provenance"), ("processed", "provenance")}:
            errors.extend(_validate_provenance_descriptor(base, path))
    return errors


def _parse_name_status(raw: bytes) -> list[ChangedPath]:
    fields = raw.decode("utf-8", errors="surrogateescape").split("\0")
    changes: list[ChangedPath] = []
    index = 0
    while index < len(fields) and fields[index]:
        status_field = fields[index]
        index += 1
        if index >= len(fields):
            raise ValueError("incomplete git name-status record")
        status = status_field[:1]
        old_or_current = fields[index]
        index += 1
        if status in {"R", "C"}:
            if index >= len(fields):
                raise ValueError("incomplete git rename/copy record")
            new_path = fields[index]
            index += 1
            changes.append(ChangedPath(status="D", path=old_or_current))
            changes.append(ChangedPath(status="A", path=new_path))
        else:
            changes.append(ChangedPath(status=status, path=old_or_current))
    return changes


def _changed_paths(root: Path, base_ref: str | None) -> tuple[ChangedPath, ...]:
    if base_ref and set(base_ref) == {"0"}:
        empty_tree = subprocess.run(
            ["git", "hash-object", "-t", "tree", "--stdin"],
            cwd=root,
            check=False,
            input=b"",
            capture_output=True,
        )
        if empty_tree.returncode != 0:
            raise ValueError(
                "cannot resolve Git empty tree for initial push: "
                f"{empty_tree.stderr.decode(errors='replace').strip()}"
            )
        diff_target = empty_tree.stdout.decode("ascii").strip()
        diff_revisions = [diff_target, "HEAD"]
    else:
        diff_target = "HEAD" if base_ref is None else f"{base_ref}...HEAD"
        diff_revisions = [diff_target]
    diff = subprocess.run(
        [
            "git",
            "diff",
            "--name-status",
            "-z",
            *diff_revisions,
            "--",
            "sources/literature",
            "sources/databases",
            "generated/motif_models",
        ],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if diff.returncode != 0:
        raise ValueError(
            f"cannot resolve publication diff from {diff_target!r}: "
            f"{diff.stderr.decode(errors='replace').strip()}"
        )
    untracked = subprocess.run(
        [
            "git",
            "ls-files",
            "-z",
            "--others",
            "--exclude-standard",
            "--",
            "sources/literature",
            "sources/databases",
            "generated/motif_models",
        ],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if untracked.returncode != 0:
        raise ValueError(
            "cannot enumerate untracked literature paths: "
            f"{untracked.stderr.decode(errors='replace').strip()}"
        )
    changes = _parse_name_status(diff.stdout)
    changes.extend(
        ChangedPath(status="A", path=path)
        for path in untracked.stdout.decode("utf-8", errors="surrogateescape").split(
            "\0"
        )
        if path
    )
    return tuple(sorted(set(changes), key=lambda item: (item.path, item.status)))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate literature publication rights."
    )
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--base-ref")
    args = parser.parse_args(argv)
    try:
        changed_paths = _changed_paths(args.repo_root, args.base_ref)
    except ValueError as exc:
        print(f"publication check failed: {exc}", file=sys.stderr)
        return 2
    errors = check_publication(args.repo_root, changed_paths=changed_paths)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"publication check passed ({len(changed_paths)} changed source paths)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
