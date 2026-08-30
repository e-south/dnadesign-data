"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/motifs/git_authority.py

Verifies bounded motif source and artifact blobs against durable Git anchors.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from dnadesign_data.motifs.contracts import (
    MotifExportError,
    reject_symbolic_link_ancestors,
)
from dnadesign_data.motifs.receipt_validation import REVISION_PATTERN


def run_git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    """Run one bounded local Git command without invoking a shell."""

    try:
        return subprocess.run(
            ["git", "-C", str(repository), "--no-pager", *arguments],
            check=False,
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MotifExportError("unable to verify the owner Git repository") from exc


def _verify_git_blob(
    repository: Path,
    *,
    owner_revision: str,
    ref_path: str,
    admitted_bytes: bytes,
    max_bytes: int,
    label: str,
) -> None:
    object_ref = f"{owner_revision}:{ref_path}"
    size_result = run_git(repository, "cat-file", "-s", object_ref)
    try:
        size = int(size_result.stdout.decode("ascii").strip())
    except (UnicodeDecodeError, ValueError) as exc:
        raise MotifExportError(f"canonical {label} Git target does not exist") from exc
    if size_result.returncode != 0 or size < 0:
        raise MotifExportError(f"canonical {label} Git target does not exist")
    if size > max_bytes or size > len(admitted_bytes):
        raise MotifExportError(
            f"canonical {label} Git blob exceeds the admitted byte bound"
        )
    target = run_git(repository, "show", object_ref)
    if target.returncode != 0:
        raise MotifExportError(f"canonical {label} Git target does not exist")
    if target.stdout != admitted_bytes:
        raise MotifExportError(
            f"canonical {label} Git target bytes disagree with admitted bytes"
        )


def verify_git_authority(
    repository_path: str | Path,
    *,
    owner_revision: str,
    integration_anchors: frozenset[str],
    ref_path: str,
    artifact_bytes: bytes,
    artifact_max_bytes: int,
    source_ref_path: str,
    source_bytes: bytes,
    source_max_bytes: int,
) -> None:
    """Require owner_revision to be reachable from a durable advertised anchor."""

    repository = Path(repository_path)
    reject_symbolic_link_ancestors(repository)
    if repository.is_symlink() or not repository.is_dir():
        raise MotifExportError("owner Git repository is unavailable")
    revision = run_git(repository, "cat-file", "-e", f"{owner_revision}^{{commit}}")
    if revision.returncode != 0:
        raise MotifExportError("owner_revision does not exist as a Git commit")
    reachable = False
    for anchor in integration_anchors:
        anchor_commit = run_git(repository, "rev-parse", f"{anchor}^{{commit}}")
        if anchor_commit.returncode != 0:
            continue
        candidate = anchor_commit.stdout.decode("ascii", errors="ignore").strip()
        if REVISION_PATTERN.fullmatch(candidate) is None:
            continue
        if (
            run_git(
                repository,
                "merge-base",
                "--is-ancestor",
                owner_revision,
                candidate,
            ).returncode
            == 0
        ):
            reachable = True
            break
    if not reachable:
        raise MotifExportError(
            "owner_revision is not reachable from a canonical GitHub remote integration or release anchor"
        )
    _verify_git_blob(
        repository,
        owner_revision=owner_revision,
        ref_path=ref_path,
        admitted_bytes=artifact_bytes,
        max_bytes=artifact_max_bytes,
        label="artifact",
    )
    _verify_git_blob(
        repository,
        owner_revision=owner_revision,
        ref_path=source_ref_path,
        admitted_bytes=source_bytes,
        max_bytes=source_max_bytes,
        label="catalog source",
    )
