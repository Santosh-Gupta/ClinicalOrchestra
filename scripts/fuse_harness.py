"""Do-no-harm fusion of a model's bare differential with its ClinicalHarness output (Table 3 of the paper).

Rule: keep the model's bare top-4 unchanged; fill the 5th slot with the harness's single highest-confidence
(rank-1) retrieval-surfaced diagnosis that is ABSENT from the bare top-5. By construction top-1..4 are
identical to bare (cannot demote a confident candidate); only top-5 can move.

Scoring is JUDGE-CONSISTENT: the gold's rank in the bare and harness lists comes from the same alias-aware
majority-of-3 judge that scored the run (fields closed_book_gold_rank and gold_rank). We do NOT re-locate the
gold by string match (that disagrees with the judge on aliases and inflates the gain). Because the fusion
preserves bare[:4] and only the 5th slot can change, the fused gold rank is fully determined by the two judge
ranks plus whether the harness's rank-1 diagnosis is a new entity:
  - bare rank <= 4            -> fused rank = bare rank        (preserved)
  - bare rank == 5, slot5 kept-> fused rank = 5
  - bare miss, slot5=harness#1-> fused rank = 5 iff harness rank == 1 (the gold is the inserted diagnosis)
  - otherwise                 -> miss
"slot5 = harness#1" holds when the harness's top diagnosis is absent from the bare top-5; else slot5 = bare[5].

Inputs (per model): the saved bare5 differential (data/eval/crossmodel_bare5/<model>/<case>.bare5_response.json,
used only to decide whether harness#1 is a NEW entity) and the validated harness run
(data/eval/crossmodel_harness_frontier/<model>__BARE5FLOOR_p3).

Usage: python3.11 scripts/fuse_harness.py
"""
import json, re, os

MODELS = [("gemini-3.5-flash", "Gemini 3.5 Flash"),
          ("v4-pro", "DeepSeek V4 Pro"),
          ("v4-flash", "DeepSeek V4 Flash")]
HARNESS = "data/eval/crossmodel_harness_frontier/%s__BARE5FLOOR_p3"
BARE5 = "data/eval/crossmodel_bare5/%s"


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


def _difflist(payload):
    out = []
    for d in (payload or {}).get("ranked_differential") or []:
        dx = d.get("diagnosis") if isinstance(d, dict) else d
        if dx:
            out.append(dx)
    return out


def _ladder(ranks):
    return [sum(1 for r in ranks if r <= k) for k in range(1, 6)]


def main():
    print("Model              bare@1..5             fused@1..5            top-5 Δ")
    for m, label in MODELS:
        rows = [json.loads(l) for l in open(os.path.join(HARNESS % m, "retrieval_guided_results.jsonl"))]
        bare_ranks, fused_ranks = [], []
        for x in rows:
            if x.get("error"):
                continue
            cid = x["case_id"]
            try:
                bare = _difflist(json.load(open(os.path.join(BARE5 % m, f"{cid}.bare5_response.json")))["content"])
            except (OSError, KeyError, ValueError):
                bare = []
            try:
                harn = _difflist(json.load(open(os.path.join(HARNESS % m, f"{cid}.retrieval_response.json")))["content"])
            except (OSError, KeyError, ValueError):
                harn = []
            b = x.get("closed_book_gold_rank"); b = b if isinstance(b, int) else 99
            h = x.get("gold_rank"); h = h if isinstance(h, int) else 99
            slot5_harness = bool(harn) and _norm(harn[0]) not in {_norm(d) for d in bare[:5]}
            if b <= 4:
                fr = b
            elif slot5_harness:
                fr = 5 if h == 1 else 99   # bare[5] displaced; recovered only if the inserted dx is the gold
            else:
                fr = 5 if b == 5 else 99   # bare[5] kept
            bare_ranks.append(b)
            fused_ranks.append(fr)
        bl, fl = _ladder(bare_ranks), _ladder(fused_ranks)
        print("%-17s %-21s %-21s %+d" % (label, bl, fl, fl[4] - bl[4]))


if __name__ == "__main__":
    main()
