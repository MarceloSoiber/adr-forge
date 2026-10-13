"""Stable ADR serialization that never manufactures decision content."""

from __future__ import annotations

from adr_forge.decisions.schemas import ADRDraft
from adr_forge.shared.hashing import canonical_json


def render_json(draft: ADRDraft) -> str:
    """Render an ADR as canonical JSON for reproducible export."""
    return canonical_json(draft.model_dump(mode="json"))


def render_markdown(draft: ADRDraft) -> str:
    """Render only fields supplied by the validated ADR, preserving list order."""
    lines = [f"# {draft.title}", "", f"Status: {draft.status}", ""]
    _section(lines, "Contexto", draft.context)
    _section(lines, "Fatos", draft.facts)
    _section(lines, "Premissas", [assumption.statement for assumption in draft.assumptions])
    _section(
        lines,
        "Questões em aberto",
        [f"{question.question} — {question.impact}" for question in draft.unresolved_questions],
    )
    _section(lines, "Restrições", draft.constraints)
    _section(
        lines,
        "Alternativas",
        [f"{alternative.name}: {alternative.summary}" for alternative in draft.alternatives],
    )
    if draft.decision:
        lines.extend(["## Decisão", "", draft.decision, ""])
    _section(lines, "Racional", [link.claim for link in draft.rationale])
    _section(lines, "Consequências positivas", draft.positive_consequences)
    _section(lines, "Consequências negativas", draft.negative_consequences)
    _section(
        lines,
        "Riscos",
        [f"{risk.description} — {risk.mitigation}" for risk in draft.risks],
    )
    _section(
        lines,
        "Gatilhos de revisão",
        [
            f"{trigger.metric} {trigger.operator} {trigger.threshold} {trigger.unit}"
            for trigger in draft.review_triggers
        ],
    )
    return "\n".join(lines).rstrip() + "\n"


def _section(lines: list[str], title: str, entries: list[str]) -> None:
    if not entries:
        return
    lines.extend([f"## {title}", ""])
    lines.extend(f"- {entry}" for entry in entries)
    lines.append("")
