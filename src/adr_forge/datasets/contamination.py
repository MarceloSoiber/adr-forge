"""Deterministic duplicate and lineage split-leak detection."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from adr_forge.datasets.models import DatasetExample
from adr_forge.datasets.versioning import DatasetMembership, DatasetSplit


@dataclass(frozen=True)
class ContaminationFinding:
    kind: str
    blocking: bool
    example_ids: tuple[str, ...]
    detail: str


def _normalise(value: str) -> str:
    return re.sub(r"\W+", "", value.casefold())


def detect_contamination(
    memberships: Iterable[DatasetMembership], examples: Iterable[DatasetExample] | None = None
) -> list[ContaminationFinding]:
    members = list(memberships)
    findings: list[ContaminationFinding] = []
    by_group: dict[str, set[DatasetSplit]] = defaultdict(set)
    for member in members:
        by_group[member.lineage_group_id].add(member.split)
    for group, splits in sorted(by_group.items()):
        if DatasetSplit.EVALUATION in splits and splits - {DatasetSplit.EVALUATION}:
            findings.append(ContaminationFinding("lineage_split_leak", True, (), group))
    if examples is None:
        return findings
    by_hash: dict[str, list[DatasetExample]] = defaultdict(list)
    by_normalised: dict[str, list[DatasetExample]] = defaultdict(list)
    for example in examples:
        by_hash[example.content_hash].append(example)
        by_normalised[_normalise(example.prompt + example.completion)].append(example)
    for kind, groups in (("exact_duplicate", by_hash), ("normalized_duplicate", by_normalised)):
        for group in groups.values():
            if len(group) > 1:
                findings.append(
                    ContaminationFinding(
                        kind,
                        True,
                        tuple(sorted(str(item.id) for item in group)),
                        "duplicate example content",
                    )
                )
    return findings
