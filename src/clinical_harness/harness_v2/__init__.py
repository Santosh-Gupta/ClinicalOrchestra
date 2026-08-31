"""ClinicalHarness v2 — a dominance-seeking, verifier-gated diagnostic harness.

Design goal: produce a ranked top-5 differential that DOMINATES the base model's bare differential at every
cutoff (pass@n_v2 >= pass@n_bare for n=1..5), while still improving some cutoffs (including top-1).

Architecture is bare-first / retrieval-second / verifier-gated. The harness is a conservative EDITOR of the
model's own bare differential (default action: no-op), not a generator that competes with it. See
docs/HARNESS_V2_DESIGN.md for the full spec and the two-tier "harm budget" framing, and
docs/HARNESS_V2_EXPERIMENTS.md for the dev-set protocol.

This package is NEW and independent of the frozen v1 method (the do-no-harm fusion in
scripts/fuse_harness.py + retrieval_guided_eval.py). v1 must not be modified; v2 reuses v1's retrieval/reader/
judge infrastructure but owns the ledger, self-critique, verifier, and move-policy logic.

Status: stage bodies are implemented; live dev-set validation still requires configured provider credentials.
"""
