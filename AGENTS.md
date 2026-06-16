# AGENTS.md — start here

This repo is worked on by multiple agents, some running on different LLMs. To avoid reinventing the
wheel or silently reverting hard-won decisions, follow this before you change anything.

## Read first (in order)
1. **[docs/DESIGN_DECISIONS.md](docs/DESIGN_DECISIONS.md)** — the authoritative ADR registry: every
   significant design decision, *why* it was made (often backed by an experiment), and a
   **do-not-revert-unless** clause. Most behaviors look removable until you read the case that forced
   them.
2. **[journal.md](journal.md)** — the living "what we learned" narrative and diagnostic/IR principles.
3. **[README.md](README.md)** — orientation and the rest of the `docs/` index.

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
- `PYTHONPATH=src python3 -m unittest discover -s tests` must pass.
- If you changed harness behavior, check it against the **control set** of easy cases too (ADR-004) —
  "helps the hard cases" and "doesn't break the easy ones" are different claims.
