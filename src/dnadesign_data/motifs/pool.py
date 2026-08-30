"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/motifs/pool.py

Builds explicit task-driven model inventories and seals fresh formal pools.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

from dnadesign_data.motifs.contracts import (
    MotifExportError,
    canonical_json_bytes,
    model_digest,
    read_source_bytes,
    scoring_semantics_for_model,
    sha256_bytes,
    validate_motif_identity,
)
from dnadesign_data.motifs.git_authority import run_git
from dnadesign_data.motifs.pool_validation import (
    POOL_SCHEMA,
    validate_task_model_pool_request_shape,
)
from dnadesign_data.motifs.receipt_validation import (
    REVISION_PATTERN,
    revalidate_motif_export_receipt,
)
from dnadesign_data.motifs.receipts import (
    _query_canonical_remote_revisions,
    validate_motif_export_source_replay,
)

EXPOSURE_LEDGER_SCHEMA = "dnadesign-data.motif-development-exposure-ledger/v1"
EXPOSURE_LEDGER_PATH = PurePosixPath(
    "sources/motif-development/development-exposure-ledger.json"
)
_IDENTITY = re.compile(r"[A-Za-z][A-Za-z0-9_.-]*")


def _object(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MotifExportError(f"{label} must be an object")
    return value


def _text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise MotifExportError(f"{label} must be a non-empty string")
    return value


def _safe_relative_path(value: object) -> PurePosixPath:
    raw = _text(value, label="bundle_path")
    path = PurePosixPath(raw)
    if (
        path.is_absolute()
        or str(path) != raw
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise MotifExportError("bundle_path must be one canonical relative path")
    return path


def _load_canonical_object(path: Path, *, label: str) -> tuple[dict[str, Any], bytes]:
    _path, raw = read_source_bytes(path, label=label)
    try:
        value = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise MotifExportError(f"{label} is not valid JSON") from exc
    result = _object(value, label=label)
    if raw != canonical_json_bytes(result):
        raise MotifExportError(f"{label} must use canonical JSON bytes")
    return result, raw


def _admit_model(
    entry: dict[str, Any], *, repository_root: Path, formal: bool
) -> dict[str, object]:
    if set(entry) != {"motif_id", "bundle_path"}:
        raise MotifExportError("model entries require exactly motif_id and bundle_path")
    motif_id = validate_motif_identity(entry["motif_id"], label="motif_id")
    bundle = repository_root.joinpath(*_safe_relative_path(entry["bundle_path"]).parts)
    if formal:
        validate_motif_export_source_replay(bundle, data_root=repository_root)
    artifact, artifact_bytes = _load_canonical_object(
        bundle / "artifact.json", label="model artifact"
    )
    manifest, _manifest_bytes = _load_canonical_object(
        bundle / "manifest.json", label="model manifest"
    )
    if artifact.get("motif_id") != motif_id:
        raise MotifExportError("pool motif_id disagrees with the model artifact")
    expected_model_digest = model_digest(artifact)
    if manifest.get("model_digest") != expected_model_digest or manifest.get(
        "artifact_sha256"
    ) != sha256_bytes(artifact_bytes):
        raise MotifExportError("model manifest does not bind the admitted artifact")
    source = _object(manifest.get("source"), label="model manifest source")
    admitted: dict[str, object] = {
        "motif_id": motif_id,
        "model_schema": artifact.get("schema_version"),
        "scoring_semantics": scoring_semantics_for_model(
            artifact.get("schema_version")
        ),
        "model_digest": expected_model_digest,
        "source_descriptor_id": source.get("descriptor_id"),
        "source_revision": source.get("revision"),
        "redistribution_status": source.get("redistribution_status"),
        "conversion_contract": (
            artifact.get("conversion", {}).get("method")
            if isinstance(artifact.get("conversion"), dict)
            else "direct_probability_model_v1"
        ),
    }
    receipt_path = bundle / "receipt.json"
    if receipt_path.is_file():
        receipt, receipt_bytes = _load_canonical_object(
            receipt_path, label="model receipt"
        )
        if formal:
            receipt = revalidate_motif_export_receipt(
                bundle,
                receipt,
                owner_repository_path=repository_root,
                data_root=repository_root,
            )
        if (
            receipt.get("schema") != "dnadesign-data.motif-export-receipt/v1"
            or receipt.get("status") != "accepted"
            or receipt.get("motif_id") != motif_id
            or receipt.get("model_digest") != expected_model_digest
            or receipt.get("canonical_file_sha256") != sha256_bytes(artifact_bytes)
            or receipt.get("source_descriptor_id") != source.get("descriptor_id")
            or receipt.get("source_revision") != source.get("revision")
            or receipt.get("redistribution_status")
            != source.get("redistribution_status")
        ):
            raise MotifExportError("accepted receipt does not bind the admitted model")
        if formal and receipt.get("redistribution_status") != "redistributable":
            raise MotifExportError(
                "formal pools require redistributable model authority"
            )
        admitted.update(
            {
                "qualification": "accepted_owner_receipt",
                "receipt_sha256": sha256_bytes(receipt_bytes),
                "canonical_artifact_ref": receipt.get("canonical_artifact_ref"),
                "owner_revision": receipt.get("owner_revision"),
            }
        )
    else:
        admitted.update(
            {
                "qualification": "conversion_verified_pending_receipt",
                "receipt_sha256": None,
                "canonical_artifact_ref": None,
                "owner_revision": None,
            }
        )
    return admitted


def _load_exposure_ledger(
    ledger: dict[str, Any], raw: bytes
) -> tuple[set[str], set[str], set[tuple[str, ...]]]:
    if (
        set(ledger) != {"schema_version", "models", "tasks"}
        or ledger["schema_version"] != EXPOSURE_LEDGER_SCHEMA
    ):
        raise MotifExportError("development-exposure ledger schema is malformed")
    if not isinstance(ledger["models"], list) or not isinstance(ledger["tasks"], list):
        raise MotifExportError("development-exposure ledger collections must be lists")
    exposed_ids: set[str] = set()
    exposed_digests: set[str] = set()
    for raw_model in ledger["models"]:
        model = _object(raw_model, label="exposed model")
        if set(model) != {"motif_id", "model_digest"}:
            raise MotifExportError("exposed model keys are malformed")
        motif_id = validate_motif_identity(model["motif_id"], label="exposed motif_id")
        digest = _text(model["model_digest"], label="exposed model_digest")
        if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise MotifExportError("exposed model_digest must be a SHA-256 digest")
        if digest in exposed_digests:
            raise MotifExportError("development-exposure ledger repeats a model")
        exposed_ids.add(motif_id)
        exposed_digests.add(digest)
    exposed_tasks: set[tuple[str, ...]] = set()
    for raw_task in ledger["tasks"]:
        task = _object(raw_task, label="exposed task")
        if set(task) != {"motif_ids"} or not isinstance(task["motif_ids"], list):
            raise MotifExportError("exposed task keys are malformed")
        motif_ids = tuple(
            sorted(
                validate_motif_identity(item, label="exposed task motif_id")
                for item in task["motif_ids"]
            )
        )
        if len(motif_ids) < 2 or len(set(motif_ids)) != len(motif_ids):
            raise MotifExportError("exposed task must contain unique motif identities")
        exposed_tasks.add(motif_ids)
    return exposed_ids, exposed_digests, exposed_tasks


def _trusted_exposure_ledger(
    repository_root: Path,
) -> tuple[set[str], set[str], set[tuple[str, ...]], list[dict[str, str]]]:
    exposed_ids: set[str] = set()
    exposed_digests: set[str] = set()
    exposed_tasks: set[tuple[str, ...]] = set()
    authorities: list[dict[str, str]] = []
    object_path = str(EXPOSURE_LEDGER_PATH)

    def read_at(commit: str) -> bytes | None:
        size_result = run_git(
            repository_root, "cat-file", "-s", f"{commit}:{object_path}"
        )
        if size_result.returncode != 0:
            return None
        try:
            size = int(size_result.stdout.decode("ascii").strip())
        except (UnicodeDecodeError, ValueError) as exc:
            raise MotifExportError("trusted exposure ledger size is malformed") from exc
        if size < 0 or size > 1024 * 1024:
            raise MotifExportError("trusted exposure ledger exceeds its byte bound")
        blob = run_git(repository_root, "show", f"{commit}:{object_path}")
        if blob.returncode != 0 or len(blob.stdout) != size:
            raise MotifExportError("trusted exposure ledger cannot be read")
        return blob.stdout

    def parse_ledger(
        raw: bytes, *, label: str
    ) -> tuple[set[str], set[str], set[tuple[str, ...]]]:
        try:
            ledger = json.loads(raw)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise MotifExportError(f"{label} is invalid JSON") from exc
        admitted = _object(ledger, label=label)
        if raw != canonical_json_bytes(admitted):
            raise MotifExportError(f"{label} is not canonical JSON")
        return _load_exposure_ledger(admitted, raw)

    for anchor in sorted(_query_canonical_remote_revisions()):
        commit_result = run_git(repository_root, "rev-parse", f"{anchor}^{{commit}}")
        if commit_result.returncode != 0:
            continue
        commit = commit_result.stdout.decode("ascii", errors="ignore").strip()
        current_raw = read_at(commit)
        if current_raw is None:
            continue
        history_result = run_git(
            repository_root,
            "rev-list",
            "--reverse",
            "--max-count=10001",
            commit,
            "--",
            object_path,
        )
        if history_result.returncode != 0:
            raise MotifExportError("trusted exposure ledger history cannot be read")
        history = history_result.stdout.decode("ascii", errors="ignore").splitlines()
        if (
            not history
            or len(history) > 10_000
            or any(REVISION_PATTERN.fullmatch(item) is None for item in history)
        ):
            raise MotifExportError(
                "trusted exposure ledger history is malformed or unbounded"
            )
        previous: tuple[set[str], set[str], set[tuple[str, ...]]] | None = None
        for ledger_commit in history:
            historical_raw = read_at(ledger_commit)
            if historical_raw is None:
                raise MotifExportError(
                    "development-exposure ledger must remain present and append-only"
                )
            historical = parse_ledger(
                historical_raw, label="trusted exposure ledger history entry"
            )
            if previous is not None and not all(
                old <= new for old, new in zip(previous, historical, strict=True)
            ):
                raise MotifExportError(
                    "development-exposure ledger must be append-only"
                )
            previous = historical
        ids, digests, tasks = parse_ledger(current_raw, label="trusted exposure ledger")
        exposed_ids.update(ids)
        exposed_digests.update(digests)
        exposed_tasks.update(tasks)
        authorities.append(
            {"owner_revision": commit, "ledger_sha256": sha256_bytes(current_raw)}
        )
    if not authorities:
        raise MotifExportError(
            "development-exposure ledger is not reachable from an advertised integration or release anchor"
        )
    return exposed_ids, exposed_digests, exposed_tasks, authorities


def _local_exposure_ledger(
    repository_root: Path,
) -> tuple[set[str], set[str], set[tuple[str, ...]], list[dict[str, str]]]:
    ledger, raw = _load_canonical_object(
        repository_root.joinpath(*EXPOSURE_LEDGER_PATH.parts),
        label="development-exposure ledger",
    )
    ids, digests, tasks = _load_exposure_ledger(ledger, raw)
    return (
        ids,
        digests,
        tasks,
        [{"owner_revision": "local_untrusted", "ledger_sha256": sha256_bytes(raw)}],
    )


def _bundles_reachable_from_authorities(
    entries: list[object],
    *,
    repository_root: Path,
    authorities: list[dict[str, str]],
) -> bool:
    """Return whether every local bundle is byte-identical at one trusted anchor."""

    members: list[tuple[PurePosixPath, bytes]] = []
    for raw_entry in entries:
        entry = _object(raw_entry, label="model entry")
        bundle_path = _safe_relative_path(entry.get("bundle_path"))
        for member_name in ("artifact.json", "manifest.json"):
            member = bundle_path / member_name
            local_path = repository_root.joinpath(*member.parts)
            try:
                local_bytes = local_path.read_bytes()
            except OSError:
                return False
            members.append((member, local_bytes))
    return any(
        all(
            (
                result := run_git(
                    repository_root,
                    "show",
                    f"{authority['owner_revision']}:{member.as_posix()}",
                )
            ).returncode
            == 0
            and result.stdout == local_bytes
            for member, local_bytes in members
        )
        for authority in authorities
        if REVISION_PATTERN.fullmatch(authority["owner_revision"])
    )


def build_task_model_pool(
    request: dict[str, object], *, repository_root: str | Path
) -> dict[str, object]:
    """Build a path-free inventory; formal mode additionally enforces freshness."""

    validate_task_model_pool_request_shape(request)
    pool_id = _text(request["pool_id"], label="pool_id")
    pool_kind = request["pool_kind"]
    formal = pool_kind == "formal"
    freshness_authority = "development_local"
    if formal:
        try:
            exposed_ids, exposed_digests, exposed_tasks, exposure_authorities = (
                _trusted_exposure_ledger(Path(repository_root))
            )
            freshness_authority = "durable_git"
        except MotifExportError as exc:
            message = str(exc)
            if not (
                "canonical GitHub remote query failed" in message
                or "not reachable from an advertised integration or release anchor"
                in message
            ):
                raise
            exposed_ids, exposed_digests, exposed_tasks, exposure_authorities = (
                _local_exposure_ledger(Path(repository_root))
            )
            freshness_authority = "local_untrusted"
    else:
        exposed_ids, exposed_digests, exposed_tasks, exposure_authorities = (
            _local_exposure_ledger(Path(repository_root))
        )
    unlisted_exposure = (
        "not_listed"
        if freshness_authority == "durable_git"
        else "unresolved_local_untrusted"
    )
    if not isinstance(request["models"], list) or not request["models"]:
        raise MotifExportError("task-pool models must be a non-empty list")
    if (
        formal
        and freshness_authority == "durable_git"
        and not (
            _bundles_reachable_from_authorities(
                request["models"],
                repository_root=Path(repository_root),
                authorities=exposure_authorities,
            )
        )
    ):
        freshness_authority = "local_untrusted"
        (
            exposed_ids,
            exposed_digests,
            exposed_tasks,
            exposure_authorities,
        ) = _local_exposure_ledger(
            Path(repository_root),
        )
        unlisted_exposure = "unresolved_local_untrusted"
    if formal:
        requested_ids = {
            _object(item, label="model entry").get("motif_id")
            for item in request["models"]
        }
        if requested_ids & exposed_ids:
            raise MotifExportError(
                "formal candidate contains an authority-ledger development exposure"
            )
    models = sorted(
        (
            _admit_model(
                _object(item, label="model entry"),
                repository_root=Path(repository_root),
                formal=formal,
            )
            for item in request["models"]
        ),
        key=lambda item: str(item["motif_id"]),
    )
    motif_ids = [str(item["motif_id"]) for item in models]
    if len(set(motif_ids)) != len(motif_ids):
        raise MotifExportError("task-pool model identities must be unique")
    if not isinstance(request["tasks"], list) or not request["tasks"]:
        raise MotifExportError("task-pool tasks must be a non-empty list")
    tasks: list[dict[str, object]] = []
    for raw_task in request["tasks"]:
        task = _object(raw_task, label="task entry")
        if set(task) != {"task_id", "motif_ids"}:
            raise MotifExportError("task entries have incomplete or unknown fields")
        task_id = _text(task["task_id"], label="task_id")
        if _IDENTITY.fullmatch(task_id) is None:
            raise MotifExportError("task_id must be a stable identifier")
        selected = task["motif_ids"]
        if (
            not isinstance(selected, list)
            or len(selected) < 2
            or any(item not in motif_ids for item in selected)
            or len(set(selected)) != len(selected)
        ):
            raise MotifExportError(
                "task motif_ids must name at least two unique models"
            )
        exposure = (
            "development_exposed"
            if tuple(sorted(selected)) in exposed_tasks
            else unlisted_exposure
        )
        tasks.append(
            {
                "task_id": task_id,
                "motif_ids": selected,
                "development_exposure": exposure,
            }
        )
    tasks.sort(key=lambda item: str(item["task_id"]))
    if len({str(item["task_id"]) for item in tasks}) != len(tasks):
        raise MotifExportError("task identities must be unique")
    any_exposed_model = False
    for model in models:
        exposure = (
            "development_exposed"
            if model["motif_id"] in exposed_ids
            or model["model_digest"] in exposed_digests
            else unlisted_exposure
        )
        model["development_exposure"] = exposure
        any_exposed_model = any_exposed_model or exposure == "development_exposed"
    if formal and (
        any_exposed_model
        or any(task["development_exposure"] == "development_exposed" for task in tasks)
    ):
        raise MotifExportError(
            "formal candidate contains an authority-ledger development exposure"
        )
    all_receipts = all(
        model["qualification"] == "accepted_owner_receipt" for model in models
    )
    admission_status = (
        "qualification_ready"
        if formal and all_receipts and freshness_authority == "durable_git"
        else "qualification_pending"
        if formal
        else "development_only"
    )
    payload: dict[str, object] = {
        "schema_version": POOL_SCHEMA,
        "pool_id": pool_id,
        "pool_kind": pool_kind,
        "admission_status": admission_status,
        "freshness_authority": freshness_authority,
        "development_exposure_authorities": exposure_authorities,
        "models": models,
        "tasks": tasks,
    }
    payload["seal_sha256"] = sha256_bytes(canonical_json_bytes(payload).rstrip(b"\n"))
    return payload


def load_task_model_pool_request(path: str | Path) -> dict[str, object]:
    """Load one bounded canonical pool request."""

    value, _raw = _load_canonical_object(Path(path), label="task-pool request")
    return value
