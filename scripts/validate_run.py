#!/usr/bin/env python3.11
"""LOUD post-run validator. Exits 1 with an explicit list of violations if a harness run dir is NOT
safe to report as a canonical number. Catches exactly the silent-degradation modes that corrupted past
runs: row errors, off-spec temperature/reader/judge, empty planners (disabled floor), missing scored
ranks or floor baseline, missing provenance, and manifest/result count mismatch.

Usage:
  validate_run.py <run_dir> [--n 68] [--reader v4-flash] [--judge deepseek-v4-flash]
A run PASSES only if every check passes. Designed to be run before any number is trusted/reported.
"""
import argparse, glob, json, os, sys

p = argparse.ArgumentParser()
p.add_argument("run_dir")
p.add_argument("--n", type=int, default=68, help="expected case count")
p.add_argument("--reader", default=None, help="expected reader model key (else from run_config)")
p.add_argument("--judge", default="deepseek-v4-flash", help="expected judge model")
args = p.parse_args()
D = args.run_dir.rstrip("/")
fail: list[str] = []
warn: list[str] = []


def load(path):
    try:
        return json.load(open(path))
    except Exception:
        return None


# --- provenance ---
cfg = load(os.path.join(D, "run_config.json"))
if cfg is None:
    fail.append("NO run_config.json — provenance unknown; cannot certify temperature/reader/judge/code version")
else:
    st = cfg.get("sample_temperature")
    cbt = cfg.get("closed_book_sample_temperature")
    if st not in (0, 0.0):
        fail.append(f"sample_temperature={st} (MUST be 0.0)")
    if cbt not in (0, 0.0):
        fail.append(f"closed_book_sample_temperature={cbt} (MUST be 0.0)")
    if args.reader and cfg.get("reader") not in (args.reader, None):
        if cfg.get("reader") != args.reader:
            fail.append(f"reader={cfg.get('reader')} != expected {args.reader}")
    jr = cfg.get("judge")
    if jr and args.judge and jr != args.judge:
        fail.append(f"judge={jr} != expected {args.judge}")

# --- results.jsonl: counts, errors, scored ranks, floor baseline ---
rf = os.path.join(D, "retrieval_guided_results.jsonl")
rows = [json.loads(l) for l in open(rf)] if os.path.exists(rf) else []
if not rows:
    fail.append("no retrieval_guided_results.jsonl rows")
else:
    if len(rows) != args.n:
        fail.append(f"results rows={len(rows)} != expected N={args.n}")
    errored = [r.get("case_id") for r in rows if r.get("error")]
    if errored:
        fail.append(f"{len(errored)} rows have errors, e.g. {errored[:5]}")
    no_gold = [r.get("case_id") for r in rows if not r.get("error") and r.get("gold_rank") is None and r.get("score") not in ("pass", "fail")]
    # gold_rank None is legitimate only when scored as a miss; flag rows with neither a rank nor a score
    if no_gold:
        fail.append(f"{len(no_gold)} rows unscored (no gold_rank and no pass/fail), e.g. {no_gold[:5]}")
    # closed_book_gold_rank == None is a LEGITIMATE floor miss (gold absent from the model's closed-book
    # differential), not a persistence failure — so it is informational, not a hard fail. The floor being
    # genuinely DISABLED is caught by the empty-planner check below. (The original skip-resume corruption
    # is prevented upstream by response persistence + the empty-planner check.)
    floor_miss = sum(1 for r in rows if not r.get("error") and r.get("closed_book_gold_rank") is None)
    if floor_miss:
        warn.append(f"{floor_miss} cases with closed_book_gold_rank=None (legitimate floor misses on a hard set)")

# --- per-case query plans: empty planner == disabled do-no-harm floor ---
qps = glob.glob(os.path.join(D, "*.query_plan.json"))
if qps:
    empty = [os.path.basename(f).replace(".query_plan.json", "") for f in qps
             if not (load(f) or {}).get("possible_diagnoses")]
    if empty:
        fail.append(f"{len(empty)}/{len(qps)} EMPTY planners (floor disabled — truncation/credit/format), e.g. {empty[:5]}")

# --- per-case response files: errors ---
resp = glob.glob(os.path.join(D, "*.retrieval_response.json"))
resp_err = [os.path.basename(f).split(".")[0] for f in resp if (load(f) or {}).get("error")]
if resp_err:
    fail.append(f"{len(resp_err)} response files contain errors, e.g. {resp_err[:5]}")
if resp and len(resp) != args.n:
    warn.append(f"response files={len(resp)} != N={args.n}")

# --- verdict ---
print(f"=== validate_run: {D} ===")
if cfg:
    print(f"  provenance: answerer={cfg.get('answerer')} reader={cfg.get('reader')} judge={cfg.get('judge')} "
          f"temp={cfg.get('sample_temperature')}/{cfg.get('closed_book_sample_temperature')} "
          f"cb_samples={cfg.get('closed_book_samples')} JUDGE_VOTES={cfg.get('judge_votes')}")
for w in warn:
    print(f"  WARN: {w}")
if fail:
    print(f"  RESULT: \033[31mFAIL ({len(fail)} violations) — NOT safe to report\033[0m")
    for f in fail:
        print(f"    ✗ {f}")
    sys.exit(1)
print("  RESULT: \033[32mPASS — safe to report\033[0m")
sys.exit(0)
