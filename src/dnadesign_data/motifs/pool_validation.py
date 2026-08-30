"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/motifs/pool_validation.py

Validates task-driven motif pool request and inventory contracts offline.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any

from dnadesign_data.motifs.contracts import (
    MotifExportError,
    canonical_json_bytes,
    model_digest,
    scoring_semantics_for_model,
    sha256_bytes,
    validate_motif_identity,
)
from dnadesign_data.motifs.pool_receipt_validation import (
    validate_offline_pool_receipt,
)
from dnadesign_data.motifs.receipt_validation import validate_artifact_ref

REQUEST_SCHEMA = "dnadesign-data.motif-task-pool-request/v1"
POOL_SCHEMA = "dnadesign-data.motif-task-pool/v1"
_IDENTITY = re.compile(r"[A-Za-z][A-Za-z0-9_.-]*")
_DIGEST = re.compile(r"[0-9a-f]{64}")
_REVISION = re.compile(r"[0-9a-f]{40}")
_MAX_POOL_MODELS = 1_000
_MAX_POOL_TASKS = 1_000
_INVENTORY_KEYS = {
    "schema_version",
    "pool_id",
    "pool_kind",
    "admission_status",
    "freshness_authority",
    "development_exposure_authorities",
    "models",
    "tasks",
    "seal_sha256",
}
_INVENTORY_MODEL_KEYS = {
    "motif_id",
    "model_schema",
    "scoring_semantics",
    "model_digest",
    "source_descriptor_id",
    "source_revision",
    "redistribution_status",
    "conversion_contract",
    "qualification",
    "receipt_sha256",
    "canonical_artifact_ref",
    "owner_revision",
    "development_exposure",
}
_MANIFEST_KEYS = {
    "schema_version",
    "provider_id",
    "output_file",
    "output_schema",
    "artifact_sha256",
    "source",
    "selection",
    "model_digest",
}
_MANIFEST_SOURCE_KEYS = {
    "artifact_name",
    "artifact_sha256",
    "descriptor_id",
    "revision",
    "redistribution_status",
}
_BUNDLE_PREFIX = PurePosixPath("generated/motif_models")
_MAX_BUNDLE_MEMBER_BYTES = 4 * 1024 * 1024


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


def _digest(value: object, *, label: str) -> str:
    digest = _text(value, label=label)
    if _DIGEST.fullmatch(digest) is None:
        raise MotifExportError(f"{label} must be a SHA-256 digest")
    return digest


class _DuplicateKeyError(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise _DuplicateKeyError(f"duplicate key {key!r}")
        value[key] = item
    return value


def _canonical_object(raw: bytes, *, label: str) -> dict[str, Any]:
    if len(raw) > _MAX_BUNDLE_MEMBER_BYTES:
        raise MotifExportError(f"{label} exceeds its byte bound")
    try:
        value = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
    except (
        UnicodeError,
        json.JSONDecodeError,
        _DuplicateKeyError,
        RecursionError,
    ) as exc:
        raise MotifExportError(f"{label} is invalid JSON: {exc}") from exc
    result = _object(value, label=label)
    if raw != canonical_json_bytes(result):
        raise MotifExportError(f"{label} must use canonical JSON bytes")
    return result


def validate_pool_bundle_path(value: object) -> str:
    path = _safe_relative_path(value)
    if (
        len(path.parts) != len(_BUNDLE_PREFIX.parts) + 2
        or path.parts[: len(_BUNDLE_PREFIX.parts)] != _BUNDLE_PREFIX.parts
    ):
        raise MotifExportError(
            "bundle_path must identify one confined generated motif bundle"
        )
    return path.as_posix()


def validate_task_model_pool_request_shape(request: dict[str, object]) -> None:
    """Validate one pool request without reading models or mutable authority."""

    if set(request) != {"schema_version", "pool_id", "pool_kind", "models", "tasks"}:
        raise MotifExportError("task-pool request keys are incomplete or unknown")
    if request["schema_version"] != REQUEST_SCHEMA:
        raise MotifExportError("task-pool request schema is unsupported")
    pool_id = _text(request["pool_id"], label="pool_id")
    if _IDENTITY.fullmatch(pool_id) is None:
        raise MotifExportError("pool_id must be a stable identifier")
    pool_kind = _text(request["pool_kind"], label="pool_kind")
    if pool_kind not in {"development", "formal"}:
        raise MotifExportError("pool_kind must be development or formal")
    models = request["models"]
    if not isinstance(models, list) or not models or len(models) > _MAX_POOL_MODELS:
        raise MotifExportError("task-pool models must be a bounded non-empty list")
    motif_ids: list[str] = []
    bundle_paths: list[str] = []
    for raw_model in models:
        model = _object(raw_model, label="model entry")
        if set(model) != {"motif_id", "bundle_path"}:
            raise MotifExportError(
                "model entries require exactly motif_id and bundle_path"
            )
        motif_ids.append(validate_motif_identity(model["motif_id"], label="motif_id"))
        bundle_paths.append(validate_pool_bundle_path(model["bundle_path"]))
    if len(set(motif_ids)) != len(motif_ids):
        raise MotifExportError("task-pool model identities must be unique")
    if len(set(bundle_paths)) != len(bundle_paths):
        raise MotifExportError("task-pool bundle paths must be unique")
    tasks = request["tasks"]
    if not isinstance(tasks, list) or not tasks or len(tasks) > _MAX_POOL_TASKS:
        raise MotifExportError("task-pool tasks must be a bounded non-empty list")
    task_ids: list[str] = []
    for raw_task in tasks:
        task = _object(raw_task, label="task entry")
        if set(task) != {"task_id", "motif_ids"}:
            raise MotifExportError("task entries have incomplete or unknown fields")
        task_id = _text(task["task_id"], label="task_id")
        if _IDENTITY.fullmatch(task_id) is None:
            raise MotifExportError("task_id must be a stable identifier")
        task_ids.append(task_id)
        selected = task["motif_ids"]
        if (
            not isinstance(selected, list)
            or len(selected) < 2
            or len(selected) > _MAX_POOL_MODELS
        ):
            raise MotifExportError(
                "task motif_ids must name at least two unique models"
            )
        selected_ids = [
            validate_motif_identity(item, label="task motif_id") for item in selected
        ]
        if any(item not in motif_ids for item in selected_ids) or len(
            set(selected_ids)
        ) != len(selected_ids):
            raise MotifExportError(
                "task motif_ids must name at least two unique models"
            )
    if len(set(task_ids)) != len(task_ids):
        raise MotifExportError("task identities must be unique")


def validate_task_model_pool_inventory_shape(inventory: dict[str, object]) -> None:
    """Validate one path-free pool inventory and its content seal offline."""

    if set(inventory) != _INVENTORY_KEYS:
        raise MotifExportError("task-pool inventory keys are incomplete or unknown")
    if inventory["schema_version"] != POOL_SCHEMA:
        raise MotifExportError("task-pool inventory schema is unsupported")
    pool_id = _text(inventory["pool_id"], label="pool_id")
    if _IDENTITY.fullmatch(pool_id) is None:
        raise MotifExportError("pool_id must be a stable identifier")
    pool_kind = _text(inventory["pool_kind"], label="pool_kind")
    admission = _text(inventory["admission_status"], label="admission_status")
    freshness = _text(inventory["freshness_authority"], label="freshness_authority")
    if pool_kind == "development":
        if admission != "development_only" or freshness != "development_local":
            raise MotifExportError("development pool state is inconsistent")
    elif pool_kind == "formal":
        if admission not in {"qualification_pending", "qualification_ready"}:
            raise MotifExportError("formal pool admission_status is unsupported")
        if freshness not in {"local_untrusted", "durable_git"}:
            raise MotifExportError("formal pool freshness_authority is unsupported")
        if admission == "qualification_ready" and freshness != "durable_git":
            raise MotifExportError("qualification_ready requires durable authority")
    else:
        raise MotifExportError("pool_kind must be development or formal")
    authorities = inventory["development_exposure_authorities"]
    if not isinstance(authorities, list) or not authorities or len(authorities) > 100:
        raise MotifExportError("development exposure authorities must be bounded")
    for raw_authority in authorities:
        authority = _object(raw_authority, label="development exposure authority")
        if set(authority) != {"owner_revision", "ledger_sha256"}:
            raise MotifExportError("development exposure authority keys are malformed")
        revision = _text(authority["owner_revision"], label="owner_revision")
        if revision != "local_untrusted" and _REVISION.fullmatch(revision) is None:
            raise MotifExportError(
                "owner_revision must be local_untrusted or a Git revision"
            )
        _digest(authority["ledger_sha256"], label="ledger_sha256")
        if (
            freshness in {"development_local", "local_untrusted"}
            and revision != "local_untrusted"
        ):
            raise MotifExportError(
                "untrusted pool authority must remain local_untrusted"
            )
        if freshness == "durable_git" and revision == "local_untrusted":
            raise MotifExportError("durable pool authority requires a Git revision")
    models = inventory["models"]
    if not isinstance(models, list) or not models or len(models) > _MAX_POOL_MODELS:
        raise MotifExportError("inventory models must be a bounded non-empty list")
    motif_ids: list[str] = []
    for raw_model in models:
        model = _object(raw_model, label="inventory model")
        if set(model) != _INVENTORY_MODEL_KEYS:
            raise MotifExportError("inventory model keys are incomplete or unknown")
        motif_ids.append(validate_motif_identity(model["motif_id"], label="motif_id"))
        schema = _text(model["model_schema"], label="model_schema")
        scoring_semantics = _text(model["scoring_semantics"], label="scoring_semantics")
        if scoring_semantics != scoring_semantics_for_model(schema):
            raise MotifExportError(
                "inventory model scoring semantics disagree with schema"
            )
        _digest(model["model_digest"], label="model_digest")
        for field in (
            "source_descriptor_id",
            "source_revision",
            "redistribution_status",
            "conversion_contract",
        ):
            _text(model[field], label=field)
        development_exposure = _text(
            model["development_exposure"], label="development_exposure"
        )
        if development_exposure not in {
            "development_exposed",
            "not_listed",
            "unresolved_local_untrusted",
        }:
            raise MotifExportError(
                "inventory model development_exposure is unsupported"
            )
        receipt_fields = (
            model["receipt_sha256"],
            model["canonical_artifact_ref"],
            model["owner_revision"],
        )
        qualification = _text(model["qualification"], label="qualification")
        if qualification == "accepted_owner_receipt":
            _digest(receipt_fields[0], label="receipt_sha256")
            revision = _text(receipt_fields[2], label="owner_revision")
            if _REVISION.fullmatch(revision) is None:
                raise MotifExportError("accepted owner_revision must be a Git revision")
            validate_artifact_ref(
                _text(receipt_fields[1], label="canonical_artifact_ref"),
                owner_revision=revision,
            )
        elif qualification == "conversion_verified_pending_receipt":
            if receipt_fields != (None, None, None):
                raise MotifExportError("pending model must not claim receipt authority")
        else:
            raise MotifExportError("inventory model qualification is unsupported")
    if len(set(motif_ids)) != len(motif_ids):
        raise MotifExportError("inventory model identities must be unique")
    tasks = inventory["tasks"]
    if not isinstance(tasks, list) or not tasks or len(tasks) > _MAX_POOL_TASKS:
        raise MotifExportError("inventory tasks must be a bounded non-empty list")
    task_ids: list[str] = []
    for raw_task in tasks:
        task = _object(raw_task, label="inventory task")
        if set(task) != {"task_id", "motif_ids", "development_exposure"}:
            raise MotifExportError("inventory task keys are incomplete or unknown")
        task_id = _text(task["task_id"], label="task_id")
        if _IDENTITY.fullmatch(task_id) is None:
            raise MotifExportError("task_id must be a stable identifier")
        task_ids.append(task_id)
        selected = task["motif_ids"]
        if not isinstance(selected, list) or len(selected) < 2:
            raise MotifExportError("inventory task motif_ids are malformed")
        selected_ids = [
            validate_motif_identity(item, label="inventory task motif_id")
            for item in selected
        ]
        if any(item not in motif_ids for item in selected_ids) or len(
            set(selected_ids)
        ) != len(selected_ids):
            raise MotifExportError("inventory task motif_ids are malformed")
        development_exposure = _text(
            task["development_exposure"], label="development_exposure"
        )
        if development_exposure not in {
            "development_exposed",
            "not_listed",
            "unresolved_local_untrusted",
        }:
            raise MotifExportError("inventory task development_exposure is unsupported")
    if len(set(task_ids)) != len(task_ids):
        raise MotifExportError("inventory task identities must be unique")
    seal = _digest(inventory["seal_sha256"], label="seal_sha256")
    unsealed = dict(inventory)
    unsealed.pop("seal_sha256")
    expected = sha256_bytes(canonical_json_bytes(unsealed).rstrip(b"\n"))
    if seal != expected:
        raise MotifExportError("task-pool inventory seal is invalid")


def validate_task_model_pool_correspondence(
    request: dict[str, object], inventory: dict[str, object]
) -> None:
    """Require one offline inventory to describe exactly one request."""

    validate_task_model_pool_request_shape(request)
    validate_task_model_pool_inventory_shape(inventory)
    if (
        request["pool_id"] != inventory["pool_id"]
        or request["pool_kind"] != inventory["pool_kind"]
    ):
        raise MotifExportError("pool request and inventory identities disagree")
    requested_models = {
        _object(item, label="model entry")["motif_id"]
        for item in _list(request["models"], label="request models")
    }
    inventoried_models = {
        _object(item, label="inventory model")["motif_id"]
        for item in _list(inventory["models"], label="inventory models")
    }
    if requested_models != inventoried_models:
        raise MotifExportError("pool request and inventory model identities disagree")
    requested_tasks = {
        task["task_id"]: tuple(_list(task["motif_ids"], label="task motif_ids"))
        for item in _list(request["tasks"], label="request tasks")
        for task in (_object(item, label="task entry"),)
    }
    inventoried_tasks = {
        task["task_id"]: tuple(_list(task["motif_ids"], label="task motif_ids"))
        for item in _list(inventory["tasks"], label="inventory tasks")
        for task in (_object(item, label="inventory task"),)
    }
    if requested_tasks != inventoried_tasks:
        raise MotifExportError("pool request and inventory task identities disagree")


def validate_task_model_pool_local_bundles(
    request: dict[str, object],
    inventory: dict[str, object],
    bundles: Mapping[str, Mapping[str, bytes]],
) -> None:
    """Bind every inventory model to already-read, confined local bundle bytes."""

    validate_task_model_pool_correspondence(request, inventory)
    inventory_models = {
        model["motif_id"]: model
        for item in _list(inventory["models"], label="inventory models")
        for model in (_object(item, label="inventory model"),)
    }
    for item in _list(request["models"], label="request models"):
        requested = _object(item, label="model entry")
        motif_id = validate_motif_identity(requested["motif_id"], label="motif_id")
        bundle_path = validate_pool_bundle_path(requested["bundle_path"])
        members = bundles.get(bundle_path)
        if members is None:
            raise MotifExportError(
                f"bundle_path {bundle_path!r} does not resolve to a local motif bundle"
            )
        expected = _local_bundle_inventory_fields(
            motif_id=motif_id,
            bundle_path=bundle_path,
            members=members,
        )
        observed = inventory_models[motif_id]
        qualification_fields = {
            "qualification",
            "receipt_sha256",
            "canonical_artifact_ref",
            "owner_revision",
        }
        if any(observed[field] != expected[field] for field in qualification_fields):
            raise MotifExportError(
                f"inventory model {motif_id!r} disagrees with local bundle qualification"
            )
        metadata_fields = {
            "motif_id",
            "model_schema",
            "scoring_semantics",
            "model_digest",
            "source_descriptor_id",
            "source_revision",
            "redistribution_status",
            "conversion_contract",
        }
        if any(observed[field] != expected[field] for field in metadata_fields):
            raise MotifExportError(
                f"inventory model {motif_id!r} disagrees with local bundle metadata"
            )


def _local_bundle_inventory_fields(
    *, motif_id: str, bundle_path: str, members: Mapping[str, bytes]
) -> dict[str, object]:
    allowed = {"artifact.json", "manifest.json", "receipt.json"}
    if (
        not {"artifact.json", "manifest.json"} <= set(members)
        or not set(members) <= allowed
    ):
        raise MotifExportError(f"local motif bundle {bundle_path!r} is incomplete")
    artifact_raw = members["artifact.json"]
    manifest_raw = members["manifest.json"]
    artifact = _canonical_object(artifact_raw, label="local motif artifact")
    manifest = _canonical_object(manifest_raw, label="local motif manifest")
    if set(manifest) != _MANIFEST_KEYS:
        raise MotifExportError("local motif manifest keys are incomplete or unknown")
    source = _object(manifest["source"], label="local motif manifest source")
    if set(source) != _MANIFEST_SOURCE_KEYS:
        raise MotifExportError("local motif manifest source keys are malformed")
    if artifact.get("motif_id") != motif_id:
        raise MotifExportError("request motif_id disagrees with its local artifact")
    schema = _text(artifact.get("schema_version"), label="model schema")
    try:
        scientific_digest = model_digest(artifact)
    except (KeyError, TypeError, ValueError) as exc:
        raise MotifExportError("local motif artifact is not a valid model") from exc
    if (
        manifest["schema_version"] != "dnadesign-data.motif-source-export/v1"
        or manifest["output_file"] != "artifact.json"
        or manifest["output_schema"] != schema
        or manifest["artifact_sha256"] != sha256_bytes(artifact_raw)
        or manifest["model_digest"] != scientific_digest
        or artifact.get("source_digest") != source.get("artifact_sha256")
    ):
        raise MotifExportError("local motif manifest does not bind its artifact")
    conversion = artifact.get("conversion")
    conversion_contract = (
        _text(conversion.get("method"), label="conversion method")
        if isinstance(conversion, dict)
        else "direct_probability_model_v1"
    )
    expected: dict[str, object] = {
        "motif_id": motif_id,
        "model_schema": schema,
        "scoring_semantics": scoring_semantics_for_model(schema),
        "model_digest": scientific_digest,
        "source_descriptor_id": _text(
            source.get("descriptor_id"), label="source descriptor_id"
        ),
        "source_revision": _text(source.get("revision"), label="source revision"),
        "redistribution_status": _text(
            source.get("redistribution_status"), label="redistribution_status"
        ),
        "conversion_contract": conversion_contract,
    }
    receipt_raw = members.get("receipt.json")
    if receipt_raw is None:
        expected.update(
            {
                "qualification": "conversion_verified_pending_receipt",
                "receipt_sha256": None,
                "canonical_artifact_ref": None,
                "owner_revision": None,
            }
        )
        return expected
    receipt = _canonical_object(receipt_raw, label="local motif receipt")
    validate_offline_pool_receipt(
        receipt,
        artifact_raw=artifact_raw,
        artifact=artifact,
        bundle_path=bundle_path,
        manifest=manifest,
        source=source,
        conversion_contract=conversion_contract,
        motif_id=motif_id,
    )
    expected.update(
        {
            "qualification": "accepted_owner_receipt",
            "receipt_sha256": sha256_bytes(receipt_raw),
            "canonical_artifact_ref": receipt["canonical_artifact_ref"],
            "owner_revision": receipt["owner_revision"],
        }
    )
    return expected


def _list(value: object, *, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise MotifExportError(f"{label} must be a list")
    return value
