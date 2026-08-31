# A vibe check on frontier LLMs' diagnostic reasoning — and why it isn't a paper

*Status: exploratory, paused. Code, the 68-case benchmark, and ~358 development cases are released in the
GitHub repository currently hosted at
[Santosh-Gupta/ClinicalOrchestra](https://github.com/Santosh-Gupta/ClinicalOrchestra). If the open problems
below interest you, please reach out.*

I set out to build a contamination-reduced benchmark of frontier LLMs on **open-ended** clinical
diagnosis — not multiple-choice, but "here is a real case, give me your ranked differential" — over neurology
and psychiatry case reports published after a conservative cutoff gate for the evaluated models. Alongside it
I built a retrieval harness meant to ground each diagnosis in citable literature. I got far enough to see some genuinely
interesting things, and far enough to convince myself that the *definitive* version of this is a much bigger,
more expensive undertaking than one person should claim to have nailed. So this is a write-up of the vibe, not
a paper. Here is what's interesting, and here is why I'm not calling it settled.

The workshop-paper draft is therefore archived as a methods/results record, not being advanced as a submission
right now. The public README points here first; the LaTeX draft stays in the repo so others can inspect the
full experimental trail, reproduce pieces, or decide whether a more rigorous expert-reviewed version is worth
funding.

## What's actually interesting

**1. Frontier models differ in *where* they place the correct diagnosis, not just *whether* they get it.**
Scoring the full ranked differential (top-1 through top-5) instead of a single label changes the apparent ordering.
On a 68-case stress set, at **top-1** the GPT-5.x models led (GPT-5.4 47/68, GPT-5.5 43) and Gemini 3.5 Flash sat
near the bottom (29). By **top-5**, Gemini Flash had climbed to *second* (54), overtaking GPT-5.5 (51), Opus
4.8 (50), and DeepSeek V4 Pro (47) — while GPT-5.4 stayed on top (57). Some models "commit" (right early, flat
after), others "spread" (the correct entity is often present but ranked lower). A single-label eval mis-ranks
exactly the models that are most useful when the deliverable is a differential a clinician can weigh. Also
surprising: within a family the *cheaper* sibling won (Gemini 3.5 Flash beat 3.1 Pro by ten points at top-5),
and the earlier GPT-5.4 edged the later 5.5. I can measure that the distributions differ; I can't tell you why,
because the training is undisclosed.

There is an important sampling caveat: these 68 cases were retained because an earlier closed-book DeepSeek V4
Flash run failed them. DeepSeek Flash is therefore 0/68 by construction, and this is a **failure-selected rescue
set**, not a neutral leaderboard or a representative estimate of clinical accuracy. The useful observation is
the difference between committing and spreading on the same stress cases—not the fine ordering of model brands.

**2. Naively bolting on retrieval *hurts* a strong model.** This was the biggest surprise. Replacing a
model's own differential with a retrieval-grounded one *lowered* accuracy — retrieval injects
literature-salient candidates near the top and crowds the model's own correct diagnoses downward. The fix
wasn't more retrieval; it was *less* — a conservative "do-no-harm fusion" that keeps the model's confident
top-4 and only lets retrieval fill the fifth slot with a diagnosis the model missed. That nudged top-5 up by
+1/+2/+3, largest on the weakest base model. The lesson generalizes: for a model with rich internal medical
knowledge, external evidence complements at the margin rather than replacing — and integrating it carelessly
makes the system worse.

There was an even more basic confound: the closed-book baseline itself was under-elicited. On Gemini 3.5 Flash,
one greedy differential exposed far less of the model's knowledge than a three-sample union. With three samples,
the gold appeared in the closed-book candidate set for 53/68 cases; adding retrieval moved that to 54/68. The
pattern reproduced with a different reader and judge. Much of the apparent "retrieval lift" was really an
elicitation lift. Before crediting a tool, strengthen the no-tool baseline enough that the tool is not merely
recovering answers the model already knows but failed to say on its first sample.

This also separated two problems I had initially conflated. Retrieval often did its job: it brought the gold
diagnosis into the candidate set and improved top-5 recall. The regression happened afterward, when the final
chooser promoted a more specific or literature-salient mimic above it. In this regime, **elicitation, selection,
and calibration—not document retrieval—were often the bottlenecks**. Measuring only the final top-1 answer would
have blamed the wrong component.

**3. You can only safely "verify-and-edit" a model's answer where you have a sound oracle.** I tried a second
harness that acts as a conservative *editor* of the model's differential — only re-ranking on a verbatim,
case-grounded, independently-verified discriminator. It still didn't reliably beat the base model on hard
cases. The audit showed why: the model would demote a *correct* diagnosis on a real lab value it
*misinterpreted* (e.g., "Mg 2.8 refutes Gitelman syndrome" — defensible, since Gitelman classically causes low
magnesium, but the answer was Gitelman anyway). Contrast this with recent math results, where a prover–verifier
pipeline cracks open problems *because Lean is a sound oracle* — a proof either type-checks or it doesn't.
Clinical diagnosis is **defeasible**: a "refuting" finding is a probabilistic prior, not a proof. So
verification-gated augmentation, which pays off spectacularly in formal math, did not reliably beat the base
model on these hard cases — because the verification it needed was often exactly the reasoning the model lacked
there. The safe contribution I could demonstrate was a *dominance guarantee* (never do harm), not reliable
accuracy gains.

## What went wrong while building the harness

The harness work was its own lesson. I originally thought the pipeline would look something like: take the case,
retrieve relevant literature, summarize the useful discriminators, and let the model produce a better diagnosis.
That intuition was too optimistic.

The first problem was that **a harness is only as meaningful as the benchmark underneath it**. If the challenge
prompt is missing the clue that justifies the gold diagnosis, then retrieval can do two bad things: it can find
the source article and leak the answer, or it can find adjacent literature and make the model hallucinate a
justification that is not actually in the prompt. If the gold is over-specific, under-supported, or really an
outcome/management answer rather than a diagnosis, the harness may look wrong for giving the clinically better
answer. So benchmark flaws don't just add noise to evaluation; they actively corrupt harness development,
because every apparent "model failure" might really be a challenge-construction failure.

One early bug made this painfully concrete. A regex intended to remove diagnostic leakage treated phrases like
"MRI revealed ..." as if they announced the diagnosis, and silently cut away workup findings—including, in some
cases, the discriminator that made the published answer reachable. The general lesson was broader than that bug:
mechanical parsers can locate sections, but the boundary between *diagnostic evidence* and *answer leakage* is a
semantic decision. It needs source-grounded validation, not a clever string rule or the constructor model grading
its own work.

Even after filtering and mending the benchmark, the harness kept running into a second problem: **retrieval is
not automatically a better prior than the model's own medical knowledge**. The model often already had the
right diagnosis somewhere in its top five. Retrieval brought in literature-salient mimics, rare entities,
guideline language, and source-adjacent terminology. Those were useful when the base model had a real knowledge
gap, but harmful when the model was already basically right. The retrieved evidence changed the frame of the
case, and the final model would sometimes demote its own correct answer because a retrieved mimic sounded more
specific, more publishable, or more strongly associated with one finding.

I tried several versions of the harness around that failure mode. Deterministic query templates helped weak
models in some hand-analyzed cases, but they also encoded the failures I had just seen — for example, pushing
too hard on rare neuroinflammatory, vascular, infectious, or pathology mimics. Later versions let the frontier
model generate its own query ideas first, used a cheaper reader model only to extract evidence, added skeptical
reader instructions, did multiple retrieval rounds, and tried to preserve the model's closed-book differential
as a floor. Those were all directionally saner. But the fundamental issue remained: once the harness is allowed
to freely re-rank, it can crowd out the model's own correct candidates.

The most reliable thing I found was therefore very conservative: keep the base model's top candidates protected,
and let retrieval add only a small amount of recall at the bottom of the list unless there is a truly
case-grounded reason to edit. That produced the modest "do-no-harm fusion" result. It is less exciting than a
full agentic diagnostic workflow, but it matches the evidence: retrieval helped at the margin and hurt when it
was allowed to become the main diagnostician.

The v2 attempt pushed this to the logical extreme: make the harness a verifier/editor instead of a generator.
Every edit needed a verbatim case discriminator, not just a retrieved-paper claim. Absence of support was not
allowed to demote a candidate. The reader was not allowed to decide. The model had to ratify proposed moves.
That architecture is much safer, but it also exposed the deeper clinical problem: **the "verifier" is not a
sound oracle**. A lab value, imaging feature, or time course can be strongly suggestive without being
conclusive. In medicine, exceptions are common and diagnoses are probabilistic. So the verifier can still
reject the right answer for a plausible-but-wrong reason. Without an expert or formal criterion that actually
settles the question, a verifier-gated harness can avoid obvious harm, but it is hard to make it reliably
improve top-1.

There was also a subtler trap: the measurement itself was unreliable. Scoring the same differential twice could
return different ranks, so before I could trust any result I had to fix the *judge* — judge stochasticity had
been manufacturing fake gains and fake harms, and I was debugging the measurement and the thing being measured
at the same time.

Some failures were more prosaic and just as dangerous. Truncated model JSON could become an empty query plan;
an empty plan could leave the supposedly protected closed-book floor empty; reader failures could make papers
vanish from the evidence packet; resumed runs could lose derived baseline fields; and rate-limit errors could
quietly change the denominator. Each failure still produced plausible-looking output. That changed how I think
about agent evaluation: **observability and run provenance are part of the scientific method**. Every fallback,
dropped document, model/version change, incomplete case, and scoring denominator has to be explicit and fail
loudly, or the system can manufacture an improvement without improving anything.

That points at the deepest issue. Every instrument in the stack is an LLM: the benchmark is
LLM-built, the judge is an LLM, and the v2 verifier is an LLM that shares the base model's blind spots. Three
noisy, *correlated* instruments stacked on one another, so you can never cleanly separate "the harness
improved" from "the measurement moved." Formal math has Lean at the bottom of the stack; here it's LLMs all the
way down.

So the harness development story is not "we just needed better prompts." Open-ended diagnosis sits in an awkward
middle ground: it benefits from retrieval, but retrieval is noisy; it benefits from verification, but
verification is defeasible; it needs benchmark examples, but weak examples teach the harness the wrong lesson —
and there is no sound anchor anywhere in the stack to tell you whether you're making progress. That combination
makes the problem much harder than it looked at the start.

## Why this is a blog post, not a paper

The honest reason is the benchmark-construction problem, which turned out to be much deeper than I expected.

**The circularity.** To turn a published case report into a fair challenge, you have to redact the diagnosis
while keeping *everything a doctor would need to reach it*. I assumed that "everything needed" is contained in
the case report itself. **It often isn't** — case reports are written to *narrate* a diagnosis already known
to the authors, not to be self-contained diagnostic puzzles. Worse: whatever gap-filling or completeness-check
you do is performed *by an LLM*, so the quality of a challenge is bounded by the capabilities of the LLM used
to build it. That's a serious problem when the whole point is to measure the diagnostic ability of LLMs. You
risk baking the constructor model's blind spots into the test. I put real effort into determinacy audits,
three-model adversarial leakage/insufficiency checks, and source-grounded repair-or-drop — and it meaningfully
helped — but I could not get to *iron-clad*, per-case, without expert human review. A pipeline that reaches
that bar likely exists, but it would take a serious time and API-cost commitment to find, and costs were
already high.

**Post-cutoff is a control, not a proof of uncontaminated evaluation.** Publishing a case after a model's
documented knowledge cutoff blocks the most obvious pretraining path, but provider cutoff metadata can be coarse
or unavailable, and later fine-tuning or connected search is not fully observable. Retrieval creates a second
leakage route: if the harness finds the original case report, it can recover the answer even though the base model
never saw it during training. A defensible run therefore needs both a conservative publication-date gate and
explicit source-article exclusion with an audit trail. Even then, the claim is "reduced memorization risk," not
"this case cannot have been seen."

**And it's a moving target.** Even as a vibe, the specific numbers are already stale — every provider has
shipped new model versions since these runs. The *shape* of the findings (models spread differently; retrieval
must be integrated conservatively; verification needs an oracle) is more durable than the leaderboard.

So: I think this is good enough to get a *feel* for how these models reason diagnostically, and to surface
some real, transferable lessons — but not good enough to stand as a definitive benchmark, and I'd rather say
that plainly than oversell it.

## Open problems (where someone could take this further)

- **Robust, non-circular challenge construction.** How do you build a self-contained diagnostic challenge from
  a case report *without* the constructor LLM's competence upper-bounding the test? Maybe: multi-source
  grounding, structured extraction against formal diagnostic criteria, or expert-in-the-loop verification at
  scale. This is the crux.
- **Verification in a defeasible domain.** Is there a partial "oracle" for diagnosis — formal criteria sets
  (McDonald, Duke, DSM thresholds), lab-range checks, an independent stronger-model verifier — that raises the
  precision of gated editing enough to safely beat the base model? My results say the same-model verifier
  isn't enough.
- **Ranked-differential evaluation as standard.** Scoring the whole differential (not one label) revealed
  model behavior a single-label eval hides. That framing seems worth keeping regardless of the rest.
- **Hard-set sampling without conditioning on one model.** A failure-selected set is useful for rescue analysis,
  but it cannot support a neutral leaderboard. A stronger study needs either model-independent difficulty criteria
  or a prospectively sampled panel, with failure-selected slices reported separately.

## What's in the repo

- `benchmark/neuro_psych_68_challenges.jsonl` — the 68-case post-cutoff, CC-BY, DeepSeek-Flash-failure-selected
  stress set. It is useful for rescue analysis, not a neutral model leaderboard.
- `benchmark/development_cases_359.jsonl` — 358 earlier development cases, with a `review_status` per case.
  **These were not all proofread/mended/filtered** — treat them as raw material, not a clean benchmark.
- The harness code, the do-no-harm fusion, and the (paused) v2 verifier-gated editor.
- The archived, unpolished draft paper, for anyone who wants the full methods. It is not the current project
  deliverable.

If you know how to make the challenge-construction pipeline robust — or you just want to argue about it —
I'd genuinely like to hear from you.
