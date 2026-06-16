"""Multi-angle diagnostic ensemble (ADR-041 core).

The hard-24 failures (docs/hard24_gap_analysis_20260614.md) were a single reasoner skipping specific
angles: it never built a drug timeline, never ran the can't-miss exclusion, never asked "could two
things coexist," never pushed to the named gene. Universal gates only *nudge* those angles; an
ensemble *structurally forces* them — each angle is argued by an independent cheap Flash agent, then
a skeptical coordinator consolidates. This is diagnostic "dropout": if one angle whiffs, the others
still fire.

This module is the core: the angle definitions, a concurrent runner, and a consolidation step. It is
provider-agnostic (any OpenAICompatibleChatClient) and reuses the bounded-pool + rate-limit infra.
Wiring it into the eval loop (difficulty-gated, per ADR-041) is the next step.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any

from .guided_eval import parse_json_object
from .model_client import OpenAICompatibleChatClient
from .schemas import JsonSerializableMixin

# Each angle is a genuinely different route to a diagnosis (not a rephrasing), and each "owns" a
# slice of the observed failure taxonomy. Keep the prompts short and sharply scoped.
DIAGNOSTIC_ANGLES: dict[str, str] = {
    "localization": (
        "You reason ONLY by anatomic localization. Where is the lesion (cortex, white matter, "
        "basal ganglia, brainstem, cord, root, plexus, NMJ, muscle, vessel territory)? Which "
        "diagnoses localize there? Ignore the 'obvious' diagnosis; follow the localization."
    ),
    "tempo": (
        "You reason ONLY by time-course. Classify tempo (hyperacute, acute, subacute, chronic, "
        "relapsing-remitting, progressive) and let the tempo dictate the shortlist (e.g. relapsing "
        "→ channelopathy/autoimmune/vascular; rapidly progressive → prion/infectious/paraneoplastic)."
    ),
    "exposure_iatrogenic": (
        "You reason ONLY about exposures and especially MEDICATIONS. Build a drug timeline: every "
        "drug started, changed, withdrawn, or interacting; supratherapeutic levels; drug-induced "
        "deficiencies; toxins; travel; diet; occupation. Prefer a drug/interaction/withdrawal cause "
        "if the timeline fits. This angle catches the misses everyone else makes."
    ),
    "cant_miss": (
        "You hunt ONLY for treatable can't-miss emergencies that would be catastrophic to miss "
        "(HSV/infectious encephalitis, bacterial meningitis, vascular emergency, status, severe "
        "metabolic derangement, cord compression). CRITICAL: only flag one if the CASE has at least "
        "one supporting feature — do NOT list the generic can't-miss differential reflexively, and do "
        "NOT flag one that another finding already fully explains. For each you flag, cite the specific "
        "case feature that raises it and name the confirming test + empiric treatment that should not wait."
    ),
    "molecular_test": (
        "You reason ONLY about the single test or molecular result that most changes the diagnosis. "
        "For a recognizable phenotype, name the specific candidate gene/panel or marker (do not stop "
        "at 'genetic, unknown'). Say exactly which result would confirm or refute the lead."
    ),
    "common_mimic_skeptic": (
        "You assume the obvious/prototypical diagnosis is a TRAP. The vignette may have had its "
        "textbook clue removed. Argue the rarer entity that produces this same syndrome when the "
        "classic feature (fever, classic MRI, typical demographics) is absent. Name it and its "
        "distinguishing discriminator."
    ),
}


@dataclass(frozen=True)
class AngleContribution(JsonSerializableMixin):
    angle: str
    candidates: tuple[dict[str, Any], ...] = field(default_factory=tuple)  # {diagnosis, rationale, discriminator_wanted}
    proposed_queries: tuple[str, ...] = field(default_factory=tuple)
    must_exclude: tuple[str, ...] = field(default_factory=tuple)  # can't-miss flags (veto-to-investigate)
    error: str | None = None


@dataclass(frozen=True)
class EnsembleResult(JsonSerializableMixin):
    contributions: tuple[AngleContribution, ...]
    final_diagnosis: str | None
    consolidation_rationale: str | None
    discriminator_to_retrieve_next: tuple[str, ...] = field(default_factory=tuple)
    unresolved: bool = False


def build_angle_prompt(angle: str, *, case_summary: str, evidence_summary: str = "") -> str:
    instruction = DIAGNOSTIC_ANGLES[angle]
    return (
        f"You are the '{angle}' diagnostic angle in a multi-angle clinical reasoning ensemble.\n"
        f"{instruction}\n\n"
        "Stay strictly in your angle; do not try to be the whole differential. Return strict JSON:\n"
        "{\n"
        '  "candidates": [{"diagnosis": "...", "rationale": "...", "discriminator_wanted": "..."}],\n'
        '  "must_exclude": ["treatable/dangerous entity to rule out first, if any"],\n'
        '  "proposed_queries": ["a focused (<=6 term) PubMed query this angle suggests"]\n'
        "}\n\n"
        f"Case:\n{case_summary}\n"
        + (f"\nEvidence gathered so far:\n{evidence_summary}\n" if evidence_summary else "")
    )


def run_angle(
    client: OpenAICompatibleChatClient, angle: str, *, case_summary: str, evidence_summary: str = "",
    max_tokens: int = 8192,  # reasoning models burn the budget on hidden reasoning first (ADR-017)
) -> AngleContribution:
    prompt = build_angle_prompt(angle, case_summary=case_summary, evidence_summary=evidence_summary)
    try:
        result = client.chat(prompt=prompt, temperature=0.0, max_tokens=max_tokens)
        payload = parse_json_object(result.content)
    except Exception as exc:  # noqa: BLE001 - one angle failing must not sink the ensemble.
        return AngleContribution(angle=angle, error=str(exc))

    def _strs(key: str) -> tuple[str, ...]:
        v = payload.get(key)
        return tuple(s for s in v if isinstance(s, str)) if isinstance(v, list) else ()

    cands = payload.get("candidates")
    candidates = tuple(c for c in cands if isinstance(c, dict)) if isinstance(cands, list) else ()
    return AngleContribution(
        angle=angle,
        candidates=candidates,
        proposed_queries=_strs("proposed_queries"),
        must_exclude=_strs("must_exclude"),
    )


def run_angles(
    client: OpenAICompatibleChatClient, *, case_summary: str, evidence_summary: str = "",
    angles: tuple[str, ...] = tuple(DIAGNOSTIC_ANGLES), concurrency: int = 6,
) -> tuple[AngleContribution, ...]:
    """Run the angle agents concurrently (independent), returning all contributions in angle order."""
    ordered: list[AngleContribution | None] = [None] * len(angles)
    if concurrency > 1 and len(angles) > 1:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            fut_to_idx = {
                pool.submit(run_angle, client, a, case_summary=case_summary, evidence_summary=evidence_summary): i
                for i, a in enumerate(angles)
            }
            for fut in as_completed(fut_to_idx):
                ordered[fut_to_idx[fut]] = fut.result()
    else:
        ordered = [run_angle(client, a, case_summary=case_summary, evidence_summary=evidence_summary) for a in angles]
    return tuple(c for c in ordered if c is not None)


def build_consolidation_prompt(case_summary: str, contributions: tuple[AngleContribution, ...]) -> str:
    angle_views = [
        {"angle": c.angle, "candidates": list(c.candidates), "must_exclude": list(c.must_exclude)}
        for c in contributions if c.error is None
    ]
    return (
        "You are the coordinator of a multi-angle diagnostic ensemble. Each angle argued independently; "
        "consolidate into one answer. Be SKEPTICAL, not additive: a confident but unsupported candidate "
        "must not win just because several angles named it (they share the same anchoring bias). Rules:\n"
        "(1) CAN'T-MISS VETO (high priority, but grounded): lead with a treatable can't-miss entity "
        "('<entity> until excluded', next step = its confirming test + empiric treatment) ONLY when it is "
        "(a) supported by actual case features AND (b) NOT better explained by another candidate. When "
        "both hold, never bury it under a more fashionable diagnosis just because more angles favored the "
        "latter (e.g. do not bury HSV under autoimmune encephalitis) — missing the treatable one is "
        "catastrophic. But do NOT elevate a can't-miss that was only listed reflexively with no case "
        "support, or one that another finding fully explains (e.g. an encephalopathy fully explained by a "
        "supratherapeutic drug level does not need to lead with HSV) — note it for workup instead.\n"
        "(2) a candidate raised by >=2 INDEPENDENT angles (different reasoning routes) is stronger;\n"
        "(3) where angles disagree, that disagreement IS the discriminator to retrieve next;\n"
        "(4) if a recognizable phenotype points to a specific entity/gene, commit to it, not a generic category.\n\n"
        "Return strict JSON:\n"
        "{\n"
        '  "final_diagnosis": "...",\n'
        '  "consolidation_rationale": "how you weighed the angles and resolved conflict",\n'
        '  "discriminator_to_retrieve_next": ["..."],\n'
        '  "unresolved": true|false\n'
        "}\n\n"
        f"Case:\n{case_summary}\n\nAngle contributions:\n{json.dumps(angle_views, ensure_ascii=False)}\n"
    )


def consolidate(
    client: OpenAICompatibleChatClient, *, case_summary: str, contributions: tuple[AngleContribution, ...],
    max_tokens: int = 8192,  # ADR-017: reasoning budget
) -> EnsembleResult:
    prompt = build_consolidation_prompt(case_summary, contributions)
    try:
        result = client.chat(prompt=prompt, temperature=0.0, max_tokens=max_tokens)
        payload = parse_json_object(result.content)
    except Exception as exc:  # noqa: BLE001
        return EnsembleResult(contributions=contributions, final_diagnosis=None,
                              consolidation_rationale=f"consolidation failed: {exc}", unresolved=True)
    disc = payload.get("discriminator_to_retrieve_next")
    return EnsembleResult(
        contributions=contributions,
        final_diagnosis=payload.get("final_diagnosis") if isinstance(payload.get("final_diagnosis"), str) else None,
        consolidation_rationale=payload.get("consolidation_rationale") if isinstance(payload.get("consolidation_rationale"), str) else None,
        discriminator_to_retrieve_next=tuple(s for s in disc if isinstance(s, str)) if isinstance(disc, list) else (),
        unresolved=bool(payload.get("unresolved")),
    )


def run_ensemble(
    client: OpenAICompatibleChatClient, *, case_summary: str, evidence_summary: str = "",
    angles: tuple[str, ...] = tuple(DIAGNOSTIC_ANGLES), concurrency: int = 6,
) -> EnsembleResult:
    """One ensemble pass: run angles concurrently, then consolidate. Aggregates proposed queries for
    the query-strategist loop via the returned contributions."""
    contributions = run_angles(client, case_summary=case_summary, evidence_summary=evidence_summary,
                               angles=angles, concurrency=concurrency)
    return consolidate(client, case_summary=case_summary, contributions=contributions)


def aggregate_proposed_queries(contributions: tuple[AngleContribution, ...]) -> tuple[str, ...]:
    """Deduped union of the angles' proposed queries — feeds the retrieval/query-strategist loop."""
    seen: set[str] = set()
    out: list[str] = []
    for c in contributions:
        for q in c.proposed_queries:
            key = " ".join(q.lower().split())
            if key and key not in seen:
                seen.add(key)
                out.append(q)
    return tuple(out)
