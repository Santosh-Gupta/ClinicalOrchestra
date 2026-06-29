"""Build the etiologic-axis-breadth A/B subsets from the cleaned dev sets.

Splits every cleaned dev case into:
  P (precipitant)    — prompt contains an acute precipitant/exposure preceding onset (the lever's target;
                       should-help / must-not-hurt)
  C (no-precipitant) — control (lever must stay inert -> no regression)

Writes two manifests under data/eval/axis_experiment/. Run the A/B with:
  retrieval-guided-eval --no-retrieve  (baseline)  vs  + --axis-breadth (lever)
on each, temp 0 (deterministic), then compare pass@5 on P and C.
"""
from __future__ import annotations
import json, re
from pathlib import Path

DEV_SETS = [
    "data/eval/wave89_checkpoint/wave89_strict_55.jsonl",
    "data/eval/tenth_wave_checkpoint/tenth_wave_clean_v2.jsonl",
    "data/eval/eleventh_wave_checkpoint/eleventh_wave_clean.jsonl",
]

# Strong acute-precipitant / exposure tokens (an external event preceding onset). Deliberately exclude
# weak temporal words ("after", "following") that appear in nearly every vignette.
PRECIPITANT = re.compile(
    r"(?i)\b("
    r"ingest\w*|ingestion|swallow\w*|\bate\b|\beaten\b|meal|dietary|food|herb\w*|tea\b|"
    r"drug|medication|overdose|poison\w*|toxin|toxic exposure|intoxicat\w*|alcohol|ethanol|methanol|"
    r"mushroom|plant|aconit\w*|envenom\w*|\bbite\b|\bsting\b|snakebite|scorpion|"
    r"heat ?stroke|hyperthermi\w*|heat exposure|sauna|hypothermi\w*|frostbite|altitude|"
    r"carbon monoxide|\bCO\b poisoning|fume\w*|solvent|occupational exposure|pesticide|insecticide|"
    r"trauma\w*|head injury|\bfall\b|\bfell\b|accident|concussion|"
    r"vaccinat\w*|immuniz\w*|anaesthe\w*|anesthe\w*|post-?operat\w*|post-?surg\w*|"
    r"electrocut\w*|lightning|near-?drowning|asphyxia\w*|strangul\w*"
    r")\b"
)

def gold_of(row):
    ak = row.get("answer_key")
    if isinstance(ak, dict):
        return ak.get("diagnosis") or ak.get("primary_diagnosis") or ""
    return row.get("gold_diagnosis") or ""

def main():
    seen, P, C = set(), [], []
    for ds in DEV_SETS:
        p = Path(ds)
        if not p.exists():
            print("MISSING", ds); continue
        for line in p.open():
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            cid = r["case_id"]
            if cid in seen:
                continue
            seen.add(cid)
            prompt = r.get("challenge_prompt", "")
            (P if PRECIPITANT.search(prompt) else C).append(r)
    out = Path("data/eval/axis_experiment"); out.mkdir(parents=True, exist_ok=True)
    (out / "precipitant.jsonl").write_text("".join(json.dumps(r) + "\n" for r in P))
    (out / "control.jsonl").write_text("".join(json.dumps(r) + "\n" for r in C))
    print(f"dev cases total={len(seen)}  precipitant(P)={len(P)}  control(C)={len(C)}")
    print("\nP (lever-target) examples:")
    for r in P[:12]:
        m = PRECIPITANT.search(r["challenge_prompt"])
        print(f"  {r['case_id']:<24} trigger='{m.group(0)}'  gold={gold_of(r)[:42]}")

if __name__ == "__main__":
    main()
