from __future__ import annotations

import math

import pytest

from dnadesign_data.motifs.contracts import MotifExportError
from dnadesign_data.motifs.matrix import (
    canonical_probability_rows,
    count_matrix_sqrt_n_background_prior,
    probability_matrix_background_mixture,
)


def test_probability_normalization_has_one_canonical_fixed_point() -> None:
    source = [
        0.5256221888323026,
        0.1359840003048312,
        0.0680779429852171,
        0.2703158678776492,
    ]

    normalized = canonical_probability_rows([source])

    assert math.fsum(normalized[0]) == 1.0
    assert canonical_probability_rows(normalized) == normalized


def test_probability_cycle_canonicalization_is_entrypoint_independent() -> None:
    first = [
        0.5256221888323026,
        0.1359840003048312,
        0.0680779429852171,
        0.2703158678776492,
    ]
    second = [
        0.5256221888323025,
        0.13598400030483118,
        0.06807794298521709,
        0.27031586787764916,
    ]

    assert canonical_probability_rows([first]) == canonical_probability_rows([second])


def test_count_matrix_uses_background_weighted_sqrt_n_prior() -> None:
    conversion = count_matrix_sqrt_n_background_prior(
        [[4, 0, 0, 0], [4, 4, 4, 4]],
        background=[0.4, 0.1, 0.2, 0.3],
    )

    assert conversion.method == "count_matrix_sqrt_n_background_prior_v1"
    assert conversion.source_kind == "count_matrix"
    assert conversion.source_rows == (
        (4.0, 0.0, 0.0, 0.0),
        (4.0, 4.0, 4.0, 4.0),
    )
    assert conversion.position_observed_counts == (4.0, 16.0)
    assert conversion.position_prior_masses == (2.0, 4.0)
    assert conversion.position_denominators == (6.0, 20.0)
    assert conversion.probabilities[0] == pytest.approx(
        (4.8 / 6.0, 0.2 / 6.0, 0.4 / 6.0, 0.6 / 6.0)
    )
    assert conversion.probabilities[1] == pytest.approx(
        (5.6 / 20.0, 4.4 / 20.0, 4.8 / 20.0, 5.2 / 20.0)
    )
    assert all(math.fsum(row) == 1.0 for row in conversion.probabilities)


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        ([[1, 2, 3]], "four values"),
        ([[1, 2, 3, -1]], "finite nonnegative"),
        ([[1, 2, 3, float("inf")]], "finite nonnegative"),
        ([[0, 0, 0, 0]], "positive observed count"),
        ([[1, 1, 1, 1], [0, 0, 0, 0]], "positive observed count"),
    ],
)
def test_count_matrix_rejects_malformed_or_impossible_rows(
    rows: list[list[float]], message: str
) -> None:
    with pytest.raises(MotifExportError, match=message):
        count_matrix_sqrt_n_background_prior(
            rows,
            background=[0.25, 0.25, 0.25, 0.25],
        )


def test_probability_mixture_remains_a_distinct_fixed_weight_rule() -> None:
    source = [[1.0, 0.0, 0.0, 0.0]]

    conversion = probability_matrix_background_mixture(
        source,
        background=[0.4, 0.1, 0.2, 0.3],
        prior_weight=0.1,
    )

    assert conversion.method == "probability_matrix_prior_mixture_v1"
    assert conversion.source_kind == "probability_matrix"
    assert conversion.source_rows == ((1.0, 0.0, 0.0, 0.0),)
    assert conversion.position_observed_counts == ()
    assert conversion.position_prior_masses == ()
    assert conversion.position_denominators == ()
    assert conversion.probabilities[0] == pytest.approx(
        (1.04 / 1.1, 0.01 / 1.1, 0.02 / 1.1, 0.03 / 1.1)
    )
    assert source == [[1.0, 0.0, 0.0, 0.0]]


@pytest.mark.parametrize("prior_weight", [0.0, 0.2, float("nan")])
def test_probability_mixture_rejects_weights_outside_versioned_rule(
    prior_weight: float,
) -> None:
    with pytest.raises(MotifExportError, match="exactly 0.1"):
        probability_matrix_background_mixture(
            [[1.0, 0.0, 0.0, 0.0]],
            background=[0.25, 0.25, 0.25, 0.25],
            prior_weight=prior_weight,
        )
