"""Tier 1 (docs/testing-design.md, moved up from Tier 2): db.py's
est_cost_usd() -- pure arithmetic given a model name and token counts,
no fixture file needed. The test that matters most: an unrecognized
model must raise (UnknownModelError), never silently return a $0
estimate -- the exact failure mode this function was deliberately built
to avoid (05-monitoring/notes/03_common_pitfalls.md #2)."""

import pytest

from db import MODEL_RATES_PER_1K, UnknownModelError, est_cost_usd


def test_est_cost_usd_normal_case_arithmetic():
    rates = MODEL_RATES_PER_1K["gpt-5.4-mini"]
    cost = est_cost_usd("gpt-5.4-mini", prompt_tokens=2000, completion_tokens=500)
    expected = (2000 / 1000) * rates["prompt"] + (500 / 1000) * rates["completion"]
    assert cost == pytest.approx(expected)


def test_est_cost_usd_zero_tokens_is_zero_cost():
    assert est_cost_usd("gpt-5.4-mini", prompt_tokens=0, completion_tokens=0) == 0.0


def test_est_cost_usd_different_known_model():
    rates = MODEL_RATES_PER_1K["gpt-5.4"]
    cost = est_cost_usd("gpt-5.4", prompt_tokens=1000, completion_tokens=1000)
    expected = 1.0 * rates["prompt"] + 1.0 * rates["completion"]
    assert cost == pytest.approx(expected)


def test_est_cost_usd_raises_on_unrecognized_model_instead_of_silently_zeroing():
    with pytest.raises(UnknownModelError):
        est_cost_usd("gpt-9000-nonexistent", prompt_tokens=100, completion_tokens=100)


def test_est_cost_usd_unknown_model_error_message_names_the_model():
    with pytest.raises(UnknownModelError, match="gpt-9000-nonexistent"):
        est_cost_usd("gpt-9000-nonexistent", prompt_tokens=1, completion_tokens=1)
