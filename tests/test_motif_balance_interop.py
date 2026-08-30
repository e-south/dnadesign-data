from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

_PYTHON = os.environ.get("DNADESIGN_DATA_MOTIF_BALANCE_PYTHON")
_EXPECTED_VERSION = os.environ.get("DNADESIGN_DATA_MOTIF_BALANCE_VERSION")
_SOURCE_ROOT = os.environ.get("DNADESIGN_DATA_MOTIF_BALANCE_SOURCE_ROOT")


@pytest.mark.skipif(
    not _PYTHON or not _EXPECTED_VERSION,
    reason="exact Motif Balance release interpreter and version are not configured",
)
def test_exact_motif_balance_release_reads_scores_and_designs_v2_models() -> None:
    """Exercise both v2 conversion lanes through one exact external product build."""

    runner = r"""
import json
import sys
from pathlib import Path
from motif_balance import DesignSpec, MotifModel, __version__, design, score

expected_version = sys.argv[1]
if __version__ != expected_version:
    raise SystemExit(f"expected Motif Balance {expected_version}, found {__version__}")
bundles = [Path(value) for value in sys.argv[2:]]
models = []
for bundle in bundles:
    artifact = MotifModel.model_validate_json((bundle / "artifact.json").read_text())
    manifest = json.loads((bundle / "manifest.json").read_text())
    if artifact.model_digest != manifest["model_digest"]:
        raise SystemExit(f"model digest mismatch for {artifact.motif_id}")
    models.append(artifact)
spec = DesignSpec(
    motifs=tuple(models),
    length=max(model.width for model in models),
    count=1,
    strands="forward",
    evaluations=64,
    seed=7,
)
evaluation = score("A" * spec.length, spec)
portfolio = design(spec)
print(json.dumps({
    "version": __version__,
    "motif_ids": [model.motif_id for model in models],
    "balance_score": evaluation.balance_score,
    "delivered_count": len(portfolio.candidates),
}, sort_keys=True))
"""
    env = os.environ.copy()
    if _SOURCE_ROOT:
        env["PYTHONPATH"] = _SOURCE_ROOT
    bundles = (
        Path(
            "generated/motif_models/jaspar-2026-counts/CTCF"  # pragma: allowlist secret
        ),
        Path("generated/motif_models/development-exposed-v2/CEBPB"),
    )

    result = subprocess.run(
        [_PYTHON, "-c", runner, _EXPECTED_VERSION, *(str(item) for item in bundles)],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    report = json.loads(result.stdout)

    assert report["version"] == _EXPECTED_VERSION
    assert report["motif_ids"] == ["CTCF", "CEBPB"]
    assert report["balance_score"] >= 0.0
    assert report["delivered_count"] == 1
