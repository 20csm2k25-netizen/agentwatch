"""Cost computation for AI agent API usage.

This module converts token usage into USD cost. Pricing is loaded from an
external JSON file (pricing.json) rather than hardcoded, because model
pricing changes over time and historical trace records must reflect the
rate that was active when the call was made — not today's rate.

Design decisions:
- Pricing is NOT hardcoded in Python. It lives in pricing.json so it can be
  updated (or pulled from a remote URL in a future version) without a code
  release.
- cost() returns a CostResult, not a bare float, so callers always have
  access to the per-component breakdown (input/cached/output) for display
  and auditing — not just the total.
- An unknown model raises UnknownModelError rather than silently returning
  zero cost. Silent zero-cost would hide real spend from users, which is
  the exact failure mode this tool exists to prevent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

_DEFAULT_PRICING_PATH = Path(__file__).parent / "pricing.json"


class UnknownModelError(ValueError):
    """Raised when cost is requested for a model not present in the pricing table."""

    def __init__(self, model: str, known_models: list[str]) -> None:
        self.model = model
        self.known_models = known_models
        super().__init__(
            f"No pricing data for model '{model}'. "
            f"Known models: {', '.join(sorted(known_models))}. "
            f"If this is a new model, add it to pricing.json."
        )


@dataclass(frozen=True)
class CostResult:
    """Breakdown of computed cost for a single API call.

    All monetary values are in USD, computed at 6 decimal places of
    precision since individual calls can cost fractions of a cent.
    """

    model: str
    input_tokens: int
    cached_tokens: int
    output_tokens: int
    input_cost_usd: float
    cached_cost_usd: float
    output_cost_usd: float

    @property
    def total_cost_usd(self) -> float:
        return round(
            self.input_cost_usd + self.cached_cost_usd + self.output_cost_usd, 6
        )


class CostCalculator:
    """Computes USD cost from token usage using a loaded pricing table.

    Example:
        calc = CostCalculator()
        result = calc.cost(
            model="gpt-5.4",
            input_tokens=1200,
            cached_tokens=0,
            output_tokens=340,
        )
        print(result.total_cost_usd)
    """

    def __init__(self, pricing_path: str | Path | None = None) -> None:
        path = Path(pricing_path) if pricing_path else _DEFAULT_PRICING_PATH
        self._pricing_path = path
        self._rates = self._load_pricing(path)

    @staticmethod
    def _load_pricing(path: Path) -> dict[str, dict[str, float]]:
        if not path.exists():
            raise FileNotFoundError(
                f"Pricing file not found at {path}. "
                f"AgentWatch requires pricing.json to compute costs."
            )
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        models: dict[str, dict[str, float]] = data["models"]
        return models

    def reload(self) -> None:
        """Re-read the pricing file from disk. Call this if pricing.json
        has been updated at runtime without restarting the process."""
        self._rates = self._load_pricing(self._pricing_path)

    def known_models(self) -> list[str]:
        return list(self._rates.keys())

    def cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
    ) -> CostResult:
        """Compute the USD cost for a single API call.

        Args:
            model: Model identifier exactly as returned by the API
                (e.g. "gpt-5.4"). Must exist in pricing.json.
            input_tokens: Total input/prompt tokens, INCLUDING cached_tokens.
                This matches how OpenAI reports prompt_tokens — cached
                tokens are a subset of the input total, not additional.
            output_tokens: Completion/output tokens generated.
            cached_tokens: Portion of input_tokens served from cache and
                billed at the discounted cached rate. Defaults to 0.

        Returns:
            CostResult with the full cost breakdown.

        Raises:
            UnknownModelError: if `model` has no entry in the pricing table.
            ValueError: if any token count is negative, or cached_tokens
                exceeds input_tokens.
        """
        if model not in self._rates:
            raise UnknownModelError(model, self.known_models())

        if input_tokens < 0 or output_tokens < 0 or cached_tokens < 0:
            raise ValueError("Token counts cannot be negative.")
        if cached_tokens > input_tokens:
            raise ValueError(
                f"cached_tokens ({cached_tokens}) cannot exceed "
                f"input_tokens ({input_tokens})."
            )

        rates = self._rates[model]
        uncached_input_tokens = input_tokens - cached_tokens

        input_cost = (uncached_input_tokens / 1_000_000) * rates["input"]
        cached_cost = (cached_tokens / 1_000_000) * rates["cached_input"]
        output_cost = (output_tokens / 1_000_000) * rates["output"]

        return CostResult(
            model=model,
            input_tokens=input_tokens,
            cached_tokens=cached_tokens,
            output_tokens=output_tokens,
            input_cost_usd=round(input_cost, 6),
            cached_cost_usd=round(cached_cost, 6),
            output_cost_usd=round(output_cost, 6),
        )

