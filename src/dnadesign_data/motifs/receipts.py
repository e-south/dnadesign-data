"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/motifs/receipts.py

Builds content-bound data-owner receipts for canonical motif model artifacts.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import math
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

from dnadesign_data.catalog.regulatory_parts import (
    MotifSourceFile,
    known_motif_source_files,
)
from dnadesign_data.motifs.contracts import (
    DNA_ALPHABET,
    EXPORT_SCHEMA,
    MAX_SOURCE_BYTES,
    MODEL_SCHEMA,
    MODEL_SCHEMAS,
    MotifExportError,
    model_digest,
    read_source_bytes,
    sha256_bytes,
    validate_background,
    validate_motif_identity,
    validate_probability_rows,
)
from dnadesign_data.motifs.git_authority import verify_git_authority
from dnadesign_data.motifs.io import (
    MAX_JSON_BYTES,
    load_motif_source_export_for_receipt,
)
from dnadesign_data.motifs.receipt_validation import (
    REVISION_PATTERN,
    validate_artifact_ref,
)
from dnadesign_data.motifs.replay import replay_source_conversion

_DIGEST = re.compile(r"[0-9a-f]{64}")
_CANONICAL_GIT_REMOTE = "https://github.com/e-south/dnadesign-data.git"
_EXPORT_KEYS = frozenset({"artifact", "manifest"})
_MANIFEST_KEYS = frozenset(
    {
        "schema_version",
        "provider_id",
        "output_file",
        "output_schema",
        "artifact_sha256",
        "source",
        "selection",
        "model_digest",
    }
)
_SOURCE_KEYS = frozenset(
    {
        "artifact_name",
        "artifact_sha256",
        "descriptor_id",
        "revision",
        "redistribution_status",
    }
)
_PROBABILITY_SELECTION_KEYS = frozenset({"motif_id", "source_motif_id", "prior_weight"})
_COUNT_SELECTION_KEYS = frozenset(
    {"motif_id", "source_motif_id", "background", "conversion_contract"}
)
_MODEL_KEYS = frozenset(
    {
        "schema_version",
        "motif_id",
        "alphabet",
        "probabilities",
        "background",
        "source_digest",
        "source_name",
        "conversion",
    }
)
_PROBABILITY_CONVERSION_KEYS = frozenset(
    {"schema_version", "method", "prior_weight", "source_motif_id"}
)
_COUNT_CONVERSION_KEYS = frozenset(
    {
        "schema_version",
        "method",
        "source_motif_id",
        "position_observed_counts",
        "position_prior_masses",
        "position_denominators",
    }
)


def _require_exact_keys(
    value: object, expected: frozenset[str], *, label: str
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise MotifExportError(
            f"{label} keys must be exactly: {', '.join(sorted(expected))}"
        )
    return value


def _require_text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise MotifExportError(f"{label} must be a non-empty string")
    return value


def _require_digest(value: object, *, label: str) -> str:
    text = _require_text(value, label=label)
    if _DIGEST.fullmatch(text) is None:
        raise MotifExportError(f"{label} must be a lowercase SHA-256 digest")
    return text


def _require_number(value: object, *, label: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise MotifExportError(f"{label} must be a finite number")
    return float(value)


def _validate_model_export(
    export: dict[str, dict[str, Any]], artifact_bytes: bytes
) -> tuple[dict[str, Any], dict[str, Any], str, MotifSourceFile]:
    root = _require_exact_keys(export, _EXPORT_KEYS, label="export")
    raw_manifest = root["manifest"]
    if (
        not isinstance(raw_manifest, dict)
        or raw_manifest.get("output_schema") not in MODEL_SCHEMAS
    ):
        raise MotifExportError("authority receipts require one supported motif model")
    manifest = _require_exact_keys(raw_manifest, _MANIFEST_KEYS, label="manifest")
    artifact = _require_exact_keys(root["artifact"], _MODEL_KEYS, label="motif-model")
    source = _require_exact_keys(manifest["source"], _SOURCE_KEYS, label="source")
    provider_id = manifest.get("provider_id")
    selection_keys = (
        _COUNT_SELECTION_KEYS
        if provider_id == "jaspar_count_matrix_v1"
        else _PROBABILITY_SELECTION_KEYS
    )
    selection = _require_exact_keys(
        manifest["selection"], selection_keys, label="selection"
    )

    if manifest["schema_version"] != EXPORT_SCHEMA:
        raise MotifExportError("manifest schema_version is not the export authority")
    if provider_id not in {
        "meme_probability_matrix_v1",
        "jaspar_count_matrix_v1",
    }:
        raise MotifExportError("receipt provider is not a model-producing authority")
    if manifest["output_file"] != "artifact.json":
        raise MotifExportError("manifest output_file must be artifact.json")
    if (
        artifact["schema_version"] not in MODEL_SCHEMAS
        or manifest["output_schema"] != artifact["schema_version"]
    ):
        raise MotifExportError("authority receipts require one supported motif model")

    descriptor_id = _require_text(source["descriptor_id"], label="source descriptor_id")
    descriptors = [
        item for item in known_motif_source_files() if item.source_id == descriptor_id
    ]
    if len(descriptors) != 1:
        raise MotifExportError("source catalog descriptor must resolve exactly once")
    descriptor = descriptors[0]
    if (
        descriptor.parser_hint != manifest["provider_id"]
        or descriptor.output_capability != MODEL_SCHEMA
        or source["revision"] != descriptor.release
        or source["redistribution_status"] != descriptor.redistribution_status
    ):
        raise MotifExportError(
            "source provenance disagrees with the catalog descriptor"
        )

    motif_id = validate_motif_identity(artifact["motif_id"], label="motif_id")
    source_name = _require_text(artifact["source_name"], label="source_name")
    source_digest = _require_digest(artifact["source_digest"], label="source_digest")
    if "/" in source_name or "\\" in source_name or source_name in {".", ".."}:
        raise MotifExportError("source_name must be one file basename")
    if (
        source["artifact_name"] != source_name
        or source["artifact_sha256"] != source_digest
    ):
        raise MotifExportError(
            "source cross-link disagrees between artifact and manifest"
        )
    if artifact["alphabet"] != list(DNA_ALPHABET):
        raise MotifExportError("motif-model alphabet must be exactly A/C/G/T")
    if not isinstance(artifact["background"], list):
        raise MotifExportError("motif-model background must be a list")
    background = validate_background(artifact["background"])
    if background != artifact["background"]:
        raise MotifExportError("motif-model background must already be canonical")
    if not isinstance(artifact["probabilities"], list):
        raise MotifExportError("motif-model probabilities must be a list")
    probabilities = validate_probability_rows(artifact["probabilities"])
    if probabilities != artifact["probabilities"] or any(
        probability <= 0.0 for row in probabilities for probability in row
    ):
        raise MotifExportError(
            "motif-model probabilities must be canonical and positive"
        )

    if selection["motif_id"] != motif_id:
        raise MotifExportError("selection cross-link motif_id disagrees with artifact")
    source_motif_id = validate_motif_identity(
        selection["source_motif_id"], label="selection source_motif_id"
    )
    conversion = artifact["conversion"]
    if conversion is None:
        prior_weight = _require_number(
            selection["prior_weight"], label="selection prior_weight"
        )
        if prior_weight != 0.0:
            raise MotifExportError("direct model conversion requires zero prior_weight")
        if provider_id != "meme_probability_matrix_v1":
            raise MotifExportError("count-matrix exports require conversion provenance")
        conversion_contract = "direct_probability_model_v1"
    else:
        conversion_keys = (
            _COUNT_CONVERSION_KEYS
            if provider_id == "jaspar_count_matrix_v1"
            else _PROBABILITY_CONVERSION_KEYS
        )
        conversion = _require_exact_keys(
            conversion, conversion_keys, label="conversion"
        )
        expected_method = (
            "count_matrix_sqrt_n_background_prior_v1"
            if provider_id == "jaspar_count_matrix_v1"
            else "probability_matrix_prior_mixture_v1"
        )
        expected_conversion_schema = (
            "motif-conversion/v2"
            if provider_id == "jaspar_count_matrix_v1"
            else "motif-conversion/v1"
        )
        if (
            conversion["schema_version"] != expected_conversion_schema
            or conversion["method"] != expected_method
        ):
            raise MotifExportError("motif conversion provenance is malformed")
        if conversion["source_motif_id"] != source_motif_id:
            raise MotifExportError(
                "conversion source_motif_id disagrees with selection"
            )
        if provider_id == "jaspar_count_matrix_v1":
            if artifact["schema_version"] != MODEL_SCHEMA:
                raise MotifExportError(
                    "count-matrix conversion requires the current motif-model schema"
                )
            if selection["conversion_contract"] != expected_method:
                raise MotifExportError(
                    "count conversion policy disagrees with the declared contract"
                )
            if not isinstance(selection["background"], list):
                raise MotifExportError("count selection background must be a list")
            selection_background = validate_background(selection["background"])
            if (
                selection_background != selection["background"]
                or selection_background != background
            ):
                raise MotifExportError(
                    "count selection background disagrees with the model"
                )
            position_counts = conversion["position_observed_counts"]
            position_priors = conversion["position_prior_masses"]
            position_denominators = conversion["position_denominators"]
            if (
                not isinstance(position_counts, list)
                or not isinstance(position_priors, list)
                or not isinstance(position_denominators, list)
            ):
                raise MotifExportError("count-matrix position evidence must be lists")
            admitted_counts = [
                _require_number(value, label="position observed count")
                for value in position_counts
            ]
            admitted_priors = [
                _require_number(value, label="position prior mass")
                for value in position_priors
            ]
            admitted_denominators = [
                _require_number(value, label="position denominator")
                for value in position_denominators
            ]
            if (
                len(admitted_counts) != len(probabilities)
                or len(admitted_priors) != len(probabilities)
                or len(admitted_denominators) != len(probabilities)
                or any(value <= 0.0 for value in admitted_counts)
                or any(value <= 0.0 for value in admitted_priors)
                or any(
                    abs(prior - math.sqrt(count)) > math.ulp(math.sqrt(count))
                    or abs(denominator - (count + math.sqrt(count)))
                    > math.ulp(count + math.sqrt(count))
                    for count, prior, denominator in zip(
                        admitted_counts,
                        admitted_priors,
                        admitted_denominators,
                        strict=True,
                    )
                )
            ):
                raise MotifExportError(
                    "count-matrix sqrt(N) prior provenance is malformed"
                )
            conversion_contract = "count_matrix_sqrt_n_background_prior_v1"
        else:
            prior_weight = _require_number(
                selection["prior_weight"], label="selection prior_weight"
            )
            conversion_prior = _require_number(
                conversion["prior_weight"], label="conversion prior_weight"
            )
            if conversion_prior <= 0.0 or conversion_prior != prior_weight:
                raise MotifExportError(
                    "conversion prior_weight disagrees with selection"
                )
            conversion_contract = "probability_matrix_prior_mixture_v1"

    artifact_digest = sha256_bytes(artifact_bytes)
    if (
        _require_digest(manifest["artifact_sha256"], label="artifact_sha256")
        != artifact_digest
    ):
        raise MotifExportError(
            "export artifact bytes disagree with the manifest digest"
        )
    expected_model_digest = model_digest(artifact)
    if (
        _require_digest(manifest["model_digest"], label="model_digest")
        != expected_model_digest
    ):
        raise MotifExportError("model digest disagrees with canonical scoring fields")
    return artifact, manifest, conversion_contract, descriptor


def _verify_catalog_source_bytes(
    manifest: dict[str, Any],
    descriptor: MotifSourceFile,
    *,
    data_root: str | Path,
) -> tuple[str, bytes]:
    source = manifest["source"]
    source_name = source["artifact_name"]
    authority = descriptor.absolute_path(data_root)
    ref_path = PurePosixPath(descriptor.path)
    if ref_path.is_absolute() or any(
        part in {"", ".", ".."} for part in ref_path.parts
    ):
        raise MotifExportError("catalog source path is not a safe Git-relative path")
    if descriptor.file_format in {"meme_report_glob", "jaspar_count_glob"}:
        if not Path(source_name).match(descriptor.table):
            raise MotifExportError("catalog source name does not match its descriptor")
        authority = authority / source_name
        ref_path = ref_path / source_name
    _path, raw = read_source_bytes(authority)
    if sha256_bytes(raw) != source["artifact_sha256"]:
        raise MotifExportError(
            "catalog source bytes disagree with the admitted source digest"
        )
    return str(ref_path), raw


def validate_motif_export_source_replay(
    export_dir: str | Path, *, data_root: str | Path
) -> dict[str, dict[str, Any]]:
    """Validate one model bundle and replay it without issuing owner authority."""

    export, artifact_bytes = load_motif_source_export_for_receipt(export_dir)
    artifact, manifest, _contract, descriptor = _validate_model_export(
        export, artifact_bytes
    )
    _verify_catalog_source_bytes(manifest, descriptor, data_root=data_root)
    replay_source_conversion(artifact, manifest, descriptor, data_root=data_root)
    return export


def _query_canonical_remote_revisions() -> frozenset[str]:
    """Return fixed integration and release anchors from the public owner remote."""

    try:
        result = subprocess.run(
            [
                "git",
                "ls-remote",
                "--heads",
                "--tags",
                _CANONICAL_GIT_REMOTE,
            ],
            check=False,
            capture_output=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MotifExportError("canonical GitHub remote query failed") from exc
    if result.returncode != 0 or not result.stdout:
        raise MotifExportError("canonical GitHub remote query failed")
    revisions: set[str] = set()
    try:
        lines = result.stdout.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise MotifExportError("canonical GitHub remote output is malformed") from exc
    for line in lines:
        parts = line.split("\t")
        if len(parts) != 2:
            raise MotifExportError("canonical GitHub remote output is malformed")
        revision, ref_name = parts
        if (
            REVISION_PATTERN.fullmatch(revision) is None
            or not ref_name.startswith(("refs/heads/", "refs/tags/"))
            or any(character.isspace() for character in ref_name)
        ):
            raise MotifExportError("canonical GitHub remote output is malformed")
        if ref_name == "refs/heads/main" or ref_name.startswith("refs/tags/v"):
            revisions.add(revision)
    if not revisions:
        raise MotifExportError("canonical GitHub remote output is malformed")
    return frozenset(revisions)


def build_motif_export_receipt(
    export_dir: str | Path,
    *,
    owner_revision: str,
    canonical_artifact_ref: str,
    owner_repository_path: str | Path,
    data_root: str | Path,
) -> dict[str, object]:
    """Verify and bind one canonical bundle to an existing Git authority."""

    if REVISION_PATTERN.fullmatch(owner_revision) is None:
        raise MotifExportError("owner_revision must be a 40-character Git revision")
    export, artifact_bytes = load_motif_source_export_for_receipt(export_dir)
    artifact, manifest, conversion_contract, descriptor = _validate_model_export(
        export, artifact_bytes
    )
    source_ref_path, source_bytes = _verify_catalog_source_bytes(
        manifest, descriptor, data_root=data_root
    )
    replay_source_conversion(
        artifact,
        manifest,
        descriptor,
        data_root=data_root,
    )
    source = manifest["source"]
    redistribution_status = source["redistribution_status"]
    if redistribution_status not in {"redistributable", "private_storage"}:
        raise MotifExportError(
            "accepted receipt requires resolved redistributable or private_storage status"
        )
    ref_kind, ref_path = validate_artifact_ref(
        canonical_artifact_ref, owner_revision=owner_revision
    )
    if redistribution_status == "private_storage" and ref_kind != "storage":
        raise MotifExportError(
            "private_storage inputs require a Storage artifact reference"
        )
    if ref_kind == "storage":
        raise MotifExportError(
            "Storage artifact references require a stable explicit verifier; none is configured"
        )
    verify_git_authority(
        owner_repository_path,
        owner_revision=owner_revision,
        integration_anchors=_query_canonical_remote_revisions(),
        ref_path=ref_path,
        artifact_bytes=artifact_bytes,
        artifact_max_bytes=MAX_JSON_BYTES,
        source_ref_path=source_ref_path,
        source_bytes=source_bytes,
        source_max_bytes=MAX_SOURCE_BYTES,
    )
    artifact_digest = sha256_bytes(artifact_bytes)
    required_strings = {
        "motif_id": artifact["motif_id"],
        "source_descriptor_id": source["descriptor_id"],
        "source_revision": source["revision"],
        "source_artifact_sha256": source["artifact_sha256"],
        "model_digest": manifest["model_digest"],
    }
    if any(
        not isinstance(value, str) or not value for value in required_strings.values()
    ):
        raise MotifExportError("model export provenance is incomplete")
    return {
        "schema": "dnadesign-data.motif-export-receipt/v1",
        "status": "accepted",
        "owner_repository": "e-south/dnadesign-data",
        "owner_revision": owner_revision,
        "motif_id": required_strings["motif_id"],
        "source_descriptor_id": required_strings["source_descriptor_id"],
        "source_revision": required_strings["source_revision"],
        "source_artifact_sha256": required_strings["source_artifact_sha256"],
        "canonical_artifact_ref": canonical_artifact_ref,
        "canonical_file_sha256": artifact_digest,
        "canonical_media_type": "application/json",
        "canonical_schema": artifact["schema_version"],
        "model_digest": required_strings["model_digest"],
        "conversion_contract": conversion_contract,
        "redistribution_status": redistribution_status,
    }
