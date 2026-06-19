import pytest

from agentwatch.cost import CostCalculator, CostResult, UnknownModelError


def test_known_model_costs():
    calc = CostCalculator()
    # use gpt-5.4 from pricing.json: input=2.50 per 1M, output=15 per 1M
    res: CostResult = calc.cost("gpt-5.4", input_tokens=1_000_000, output_tokens=1_000_000)
    assert res.input_cost_usd == pytest.approx(2.5, rel=1e-6)
    assert res.output_cost_usd == pytest.approx(15.0, rel=1e-6)
    assert res.total_cost_usd == pytest.approx(17.5, rel=1e-6)


def test_cached_tokens_billed_at_discounted_rate():
    calc = CostCalculator()
    # 1_000_000 input tokens, 200_000 cached. uncached=800_000
    res = calc.cost("gpt-5.5", input_tokens=1_000_000, cached_tokens=200_000, output_tokens=0)
    # gpt-5.5 input=5.0 per 1M, cached_input=0.5 per 1M
    expected_uncached = (800_000 / 1_000_000) * 5.0
    expected_cached = (200_000 / 1_000_000) * 0.5
    assert res.input_cost_usd == pytest.approx(round(expected_uncached, 6))
    assert res.cached_cost_usd == pytest.approx(round(expected_cached, 6))


def test_cached_cannot_exceed_input():
    calc = CostCalculator()
    with pytest.raises(ValueError):
        calc.cost("gpt-5.4", input_tokens=100, cached_tokens=200, output_tokens=0)


def test_negative_token_counts_rejected():
    calc = CostCalculator()
    with pytest.raises(ValueError):
        calc.cost("gpt-5.4", input_tokens=-1, cached_tokens=0, output_tokens=0)


def test_unknown_model_raises():
    calc = CostCalculator()
    with pytest.raises(UnknownModelError):
        calc.cost("not-a-model", input_tokens=10, cached_tokens=0, output_tokens=0)
