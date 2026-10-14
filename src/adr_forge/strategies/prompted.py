"""Versioned structured-prompt strategy composition."""

from __future__ import annotations

from adr_forge.strategies.base import StrategyInput, build_adr_prompt


def build_structured_prompt(strategy_input: StrategyInput) -> str:
    return build_adr_prompt(strategy_input.scenario) + "\nVersão do prompt: " + strategy_input.prompt_version
