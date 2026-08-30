"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/motifs/matrix.py

Converts explicit count or probability matrices without losing source form.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from dnadesign_data.motifs.contracts import (
    MotifExportError,
    validate_background,
    validate_probability_rows,
)

PROBABILITY_MIXTURE_WEIGHT = 0.1


@dataclass(frozen=True)
class MatrixConversion:
    """One source matrix and its deterministic probability projection."""

    method: str
    source_kind: str
    source_rows: tuple[tuple[float, float, float, float], ...]
    probabilities: tuple[tuple[float, float, float, float], ...]
    background: tuple[float, float, float, float]
    position_observed_counts: tuple[float, ...]
    position_prior_masses: tuple[float, ...]
    position_denominators: tuple[float, ...]


def canonical_probability_rows(
    rows: list[list[float]],
) -> list[list[float]]:
    """Normalize once, resolving binary64 cycles with one residual field."""

    admitted = validate_probability_rows(rows)
    canonical: list[list[float]] = []
    for index, row in enumerate(admitted):
        seen = {tuple(row)}
        needs_residual = False
        for _ in range(8):
            replayed = validate_probability_rows([row])[0]
            if replayed == row:
                break
            if tuple(replayed) in seen:
                needs_residual = True
                break
            seen.add(tuple(replayed))
            row = replayed
        else:
            needs_residual = True
        if not needs_residual:
            canonical.append(row)
            continue
        # Select one endpoint from the complete detected cycle before assigning
        # the residual. This makes the result independent of which adjacent
        # binary64 representation entered the canonicalizer.
        row = list(min(seen))
        residual_index = max(range(4), key=lambda item: (row[item], -item))
        other_total = math.fsum(
            value for item, value in enumerate(row) if item != residual_index
        )
        row[residual_index] = 1.0 - other_total
        for _ in range(4):
            total = math.fsum(row)
            if total == 1.0:
                break
            row[residual_index] = math.nextafter(
                row[residual_index], math.inf if total < 1.0 else -math.inf
            )
        if math.fsum(row) != 1.0 or any(
            not math.isfinite(value) or value < 0.0 for value in row
        ):
            raise MotifExportError(
                f"probability row {index} cannot be represented canonically"
            )
        canonical.append(row)
    return canonical


def _as_matrix(
    rows: list[list[float]], *, label: str
) -> tuple[tuple[float, float, float, float], ...]:
    if not rows:
        raise MotifExportError(f"{label} must contain at least one row")
    admitted: list[tuple[float, float, float, float]] = []
    for index, row in enumerate(rows):
        if len(row) != 4:
            raise MotifExportError(f"{label} row {index} must contain four values")
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0.0
            for value in row
        ):
            raise MotifExportError(
                f"{label} row {index} must contain finite nonnegative values"
            )
        admitted.append(tuple(float(value) for value in row))
    return tuple(admitted)


def count_matrix_sqrt_n_background_prior(
    rows: list[list[float]], *, background: list[float]
) -> MatrixConversion:
    """Convert counts using a total sqrt(N) prior weighted by background."""

    source_rows = _as_matrix(rows, label="count matrix")
    canonical_background = tuple(validate_background(background))
    row_counts = [math.fsum(row) for row in source_rows]
    if any(count <= 0.0 for count in row_counts):
        raise MotifExportError(
            "each count matrix row must have a positive observed count"
        )
    position_prior_masses = [math.sqrt(count) for count in row_counts]
    reconstructed = [
        [
            (
                count
                + position_prior_masses[row_index] * canonical_background[base_index]
            )
            / (row_counts[row_index] + position_prior_masses[row_index])
            for base_index, count in enumerate(row)
        ]
        for row_index, row in enumerate(source_rows)
    ]
    probabilities = canonical_probability_rows(reconstructed)
    if any(value <= 0.0 for row in probabilities for value in row):
        raise MotifExportError(
            "count matrix produced an impossible nonpositive probability"
        )
    return MatrixConversion(
        method="count_matrix_sqrt_n_background_prior_v1",
        source_kind="count_matrix",
        source_rows=source_rows,
        probabilities=tuple(tuple(row) for row in probabilities),
        background=canonical_background,
        position_observed_counts=tuple(row_counts),
        position_prior_masses=tuple(position_prior_masses),
        position_denominators=tuple(
            count + prior
            for count, prior in zip(row_counts, position_prior_masses, strict=True)
        ),
    )


def probability_matrix_background_mixture(
    rows: list[list[float]], *, background: list[float], prior_weight: float
) -> MatrixConversion:
    """Apply the versioned 0.1 background mixture to source probabilities."""

    if (
        isinstance(prior_weight, bool)
        or not isinstance(prior_weight, (int, float))
        or not math.isfinite(prior_weight)
        or prior_weight != PROBABILITY_MIXTURE_WEIGHT
    ):
        raise MotifExportError("probability-matrix prior_weight must be exactly 0.1")
    source_rows = _as_matrix(rows, label="probability matrix")
    for row in source_rows:
        validate_probability_rows([list(row)])
    canonical_background = tuple(validate_background(background))
    denominator = 1.0 + PROBABILITY_MIXTURE_WEIGHT
    reconstructed = [
        [
            (value + PROBABILITY_MIXTURE_WEIGHT * canonical_background[index])
            / denominator
            for index, value in enumerate(row)
        ]
        for row in source_rows
    ]
    probabilities = canonical_probability_rows(reconstructed)
    if any(value <= 0.0 for row in probabilities for value in row):
        raise MotifExportError(
            "probability mixture produced an impossible nonpositive probability"
        )
    return MatrixConversion(
        method="probability_matrix_prior_mixture_v1",
        source_kind="probability_matrix",
        source_rows=source_rows,
        probabilities=tuple(tuple(row) for row in probabilities),
        background=canonical_background,
        position_observed_counts=(),
        position_prior_masses=(),
        position_denominators=(),
    )
