#!/usr/bin/env python3
"""Analyze a frontier-mode harness run: closed-book baseline vs final, with flip accounting.

Usage: python3.11 scripts/analyze_frontier_run.py <run_dir> [<run_dir> ...]

For each run prints pass@1/pass@5 for the model's CLOSED-BOOK top-5 (its own pre-retrieval
differential) and for the FINAL floor-enforced differential, plus the flip accounting that matters
for "does retrieval help": top-5 LOSSES (closed-book hit -> final miss, should be ~0), RESCUES
(miss -> hit), and BOTH-MISS (retrieval failed to surface the gold -> the target for more recall).
"""
from __future__ import annotations

import json
import os
import sys


def _le(rank, k):
    return isinstance(rank, int) and rank <= k


def analyze(run_dir: str) -> None:
    p = os.path.join(run_dir, "retrieval_guided_results.jsonl")
    if not os.path.exists(p):
        print(f"{run_dir}: no results.jsonl yet")
        return
    rows = [json.loads(l) for l in open(p) if l.strip()]
    n = len(rows)
    cb = lambda r: _le(r.get("closed_book_gold_rank"), 5)
    fn = lambda r: _le(r.get("gold_rank"), 5)
    cb1 = sum(1 for r in rows if _le(r.get("closed_book_gold_rank"), 1))
    cb5 = sum(1 for r in rows if cb(r))
    f1 = sum(1 for r in rows if _le(r.get("gold_rank"), 1))
    f5 = sum(1 for r in rows if fn(r))
    losses = sum(1 for r in rows if cb(r) and not fn(r))
    rescues = sum(1 for r in rows if not cb(r) and fn(r))
    both_miss = sum(1 for r in rows if not cb(r) and not fn(r))
    errors = sum(1 for r in rows if r.get("error"))
    gold_hits = sum(1 for r in rows if r.get("gold_rank") is not None)
    cb_hits = sum(1 for r in rows if r.get("closed_book_gold_rank") is not None)
    print(f"\n=== {os.path.basename(run_dir.rstrip('/'))}  (N={n}) ===")
    print(f"  rows={n}  errors={errors}  final_gold_hits={gold_hits}/{n}  closed_book_gold_hits={cb_hits}/{n}")
    print(f"  CLOSED-BOOK own top-5:  pass@1={cb1}/{n}  pass@5={cb5}/{n}")
    print(f"  FINAL (floor):          pass@1={f1}/{n}  pass@5={f5}/{n}")
    print(f"  retrieval lift (p@5):   {f5 - cb5:+d}   |   vs old harness 47:  {f5 - 47:+d}")
    print(f"  LOSSES={losses}  RESCUES={rescues}  BOTH-MISS={both_miss}  (both-miss = recall ceiling to attack)")
    # cases where retrieval surfaced gold but ranked it >5 would be in both-miss; show both-miss ids
    bm = [r["case_id"][-12:] for r in rows if not cb(r) and not fn(r)]
    print(f"  both-miss case ids: {bm}")


if __name__ == "__main__":
    for d in sys.argv[1:] or ["."]:
        analyze(d)
