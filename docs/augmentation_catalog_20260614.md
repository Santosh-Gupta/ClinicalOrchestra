# Augmentation catalog: getting the 24 right (grounded in the source papers, 2026-06-14)

Built by comparing each of the 24 challenge cases to its **original source paper** (PMC abstracts
fetched live; see `/tmp/hard24_sources.json` provenance). For each case we now know the *real*
discriminator the authors used. This catalog turns that into augmentations — as many independent
angles as possible (dropout-style), split into **general** (high-leverage, reusable) and **specific**
(niche knowledge that can't live in weights → a stored, retrieved knowledge pack).

## What the source papers reveal (the recurring discriminators)

| # | Case | Gold | Harness said | The discriminator the *paper* used |
| - | --- | --- | --- | --- |
| M1 | PMC13239290 | HSV-1 encephalitis | autoimmune enceph | "HSV can mimic neurodegenerative/NPH in elderly"; CSF HSV PCR |
| M1 | PMC13162229 | SREAT (Hashimoto) | anti-GAD65 AE | **elevated antithyroid antibodies** + steroid response + exclusion |
| M1 | PMC13260868 | DPPX AE | acute intermittent porphyria | DPPX AE characteristically has **prominent abdominal/GI** prodrome |
| M1 | PMC3011101 | carotid dissection, intracranial ext. | PACNS | young **stroke + SAH** → dissection on **vessel imaging** |
| M1 | PMC11662338 | RVCL-S | cerebral venous thrombosis | **patient had KNOWN RVCL-S** — new decline = its complication |
| M1 | PMC13208480 | global hypoxic-ischemic injury | CVST + SAH | **diffuse** edema + **refractory shock** = global anoxia, not focal |
| M1 | PMC13049788 | congenital vascular anomalies | Bow Hunter's | **BPPV treatment failure** → image vasculature; combo anomaly |
| GENE | PMC10339345 | SLC6A1 | "genetic, unknown" | paper: "**suspect SLC6A1** in typical absence + mild cognitive, normal MRI" |
| GENE | PMC11138152 | DJ-1/PARK7 | SPG7 | early-onset parkinsonism + spasticity + cognitive → **PARK gene panel** |
| GENE | PMC13233052 | KCNMA1 | pyridoxine-dependent | WES: de novo **KCNMA1**; fever-associated DEE |
| GENE | PMC12104238 | ASNS deficiency | Fryns | **microcephaly + IUGR + refractory epilepsy + characteristic MRI** |
| GENE | PMC12971692 | SCA12 | FXTAS | tremor+ataxia repeat disorder → **CAG expansion (PPP2R2B)** vs FMR1 |
| GENE | PMC13126082 | SPG4/SPAST | CDKL5 | spastic paraplegia phenotype → **SPG/SPAST**, not an epilepsy gene |
| GENE | PMC13183691 | ATP1A3 (RECA) | "mitochondrial" | **relapsing, fever-triggered** encephalopathy + ataxia → ATP1A3 |
| GENE | PMC13172017 | Mowat-Wilson | Aicardi | (abstract n/a) phenotype → ZEB2 |
| M2 | PMC13240619 | risperidone-valproate catatonia | valproate enceph | **positive dechallenge**: stop risperidone → rapid recovery |
| M2 | PMC11631938 | lamotrigine-induced parkinsonism | "22q11.2 cause" | **NORMAL DaTscan** → drug-induced, not neurodegenerative |
| M2 | PMC13171436 | EIAED → vit-D-deficiency hypocalcemia | hypoparathyroidism | enzyme-inducing AED → CYP450 → **low vit D → low Ca** chain |
| M2 | PMC13220061 | statin toxic rhabdo + neuropathy | anti-HMGCR myopathy | **acute toxic** rhabdo+GBS-like, not chronic immune (anti-HMGCR) |
| M2 | PMC12174427 | mixed overdose + Acinetobacter | (added influenza B) | parsimony — don't invent unsupported complications |
| M4 | PMC13214945 | bvFTD **+** GAD65 AE | GAD65 AE only | paper is about **two coexisting** disorders |
| M4 | PMC13219314 | AE-suspect but **GBM** | CASPR2 AE | **follow-up imaging** revealed tumor; transient low-titer Ab |
| M4 | PMC12926095 | borderline IQ + ADHD, **not autism** | ADHD only | referred for autism ≠ autism; **multi-axis**, masking |
| PSY | PMC13250257 | Illness Anxiety Disorder | functional movement | dominant feature is **illness preoccupation**, not the movement |

## General augmentations (high leverage; the "more thought and effort" ones)

**G1 — Seek the REFUTING test; a discordant objective result overrides the anchor.** (catches
PMC11631938 normal DaTscan, PMC13219314 evolving imaging / transient low-titer Ab, PMC13162229
antithyroid antibodies.) Before closing, name the single test that would most argue *against* the
lead, and check whether the case already contains it. A normal/transient/discordant result beats a
"fitting" story. → universal gate.

**G2 — The referral/prior label is a hypothesis, not the answer; a new presentation in a known rare
disease is most likely its complication.** (catches PMC11662338 known RVCL-S, PMC12926095 autism
referral, PMC12971692 "essential tremor" relabel.) Do not diagnose *around* the patient's established
disease, and do not inherit the referral's anchor. → universal gate.

**G3 — Gene disambiguation for recognizable phenotypes: name the specific gene, not the family or a
near-neighbor.** (catches the 9 GENE rows — the model gets the *family* right but the wrong gene:
SPG7-for-DJ1, FXTAS-for-SCA12, CDKL5-for-SPG4, mitochondrial-for-ATP1A3, Fryns-for-ASNS.) For a
recognizable phenotype, enumerate the candidate genes and pick by the discriminating feature; "genetic
cause unknown" is a fail. Pairs with phenotype→gene retrieval (validated) and the knowledge pack. →
universal gate + knowledge pack + retrieval.

**G4 — Iatrogenic with dechallenge/test confirmation.** (catches PMC13240619 dechallenge,
PMC13171436 drug→metabolic chain, PMC13220061 tempo.) Extend the iatrogenic gate: a positive
dechallenge (symptoms resolve on stopping the drug) is strong evidence; trace drug→metabolic chains
(EIAED→vit D→Ca); separate *toxic* from *immune* drug myopathy by tempo + antibody. → extend gate.

**G5 — Global vs focal; parsimony.** (catches PMC13208480 diffuse-edema+shock=global anoxia;
PMC12174427 don't invent influenza B.) Distinguish a diffuse/global process (systemic insult →
anoxic) from a focal vascular event; do not add complications the case does not support. → gate +
fidelity note (reuse ADR-050 spirit on the answer side).

**G6 — Second pathology / coexistence + serial evolution.** (catches PMC13214945 dual dx,
PMC13219314 GBM behind AE.) Already a universal gate; strengthen with "an evolving/relapsing course or
a transient/low-titer marker should trigger re-imaging and a second-pathology search."

## Specific augmentations → the stored knowledge pack (`knowledge_pack`)

The niche knowledge can't live in weights or a generic prompt. Store **cards** (trigger features →
consider entity → discriminator → confirmatory test → source PMID), match by case features, inject the
top matches as "specific entities to consider." Seed from the 24 (each is a real, citable teaching
point). Examples to seed:

- typical absence + mild cognitive deficit + normal MRI + GLUT1-negative → **SLC6A1** (PMID from PMC10339345)
- early-onset parkinsonism + spasticity + cognitive decline + normal/young → **DJ-1/PARK7, PINK1, Parkin** panel
- parkinsonism + **normal DaTscan** → **drug-induced parkinsonism**, not neurodegenerative
- tremor+ataxia, "essential tremor" that doesn't fit → **SCA12 (PPP2R2B CAG)** vs **FXTAS (FMR1)** — test both
- progressive spastic paraplegia/quadriplegia → **SPG4/SPAST** (commonest AD HSP)
- relapsing, **fever-triggered** encephalopathy + cerebellar ataxia → **ATP1A3** (RECA/CAPOS spectrum)
- congenital microcephaly + IUGR + refractory epilepsy + characteristic MRI → **ASNS deficiency**
- subacute encephalopathy, steroid-responsive, unexplained → check **antithyroid antibodies → SREAT**
- autoimmune encephalitis with **prominent abdominal/GI** prodrome → **DPPX antibody** encephalitis
- young **stroke + SAH** → **cervical artery dissection** (vessel-wall imaging) before PACNS
- known **RVCL-S / monogenic vasculopathy** + new decline → complication of that disease, not new CVT
- AED (enzyme-inducing) + hypocalcemic seizures → **vitamin D deficiency** chain, not hypoparathyroidism

## Retrieval augmentations (validated earlier + new)

- **Phenotype→gene queries** (`<phenotype> gene` / `<phenotype> genetic causes`) reach the gene via
  reviews even when the gene isn't known. (Already: query focusing + this pattern.)
- **"Known disease + new symptom"** → query complications of the known disease.
- **Per-paper extractor** (`paper_analysis.py`) + literature-driven query expansion will surface the
  exact teaching sentences (the SLC6A1 paper literally states its rule).

## Architecture augmentations

- **Multi-angle ensemble** (`diagnostic_ensemble.py`): the `molecular_test` angle already reclaimed a
  gene case (Mowat-Wilson); the `exposure_iatrogenic` and `cant_miss` angles own M2/can't-miss. Wire
  in + difficulty-gate.
- **Knowledge-pack-as-a-tool for an agent**: let an angle agent query the knowledge pack.

## Round 2 — third-100 dev set (2026-06-15): confirms structure, adds targets

First-contact generalization checkpoint: improved harness reclaimed 3/28 third-100 double-failures
(general machinery transferred; seeded niche cards correctly inert on new entities). The 25 residuals
re-confirm the SAME failure taxonomy and add targets:

**General (cross-set, implemented this round):** antibody over-commit / missed OVERLAP. The model
collapses overlap syndromes to one antibody and defaults to anti-NMDAR: seronegative AE → "anti-NMDA";
Morvan/CASPR2 → "anti-NMDA"; MOG+NMDAR (MNOS) → "MOGAD only"; triple-antibody overlap → "anti-NMDAR".
Fix shipped: extended the commit-to-specific gate — *don't default to anti-NMDAR without its evidence;
'seronegative AE' is valid; name the OVERLAP when features span syndromes.* Bidirectional-safe.
**Validate on the NEXT set, not by re-running third-100.**

**Niche (accumulate — new entities to card / reach via phenotype→gene retrieval):** KCTD17
myoclonus-dystonia (→ got KCNMA1), TANGO2 deficiency (→ GLUT1), DHDDS DEE (→ Pumilio1), KCNQ3 DEE
(→ Ohtahara/STXBP1), Warsaw breakage syndrome (→ Baraitser-Winter), Fahr's disease (→ drug-induced
parkinsonism), MSA-P vs MSA-C (subtype), VLOSLP, microcystic macular edema (→ MS), reflex/startle
epilepsy (→ Tay-Sachs). **Scalability note:** carding each rare gene is slow; prioritize phenotype→gene
RETRIEVAL (find the gene via a review without a pre-existing card) as the general lever, reserving
cards for non-retrievable discriminators.

**Recurring tumor-behind-a-label miss (general candidate):** psychosis from a temporal astrocytoma →
"methamphetamine psychosis"; PCNSL → "neoplasm, histology pending". Reinforce: new psychiatric/tox
presentation with any focal or structural clue → image for and exclude a brain tumor before a
primary-psychiatric/tox label.

## Priority for implementation (this evolution)

1. Stored **knowledge pack** (specific, novel, explicitly requested) — module + seed cards + inject.
2. Universal gates **G1 (refuting test), G2 (known-disease/referral), G3 (gene disambiguation)**.
3. Extend the iatrogenic gate with **G4 (dechallenge)**.
4. Measure on the 24 (union with ensemble + retrieval) and guard the control set.
