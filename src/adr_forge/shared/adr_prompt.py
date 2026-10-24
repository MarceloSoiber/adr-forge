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
        "Gere somente um objeto JSON ADR em português. Não invente fatos. "
        "Use exatamente estas chaves em snake_case: schema_version, title, status, context, "
        "facts, assumptions, unresolved_questions, constraints, alternatives, decision, "
        "rationale, positive_consequences, negative_consequences, risks, review_triggers, "
        "confidence, reference_ids. schema_version deve ser \"adr-v1\". Não use camelCase, "
        "campos extras, null em listas ou objetos em facts e constraints. context, facts, "
        "constraints, positive_consequences, negative_consequences e reference_ids são listas "
        "de strings. Cada assumption é {id, statement, impact, confidence}; cada "
        "unresolved_question é {id, question, impact}; cada alternative é {id, name, summary, "
        "viable, rejection_reason, benefits, drawbacks, constraint_ids}; cada rationale é "
        "{claim, evidence_kind, evidence_id}; cada risk é {description, likelihood, impact, "
        "mitigation}; e cada review_trigger é {metric, operator, threshold, unit}. "
        "Para status provisional, decision deve ser null, confidence deve ser no máximo 0.60, "
        "assumptions não pode ser vazia e unresolved_questions deve conter de uma a três "
        "perguntas realmente pendentes. "
        f"Problema: {problem}\n"
        f"Fatos: {facts}\nRestrições: {constraints}\n"
        f"Alternativas candidatas: {alternatives}"
        f"{resolved_context}"
    )
