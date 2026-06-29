"""Audit benchmark cases for leakage / insufficiency / other defects with a frontier model.
The model SEES the gold and judges whether the challenge is a fair, leak-free, solvable diagnostic test.
Usage: case_audit.py <model> <manifest> <out.jsonl>  (no PubMed; parallel-safe)"""
import sys, os, json
sys.path.insert(0, "src")
from concurrent.futures import ThreadPoolExecutor, as_completed
from clinical_harness.model_client import OpenAICompatibleChatClient as C
from clinical_harness.guided_eval import parse_json_object
MODELS = {
 "gpt-5.4":  ("https://api.openai.com/v1", os.environ["XM_OPENAI_KEY"], "gpt-5.4"),
 "gpt-5.5":  ("https://api.openai.com/v1", os.environ["XM_OPENAI_KEY"], "gpt-5.5"),
 "opus-4.8": ("https://api.anthropic.com/v1", os.environ["XM_ANTHROPIC_KEY"], "claude-opus-4-8"),
}
name, manifest, outpath = sys.argv[1], sys.argv[2], sys.argv[3]
base, key, model = MODELS[name]
cl = C(base_url=base, api_key=key, model=model, timeout_seconds=300, max_retries=4)
def gold(r):
    ak=r.get("answer_key") or {}; d=ak.get("diagnosis") or r.get("gold_diagnosis") or ""
    return (d[0] if isinstance(d,list) else d), (ak.get("aliases") or [])
def audit(r):
    g,al = gold(r)
    prompt = (
      "You audit a clinical-diagnosis BENCHMARK case for quality. You are given the challenge prompt a "
      "solver sees and the GOLD diagnosis it is scored against. A good case: (a) does NOT leak the answer "
      "(the prompt must not state or pathognomonically give away the gold — the solver must reason), and "
      "(b) is SOLVABLE from the prompt alone (every discriminator needed to reach THIS gold over its "
      "nearest mimic is present). Flag problems. Return ONLY JSON:\n"
      '{"leakage": true|false, "leakage_detail": "<=40 words or null", '
      '"insufficient": true|false, "insufficient_detail": "the missing discriminator, or null", '
      '"other_issue": "gold-not-a-diagnosis / scenario / ambiguous / etc., or null", '
      '"verdict": "clean|flawed"}\n\n'
      f"CHALLENGE PROMPT:\n{r.get('challenge_prompt','')}\n\nGOLD DIAGNOSIS: {g}\nALIASES: {al}\n")
    try:
        res = cl.chat(prompt=prompt, temperature=0.0, max_tokens=4000)
        p = parse_json_object(res.content)
        return {"case_id": r["case_id"], **p}
    except Exception as e:
        return {"case_id": r["case_id"], "error": str(e)[:160]}
rows=[json.loads(l) for l in open(manifest) if l.strip()]
out=[]
with ThreadPoolExecutor(max_workers=3) as pool:
    futs={pool.submit(audit,r):r for r in rows}
    for i,f in enumerate(as_completed(futs),1):
        out.append(f.result())
        if i%10==0: print(f"  {name}: {i}/{len(rows)}", file=sys.stderr, flush=True)
open(outpath,"w").writelines(json.dumps(o)+"\n" for o in out)
from collections import Counter
print(name, "verdicts:", dict(Counter(o.get("verdict","error") for o in out)),
      "leakage:", sum(1 for o in out if o.get("leakage")), "insufficient:", sum(1 for o in out if o.get("insufficient")))
