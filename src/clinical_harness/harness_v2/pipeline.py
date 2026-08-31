"""Orchestration: compose the stages into the four experiment arms. Each arm returns an ArmResult per case.

Arms (docs/HARNESS_V2_EXPERIMENTS.md):
- "bare":          ledger only, no moves (P0). Must reproduce bare pass@1..5 exactly.
- "self_critique": ledger + verified self-critique moves; NO external retrieval.
- "retrieval":     ledger + retrieval-driven moves; NO self-critique.
- "full":          ledger + self-critique + retrieval.

In every arm, proposed moves (from self-critique and/or retrieval-derived discriminators) are routed through
the verifier, then applied by the moves engine under config.policy_level. The arm flag only controls which
proposal SOURCES are active; the verifier and policy ladder are identical across arms.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Literal

from clinical_harness.guided_eval import case_from_manifest_row, load_failed_manifest
from clinical_harness.retrieval_guided_eval import _norm_dx

from . import ledger as _ledger
from . import moves as _moves
from . import retrieval as _retrieval
from . import self_critique as _self_critique
from . import verifier as _verifier
from .types import ArmResult, Discriminator, Move


def run_case(
    case_id: str,
    case_prompt: str,
    arm: Literal["bare", "self_critique", "retrieval", "full"],
    *,
    primary_model,
    reader_model,
    ncbi_client,
    config,
    bare5_response: dict | None = None,
    source_exclusion: dict | None = None,
) -> ArmResult:
    """Run one case through one arm. Reference flow (executor fills the stage bodies):

        led = _ledger.build_ledger(case_id, case_prompt, primary_model, bare5_response=bare5_response)
        proposals = []
        if arm in ("self_critique", "full"):
            proposals += _self_critique.propose_moves(led, primary_model, config)
        if arm in ("retrieval", "full") and (not config.retrieval_necessity_gate
                                             or _retrieval.retrieval_needed(led, primary_model, config)):
            q = _retrieval.generate_queries(led, primary_model, config)
            ev = _retrieval.gather_evidence(q, case_prompt, ncbi_client, reader_model, config)
            discs = _retrieval.evidence_to_discriminators(ev, led)
            proposals += _moves_from_discriminators(discs)   # executor: discriminators -> Move proposals
        verdicts = _verifier.verify_all(proposals, led, primary_model, config)
        return _moves.apply_moves(led, verdicts, config)     # bare arm => no proposals => final == bare
    """
    led = _ledger.build_ledger(case_id, case_prompt, primary_model, bare5_response=bare5_response)
    proposals: list[Move] = []
    grounding_sources: list[dict] = []
    retrieval_invoked = False
    if arm in ("self_critique", "full") and config.use_self_critique:
        proposals.extend(_self_critique.propose_moves(led, primary_model, config))
    if arm in ("retrieval", "full") and config.use_retrieval:
        setattr(config, "_current_source_exclusion", source_exclusion or {})
        if (not config.retrieval_necessity_gate) or _retrieval.retrieval_needed(led, primary_model, config):
            retrieval_invoked = True
            queries = _retrieval.generate_queries(led, primary_model, config)
            evidence = _retrieval.gather_evidence(queries, case_prompt, ncbi_client, reader_model, config)
            grounding_sources = [_compact_source(item) for item in evidence]
            discs = _retrieval.evidence_to_discriminators(evidence, led)
            proposals.extend(_moves_from_discriminators(discs, led))
    verdicts = _verifier.verify_all(proposals, led, primary_model, config)
    result = _moves.apply_moves(led, verdicts, config)
    result.arm = arm
    result.grounding_sources = grounding_sources
    result.retrieval_invoked = retrieval_invoked
    return result


def run_manifest(manifest_path: str, arm, *, primary_model, reader_model, ncbi_client, config, out_dir: str) -> list[ArmResult]:
    """Run an arm over a manifest (e.g. benchmark/development_solvable.jsonl), persisting per-case artifacts
    (proposed/applied/rejected moves, grounding sources) so every result is auditable. Scoring is done
    separately by scripts/harness_v2_eval.py."""
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    rows = load_failed_manifest(manifest_path)
    results: list[ArmResult] = []
    summary_path = root / "arm_results.jsonl"
    skip_existing = str(getattr(config, "skip_existing", True)).lower() not in {"0", "false", "no"}
    with summary_path.open("w", encoding="utf-8") as summary:
        for index, row in enumerate(rows, start=1):
            case = case_from_manifest_row(row)
            cid = row.get("case_id") or case.case_id
            case_path = root / f"{cid}.{arm}.json"
            if skip_existing and case_path.exists():
                stored = json.loads(case_path.read_text(encoding="utf-8"))
                if stored.get("error"):
                    summary.write(json.dumps(stored, sort_keys=True) + "\n")
                    summary.flush()
                    continue
                result = _arm_result_from_payload(stored)
                results.append(result)
                summary.write(json.dumps(stored, sort_keys=True) + "\n")
                summary.flush()
                continue
            try:
                bare5_response = _load_bare5(root, cid)
                result = run_case(
                    case.case_id,
                    case.prompt,
                    arm,
                    primary_model=primary_model,
                    reader_model=reader_model,
                    ncbi_client=ncbi_client,
                    config=config,
                    bare5_response=bare5_response,
                    source_exclusion={"pmcid": row.get("pmcid"), "doi": row.get("doi"), "title": row.get("title")},
                )
                payload = {
                    **asdict(result),
                    "answer_key": _answer_key_payload(row),
                    "review_status": row.get("review_status"),
                    "source_exclusion": {"pmcid": row.get("pmcid"), "doi": row.get("doi"), "title": row.get("title")},
                    "index": index,
                }
                case_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                summary.write(json.dumps(payload, sort_keys=True) + "\n")
                summary.flush()
                results.append(result)
            except Exception as exc:  # noqa: BLE001 - per-case errors must be loud and persisted.
                payload = {
                    "case_id": cid,
                    "arm": arm,
                    "error": str(exc),
                    "answer_key": _answer_key_payload(row) if row.get("answer_key") or row.get("answer_rest") else None,
                    "review_status": row.get("review_status"),
                    "index": index,
                }
                case_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                summary.write(json.dumps(payload, sort_keys=True) + "\n")
                summary.flush()
    return results


def _moves_from_discriminators(discriminators: list[Discriminator], ledger) -> list[Move]:
    moves: list[Move] = []
    for disc in discriminators:
        target_rank = _matching_rank(disc.points_to, ledger)
        evidence_tier = _evidence_tier(getattr(disc, "evidence_tier", 3))
        if disc.relation == "refutes" and target_rank is not None:
            moves.append(
                Move(
                    kind="demote",
                    tier="free",
                    target_rank=target_rank,
                    licensing=disc,
                    evidence_tier=evidence_tier,
                    note="retrieval: stated contradiction",
                )
            )
        elif disc.relation == "supports":
            if target_rank is None:
                moves.append(
                    Move(
                        kind="add_candidate",
                        tier="free",
                        new_diagnosis=disc.points_to,
                        licensing=disc,
                        evidence_tier=evidence_tier,
                        note="retrieval: literature-surfaced candidate",
                    )
                )
            else:
                candidate = next(c for c in ledger.candidates if c.rank == target_rank)
                if _looks_like_refinement(candidate.diagnosis, disc.points_to):
                    moves.append(
                        Move(
                            kind="refine_specificity",
                            tier="free",
                            target_rank=target_rank,
                            new_diagnosis=disc.points_to,
                            licensing=disc,
                            evidence_tier=evidence_tier,
                            note="retrieval: same-rank specificity repair",
                        )
                    )
    return moves


def _matching_rank(diagnosis: str, ledger) -> int | None:
    key = _norm_dx(diagnosis)
    for candidate in ledger.candidates:
        names = [candidate.diagnosis, *candidate.aliases]
        for name in names:
            n = _norm_dx(name)
            if key == n or (key and n and (key in n or n in key)):
                return candidate.rank
    return None


def _looks_like_refinement(old: str, new: str) -> bool:
    old_key = _norm_dx(old)
    new_key = _norm_dx(new)
    return bool(old_key and new_key and old_key != new_key and (old_key in new_key or new_key in old_key))


def _compact_source(item: dict) -> dict:
    return {
        "query": item.get("query"),
        "pmid": item.get("pmid"),
        "pmcid": item.get("pmcid"),
        "doi": item.get("doi"),
        "title": item.get("title"),
        "excluded": item.get("excluded", False),
        "exclusion_reason": item.get("exclusion_reason"),
        "discriminator_count": len(item.get("discriminators") or []),
        "error": item.get("error"),
    }


def _evidence_tier(value) -> int:
    try:
        tier = int(value)
    except (TypeError, ValueError):
        return 3
    return tier if 1 <= tier <= 4 else 3


def _load_bare5(root: Path, case_id: str) -> dict | None:
    for path in (
        root / f"{case_id}.bare5_response.json",
        root.parent / "bare" / f"{case_id}.bare5_response.json",
        root.parent / "bare" / f"{case_id}.bare.json",
    ):
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                return payload if isinstance(payload, dict) else None
            except json.JSONDecodeError:
                return None
    return None


def _answer_key_payload(row: dict) -> dict:
    raw = row.get("answer_key")
    if isinstance(raw, dict):
        aliases = raw.get("aliases")
        if isinstance(aliases, str):
            aliases = [aliases]
        elif not isinstance(aliases, list):
            aliases = []
        return {
            **raw,
            "aliases": [alias for alias in aliases if isinstance(alias, str) and alias.strip()],
        }
    answer_rest = row.get("answer_rest")
    if isinstance(answer_rest, str) and answer_rest.strip():
        parsed = json.loads(answer_rest)
        if isinstance(parsed, dict):
            aliases = parsed.get("aliases")
            if isinstance(aliases, str):
                aliases = [aliases]
            elif not isinstance(aliases, list):
                aliases = []
            return {
                **parsed,
                "aliases": [alias for alias in aliases if isinstance(alias, str) and alias.strip()],
            }
    raise ValueError(f"{row.get('case_id')}: missing answer_key.diagnosis")


def _arm_result_from_payload(payload: dict) -> ArmResult:
    return ArmResult(
        case_id=str(payload["case_id"]),
        arm=payload["arm"],
        bare_top5=list(payload.get("bare_top5") or []),
        final_top5=list(payload.get("final_top5") or []),
        applied_moves=[],
        rejected_moves=[],
        grounding_sources=list(payload.get("grounding_sources") or []),
        retrieval_invoked=bool(payload.get("retrieval_invoked")),
    )
