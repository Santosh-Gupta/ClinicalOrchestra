"""Stored diagnostic knowledge pack (specific, niche augmentations).

Rare-entity discriminators cannot live in model weights or a generic prompt — there are thousands and
they are exactly what models get wrong (anchoring on a near-neighbor). This is the project's own small,
growing knowledge base: each **card** captures one teaching point distilled from a real case/paper —
trigger features -> the specific entity to consider -> the discriminator -> the confirmatory test ->
a source PMID. Cards are matched to a case by feature overlap and the top matches are injected into the
prompt as "specific entities to consider," with their citations (so the cited report stays honest).

Seeded from the 24 hardest failures (docs/augmentation_catalog_20260614.md). Grow it every time a hard
case teaches a new niche discriminator — this is how specific knowledge accumulates without bloating
the prompt or relying on the model's memory.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_STOPWORDS = frozenset(
    {
        "the", "and", "with", "without", "for", "from", "this", "that", "patient", "case", "normal",
        "after", "before", "their", "than", "into", "over", "onset", "year", "old", "history",
    }
)

# Generic single-word features that appear in many neuro cases — they can add to a card's score but
# must NOT be the sole reason a card fires (that caused irrelevant cards to inject). A card qualifies
# only on a *specific* trigger: a multi-word phrase, or a distinctive single word not in this set.
_GENERIC_TRIGGERS = frozenset(
    {
        "tremor", "ataxia", "seizures", "cerebellar", "cognitive", "psychiatric", "headache", "fever",
        "parkinsonism", "infant", "young", "stroke", "encephalitis", "encephalopathy", "confusion",
        "weakness", "epilepsy", "spasticity",
    }
)


@dataclass(frozen=True)
class KnowledgeCard:
    entity: str
    triggers: tuple[str, ...]            # feature phrases that should raise this entity
    discriminator: str                   # what distinguishes it from its near-neighbors
    confirmatory_test: str               # the test/finding that confirms it
    near_neighbors: tuple[str, ...] = ()  # the wrong answers it is commonly confused with
    source_pmid: str | None = None
    source_pmcid: str | None = None

    def to_prompt_dict(self) -> dict[str, Any]:
        return {
            "consider_entity": self.entity,
            "raised_by": list(self.triggers),
            "discriminator_vs_near_neighbors": self.discriminator,
            "often_confused_with": list(self.near_neighbors),
            "confirmatory_test": self.confirmatory_test,
            "source_pmid": self.source_pmid,
        }


# Seed cards. Keep triggers as lowercase feature phrases found in the *presentation* (never the answer).
KNOWLEDGE_CARDS: tuple[KnowledgeCard, ...] = (
    KnowledgeCard(
        entity="SLC6A1-related neurodevelopmental disorder",
        triggers=("absence seizures", "typical absence", "spike and wave", "developmental delay", "mild cognitive", "myoclonic atonic"),
        discriminator="typical absences as the main seizure type + even mild cognitive deficit, normal MRI, GLUT1/SLC2A1 negative",
        confirmatory_test="SLC6A1 sequencing / epilepsy gene panel",
        near_neighbors=("idiopathic absence epilepsy", "GLUT1 deficiency"),
        source_pmcid="PMC10339345",
    ),
    KnowledgeCard(
        entity="Drug-induced parkinsonism",
        triggers=("parkinsonism", "bradykinesia", "tremor", "antipsychotic", "valproate", "lamotrigine", "datscan"),
        discriminator="a NORMAL DaTscan (intact presynaptic dopaminergic terminals) points to drug-induced/functional, NOT neurodegenerative parkinsonism, even if a predisposing genetic syndrome is present",
        confirmatory_test="normal DaTscan + improvement on stopping the offending drug",
        near_neighbors=("Parkinson's disease", "genetic/neurodegenerative parkinsonism"),
        source_pmcid="PMC11631938",
    ),
    KnowledgeCard(
        entity="Early-onset autosomal-recessive Parkinson's disease (PARK genes: DJ-1/PARK7, PINK1, Parkin)",
        triggers=("early onset", "parkinsonism", "spasticity", "cognitive", "young", "consanguin"),
        discriminator="young parkinsonism + spasticity + cognitive change suggests a recessive PARK gene; do not default to SPG7 just because spasticity is present",
        confirmatory_test="recessive PD gene panel (PARK7/DJ-1, PINK1, PRKN)",
        near_neighbors=("SPG7 hereditary spastic paraplegia",),
        source_pmcid="PMC11138152",
    ),
    KnowledgeCard(
        entity="SCA12 (spinocerebellar ataxia type 12, PPP2R2B CAG expansion)",
        triggers=("tremor", "ataxia", "essential tremor", "postural tremor", "cerebellar"),
        discriminator="mixed postural/kinetic tremor with resting component +/- hippocampal atrophy; a repeat-expansion ataxia — test SCA12 (CAG) AND FXTAS (FMR1 premutation), do not pick one blindly",
        confirmatory_test="PPP2R2B CAG repeat testing (and FMR1 premutation to exclude FXTAS)",
        near_neighbors=("FXTAS", "essential tremor"),
        source_pmcid="PMC12971692",
    ),
    KnowledgeCard(
        entity="SPG4 hereditary spastic paraplegia (SPAST)",
        triggers=("spastic", "spasticity", "lower limb", "paraplegia", "quadriplegia", "progressive gait"),
        discriminator="progressive lower-limb (or quadriplegic) spasticity → SPAST/SPG4 is the commonest autosomal-dominant HSP; not an epilepsy gene",
        confirmatory_test="SPAST sequencing / HSP gene panel",
        near_neighbors=("CDKL5 deficiency", "other epileptic encephalopathy genes"),
        source_pmcid="PMC13126082",
    ),
    KnowledgeCard(
        entity="ATP1A3-related relapsing encephalopathy with cerebellar ataxia (RECA)",
        triggers=("relapsing", "recurrent encephalopathy", "fever", "cerebellar ataxia", "areflexia"),
        discriminator="RELAPSING, fever-triggered encephalopathy with cerebellar ataxia → ATP1A3 spectrum (AHC/RDP/CAPOS/RECA), not a generic 'mitochondrial' label",
        confirmatory_test="ATP1A3 sequencing",
        near_neighbors=("mitochondrial disorder", "NAXE/ISCA2 deficiency"),
        source_pmcid="PMC13183691",
    ),
    KnowledgeCard(
        entity="Asparagine synthetase deficiency (ASNSD, ASNS)",
        triggers=("microcephaly", "iugr", "intrauterine growth", "refractory epilepsy", "encephalopathy", "psychomotor"),
        discriminator="congenital microcephaly + IUGR + progressive encephalopathy + refractory epilepsy + characteristic neuroimaging → ASNS, not Fryns",
        confirmatory_test="ASNS sequencing",
        near_neighbors=("Fryns syndrome", "GPI-anchor biosynthesis defect"),
        source_pmcid="PMC12104238",
    ),
    KnowledgeCard(
        entity="KCNMA1-related developmental and epileptic encephalopathy",
        triggers=("epileptic encephalopathy", "fever", "developmental delay", "seizures", "infant"),
        discriminator="fever-associated DEE with a de novo channel variant; consider KCNMA1 (BK channel) on WES, not only pyridoxine-dependent epilepsy",
        confirmatory_test="whole-exome sequencing (KCNMA1)",
        near_neighbors=("pyridoxine-dependent epilepsy (ALDH7A1)",),
        source_pmcid="PMC13233052",
    ),
    KnowledgeCard(
        entity="Steroid-responsive encephalopathy associated with autoimmune thyroiditis (SREAT/Hashimoto)",
        triggers=("subacute encephalopathy", "confusion", "cognitive decline", "psychiatric", "steroid responsive", "tremor"),
        discriminator="unexplained subacute encephalopathy → check ANTITHYROID antibodies (TPO/Tg); SREAT is steroid-responsive and reversible, often mistaken for antibody-specific AE",
        confirmatory_test="anti-TPO / anti-thyroglobulin antibodies + steroid response",
        near_neighbors=("anti-GAD65 autoimmune encephalitis", "other antibody AE"),
        source_pmcid="PMC13162229",
    ),
    KnowledgeCard(
        entity="Anti-DPPX antibody encephalitis",
        triggers=("encephalitis", "diarrhea", "weight loss", "abdominal pain", "hyperexcitability", "psychiatric"),
        discriminator="autoimmune encephalitis with a prominent GI prodrome (diarrhea/weight loss/abdominal pain) + CNS hyperexcitability → DPPX, not acute intermittent porphyria",
        confirmatory_test="serum/CSF DPPX antibodies",
        near_neighbors=("acute intermittent porphyria",),
        source_pmcid="PMC13260868",
    ),
    KnowledgeCard(
        entity="Cervical artery dissection with intracranial extension",
        triggers=("young", "stroke", "subarachnoid hemorrhage", "neck pain", "headache", "thunderclap"),
        discriminator="young patient with stroke AND subarachnoid hemorrhage → cervical artery dissection (vessel-wall imaging shows the flap/hematoma) before invoking PACNS",
        confirmatory_test="vessel-wall MRI / CTA / DSA for the dissection",
        near_neighbors=("primary angiitis of the CNS (PACNS)",),
        source_pmcid="PMC3011101",
    ),
)


def _terms(text: str | None) -> set[str]:
    if not text:
        return set()
    toks = re.findall(r"[a-z0-9]+", text.lower())
    return {t for t in toks if len(t) > 2 and t not in _STOPWORDS}


def match_cards(case_text: str, *, max_cards: int = 2, min_score: int = 4) -> tuple[KnowledgeCard, ...]:
    """Return the knowledge cards whose triggers best match the case presentation.

    PRECISION over recall: injecting the wrong rare-entity card actively anchors the model, so a card
    qualifies only when it has at least one **full trigger-phrase** substring match AND clears
    ``min_score`` (phrase match = 2, strong token overlap = 1). This keeps generic single-word
    coincidences (every neuro case has "seizures"/"tremor") from pulling in irrelevant cards. Uses only
    the case presentation text — never the answer key.
    """
    text = (case_text or "").lower()
    case_tokens = _terms(case_text)
    scored: list[tuple[int, KnowledgeCard]] = []
    for card in KNOWLEDGE_CARDS:
        score = 0
        specific_hit = False
        counted: set[str] = set()  # dedupe: a case token contributes to a card's score only once
        for trig in card.triggers:
            tl = trig.lower()
            multiword = len(trig.split()) >= 2
            specific = multiword or tl not in _GENERIC_TRIGGERS
            if tl in text:
                new_tokens = _terms(trig) - counted
                if new_tokens:
                    score += 2 if multiword else 1
                    counted |= _terms(trig)
                    if specific:
                        specific_hit = True
            else:
                shared = (_terms(trig) & case_tokens) - counted
                if shared and len(_terms(trig) & case_tokens) / max(len(_terms(trig)), 1) >= 0.5:
                    score += 1
                    counted |= shared
        if specific_hit and score >= min_score:
            scored.append((score, card))
    scored.sort(key=lambda x: x[0], reverse=True)
    return tuple(card for _, card in scored[:max_cards])
