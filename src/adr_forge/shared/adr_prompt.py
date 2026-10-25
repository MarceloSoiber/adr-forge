"""Stable prompt contract shared by structured training and inference."""

from __future__ import annotations

import json
from typing import Any


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
            "As perguntas e respostas acima estão resolvidas: não as reformule nem peça o mesmo "
            "esclarecimento com outras palavras. "
            "Se as evidências forem suficientes, conclua o ADR; caso contrário, "
            "pergunte somente sobre lacunas novas."
        )
    return (
        "Gere somente um objeto JSON ADR em português. Comece com { e termine com }; não use "
        "blocos Markdown, notas, explicações ou qualquer texto antes ou depois do JSON. "
        "Não invente fatos. "
        "Use exatamente estas chaves em snake_case: schema_version, title, status, context, "
        "facts, assumptions, unresolved_questions, constraints, alternatives, decision, "
        "rationale, positive_consequences, negative_consequences, risks, review_triggers, "
        "confidence, reference_ids. schema_version deve ser \"adr-v1\". Não use camelCase, "
        "campos extras, null em listas ou objetos em facts e constraints. context, facts, "
        "constraints, positive_consequences, negative_consequences e reference_ids são listas "
        "de strings. context deve conter pelo menos um item e resumir o Problema fornecido; "
        "constraints deve conter somente textos, nunca objetos com id/text. Cada assumption é "
        "{id, statement, impact, confidence}; cada "
        "unresolved_question é {id, question, impact}; cada alternative é {id, name, summary, "
        "viable, rejection_reason, benefits, drawbacks, constraint_ids}; cada rationale é "
        "{claim, evidence_kind, evidence_id}; cada risk é {description, likelihood, impact, "
        "mitigation}; e cada review_trigger é {metric, operator, threshold, unit}. "
        "Em risk, likelihood e impact aceitam somente as strings \"low\", \"medium\" ou "
        "\"high\"; nunca use números. Em review_trigger, operator aceita somente \"gt\", "
        "\"gte\", \"lt\", \"lte\" ou \"eq\"; nunca use símbolos como > ou <=. "
        "Em rationale, evidence_kind aceita somente \"fact\", \"assumption\", \"constraint\" "
        "ou \"reference\"; "
        "nunca use \"decision_boundary\" ou outro valor. evidence_id deve apontar para um ID "
        "existente: fatos usam \"fact:0\", \"fact:1\" etc.; assumptions usam o id da assumption; "
        "restrições usam \"constraint:0\", \"constraint:1\" etc.; references usam um valor "
        "presente em reference_ids. "
        "Para status provisional, decision deve ser null, confidence deve ser no máximo 0.60, "
        "a confidence de cada assumption deve ser um número entre 0 e 1, nunca low, medium ou "
        "high; assumptions não pode ser vazia e unresolved_questions deve conter de uma a três "
        "perguntas realmente pendentes; [] é inválido. Antes de responder, confira essa regra. "
        f"Problema: {problem}\n"
        f"Fatos: {facts}\nRestrições: {constraints}\n"
        f"Alternativas candidatas: {alternatives}"
        f"{resolved_context}"
    )


def build_adr_repair_prompt(
    adr_contract: str, raw_output: str, findings: list[dict[str, Any]]
) -> str:
    """Ask for one auditable correction without changing the original output locally."""
    return (
        f"{adr_contract}\n\n"
        "Corrija a resposta ADR abaixo e retorne somente o objeto JSON ADR completo em português. "
        "Comece com { e termine com }; remova notas, explicações e qualquer texto fora do JSON. "
        "com schema_version \"adr-v1\". "
        "Não invente fatos: para uma lacuna real, use status provisional com assumptions e de uma "
        "a três unresolved_questions; nunca retorne unresolved_questions vazio para provisional. "
        "Cada item de unresolved_questions deve ser um objeto JSON, nunca uma string, exatamente "
        "no formato {\"id\":\"pergunta-1\",\"question\":\"...\",\"impact\":\"...\"}. "
        "context deve conter pelo menos um texto baseado no Problema fornecido. constraints deve "
        "ser uma lista de strings, nunca objetos com id/text. "
        "A confidence de cada assumption deve ser numérica entre 0 e 1, nunca low, medium ou "
        "high. Não repita em unresolved_questions nenhuma pergunta já respondida no contexto. "
        "Em rationale, evidence_kind deve ser somente \"fact\", \"assumption\", \"constraint\" "
        "ou \"reference\". "
        "Converta likelihood e impact numéricos para \"low\", \"medium\" ou \"high\"; converta "
        "operadores simbólicos para \"gt\", \"gte\", \"lt\", \"lte\" ou \"eq\"; e use "
        "evidence_id \"fact:0\", \"fact:1\" etc. ao referenciar fatos. "
        "Mantenha os fatos fornecidos quando forem válidos.\n"
        f"Resposta original:\n{raw_output}\n"
        "Erros de validação a corrigir:\n"
        f"{json.dumps(findings, ensure_ascii=False)}"
    )
