"""Stable prompt contract shared by structured training and inference."""

from __future__ import annotations


def build_adr_prompt(
    problem: str,
    facts: list[str],
    constraints: list[str],
    alternatives: list[str],
    clarification_answers: list[str] | None = None,
) -> str:
    """Request only a JSON ADR without adding ungrounded context."""
    resolved_context = ""
    if clarification_answers:
        resolved_context = (
            "\nEsclarecimentos já respondidos pelo usuário (trate como evidência do cenário):\n"
            + "\n".join(f"- {answer}" for answer in clarification_answers)
            + "\nNão repita perguntas que já tenham uma resposta acima. "
            "Se as evidências forem suficientes, conclua o ADR; caso contrário, "
            "pergunte somente sobre lacunas novas."
        )
    return (
        "Gere somente JSON para um ADR em português. Não invente fatos. "
        f"Problema: {problem}\n"
        f"Fatos: {facts}\nRestrições: {constraints}\n"
        f"Alternativas candidatas: {alternatives}"
        f"{resolved_context}"
    )
