"""Tokenizer-agnostic chat prompt boundary for Qwen Instruct."""

from __future__ import annotations

from typing import Any, cast


def render_assistant_prompt(tokenizer: Any, prompt: str) -> str:
    """Render the same user-to-assistant boundary for SFT and inference."""
    return cast(
        str,
        tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}],
            tokenize=False,
            add_generation_prompt=True,
        ),
    )
