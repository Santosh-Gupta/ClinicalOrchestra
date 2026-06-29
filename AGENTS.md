# AGENTS.md — start here

This repo is worked on by multiple agents, some running on different LLMs. To avoid reinventing the
wheel or silently reverting hard-won decisions, follow this before you change anything.

## Read first (in order)
0. **[docs/HANDOFF_20260624.md](docs/HANDOFF_20260624.md)** — LATEST snapshot for the LM4Sci paper:
   audit approval packet, current validated preflight state, remaining gates, and exact next actions.
   Read this first.
0a. **[docs/HANDOFF_20260623.md](docs/HANDOFF_20260623.md)** — prior full snapshot (numbers, what's
   running, the resolved GPT-5.5 temperature behavior on Responses, the implemented Responses client,
   and the audit-arbitration context). Read this after the 0624 handoff for detailed background.
0b. **[docs/HANDOFF_20260620.md](docs/HANDOFF_20260620.md)** — if continuing the 2026-06-20 session:
   the cross-model benchmark + paper-draft state, what's in flight, keys/scripts, and the (citable)
   contamination control. Read this BEFORE touching the cross-model or paper work.
   - **[docs/AUDIT_ARBITRATION_INSTRUCTIONS.md](docs/AUDIT_ARBITRATION_INSTRUCTIONS.md)** — if you're
     here to act on the 3-auditor review of the 81 hard cases: the over-flagging caveat, the
     `_crossref.csv` worklist, the drop/mend/keep rules, and the user-veto-before-apply workflow.
1. **[docs/OPERATOR_RUNBOOK.md](docs/OPERATOR_RUNBOOK.md)** — the turnkey "how to actually operate it"
   guide: env setup, validating a new batch, the 3-stage eval protocol with exact commands, analyzing
   outputs (pass@k, `gold_rank`, failure triage), the trace viewer/UI, and the rules for changes. If
   you're here to *run the harness on new cases*, start with this.
2. **[docs/DESIGN_DECISIONS.md](docs/DESIGN_DECISIONS.md)** — the authoritative ADR registry: every
   significant design decision, *why* it was made (often backed by an experiment), and a
   **do-not-revert-unless** clause. Most behaviors look removable until you read the case that forced
   them.
3. **[journal.md](journal.md)** — the living "what we learned" narrative and diagnostic/IR principles.
4. **[README.md](README.md)** — orientation, the Agent-Trace Viewer (UI), and the rest of the `docs/` index.

## The one rule that matters
**Do not silently revert or weaken a documented decision.** If you believe one is wrong, add a *new*
ADR in `docs/DESIGN_DECISIONS.md` that supersedes it (state the new evidence, mark the old one
`Superseded by ADR-NNN`), then change the code. The decision trail must survive across agents.

## When you make a change
- New significant/architectural decision → **add an ADR** in `docs/DESIGN_DECISIONS.md`.
- Learned something durable about diagnosis or retrieval → **add a journal entry** (cite the case).
- Deep analysis or a design → a dated `docs/<topic>_<date>.md`, and link it from its ADR.
- A decision recorded only in a commit message is invisible to the next agent. Don't do that.

## Project boundaries & safety
- This is the **harness** repo. Benchmark *data generation* lives in the sibling **NeurologyBM** repo
  (see [docs/project_split.md](docs/project_split.md)). Don't edit NeurologyBM from here unless asked.
- **Eval mode** (default on) must never retrieve/read the source paper a benchmark item came from
  (ADR-030). Don't disable source exclusion during benchmarking.
- This is benchmark/IR research, **not** a clinical decision-support system.

## Validate before you finish
- `PYTHONPATH=src python3.11 -m unittest discover -s tests` must pass.
- For the workshop-paper package, use `python3.11 scripts/validate_workshop_submission.py` and
  `PYTHONPATH=src python3.11 -m unittest discover -s tests`.
- If you changed harness behavior, check it against the **control set** of easy cases too (ADR-004) —
  "helps the hard cases" and "doesn't break the easy ones" are different claims.
