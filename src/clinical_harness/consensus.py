"""Self-consistency aggregation for diagnostic answers.

The dominant residual failure mode on the Pro-failed set was run-to-run *variance*: at greedy
decoding the answer model would flip between the correct entity and a near-miss (e.g. myeloid
sarcoma vs DLBCL, Saprochaete clavata vs capitata). Self-consistency turns that variance into
signal: sample the answer model k times, cluster the final diagnoses into equivalence groups, and
take the majority. The size of the winning cluster is a free, calibrated confidence estimate.

Clustering here is deterministic and string-based (no extra model calls): two diagnoses are
grouped when their meaningful-token sets are near-identical (Jaccard >= threshold) or one is a
subset of the other. This is approximate but cheap and unit-testable; an LLM-judge clustering pass
can replace it later if needed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:  # avoid import cycle at runtime
    from .model_client import OpenAICompatibleChatClient

ModelCallRecorder = Callable[[dict[str, Any]], None]

# Qualifier / descriptor tokens that should not drive clustering (grade, stage, provisional, etc.).
_QUALIFIER_STOPWORDS = frozenset(
    {
        "a", "an", "and", "as", "associated", "benign", "case", "diagnosis", "due", "favored",
        "favor", "for", "grade", "high", "in", "likely", "low", "malignant", "most", "of", "or",
        "pending", "presenting", "primary", "probable", "provisional", "stage", "suspected", "the",
        "to", "tumor", "tumour", "type", "with", "without",
    }
)


def _tokens(diagnosis: str) -> frozenset[str]:
    text = re.sub(r"\([^)]*\)", " ", diagnosis.lower())  # drop parentheticals
    raw = re.findall(r"[a-z0-9]+", text)
    return frozenset(t for t in raw if len(t) > 2 and t not in _QUALIFIER_STOPWORDS)


def _same_entity(a: frozenset[str], b: frozenset[str], *, threshold: float) -> bool:
    if not a or not b:
        return a == b
    if a <= b or b <= a:
        return True
    inter = len(a & b)
    union = len(a | b)
    return union > 0 and inter / union >= threshold


@dataclass(frozen=True)
class ConsensusResult:
    consensus: str | None
    agreement: float  # fraction of samples in the winning cluster (0..1)
    cluster_size: int
    n_samples: int
    all_diagnoses: tuple[str, ...]


def consensus_diagnosis(diagnoses: list[str] | tuple[str, ...], *, jaccard_threshold: float = 0.6) -> ConsensusResult:
    """Majority-vote a consensus diagnosis from k samples.

    Empty/blank samples are ignored for clustering but still counted in n_samples so that
    frequent empty outputs lower the agreement score. The representative of the winning cluster is
    the most specific (most-token) diagnosis in it.
    """

    cleaned = [d.strip() for d in diagnoses if isinstance(d, str)]
    nonempty = [d for d in cleaned if d]
    n = len(cleaned)
    if not nonempty:
        return ConsensusResult(None, 0.0, 0, n, tuple(cleaned))

    token_sets = [_tokens(d) for d in nonempty]
    # Greedy single-link clustering over the k samples.
    clusters: list[list[int]] = []
    for i, ts in enumerate(token_sets):
        placed = False
        for cluster in clusters:
            if any(_same_entity(ts, token_sets[j], threshold=jaccard_threshold) for j in cluster):
                cluster.append(i)
                placed = True
                break
        if not placed:
            clusters.append([i])

    winner = max(clusters, key=len)
    # Representative = most specific (most meaningful tokens), tie-break by original order.
    rep_idx = max(winner, key=lambda i: (len(token_sets[i]), -i))
    return ConsensusResult(
        consensus=nonempty[rep_idx],
        agreement=len(winner) / n if n else 0.0,
        cluster_size=len(winner),
        n_samples=n,
        all_diagnoses=tuple(cleaned),
    )


def consensus_diagnosis_judged(
    diagnoses: list[str] | tuple[str, ...],
    judge_client: "OpenAICompatibleChatClient",
    *,
    model_call_recorder: ModelCallRecorder | None = None,
) -> ConsensusResult:
    """Cluster samples by LLM-judged clinical equivalence, not string overlap.

    This unifies abbreviation/synonym variants the string clusterer cannot (e.g. 'AML with
    t(8;21)' == 'Acute myeloid leukemia with t(8;21); RUNX1-RUNX1T1'). Seed-based to bound cost:
    each sample is compared against existing cluster representatives only. Falls back to string
    clustering on judge error.
    """

    from .judge import judge_diagnosis_equivalence  # local import to avoid cycle

    cleaned = [d.strip() for d in diagnoses if isinstance(d, str)]
    nonempty = [d for d in cleaned if d]
    n = len(cleaned)
    if not nonempty:
        return ConsensusResult(None, 0.0, 0, n, tuple(cleaned))

    clusters: list[list[int]] = []  # indices into nonempty
    reps: list[int] = []
    for i, dx in enumerate(nonempty):
        placed = False
        for c, rep in enumerate(reps):
            verdict = judge_diagnosis_equivalence(
                judge_client,
                expected=nonempty[rep],
                candidate=dx,
                model_call_recorder=model_call_recorder,
            )
            if verdict.method.startswith("judge_fallback"):
                # judge unavailable -> abandon judged clustering for a deterministic result
                return consensus_diagnosis(diagnoses)
            if verdict.score == "pass":
                clusters[c].append(i)
                placed = True
                break
        if not placed:
            clusters.append([i])
            reps.append(i)

    winner = max(clusters, key=len)
    rep_idx = max(winner, key=lambda i: (len(_tokens(nonempty[i])), -i))
    return ConsensusResult(
        consensus=nonempty[rep_idx],
        agreement=len(winner) / n if n else 0.0,
        cluster_size=len(winner),
        n_samples=n,
        all_diagnoses=tuple(cleaned),
    )
