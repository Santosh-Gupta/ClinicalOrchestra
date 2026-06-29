"""Deterministic BARE top-5 eval: one temperature-0 ranked-differential call per case (NO harness, NO
retrieval, NO sampling), response saved to disk, each rank judged by DeepSeek-flash for comparability.
Outputs pass@1..5. Usage: bare_top5_eval.py <model> <manifest> <outdir>"""
import os, sys, json, time, concurrent.futures as cf
sys.path.insert(0, "src")
from clinical_harness.model_client import OpenAICompatibleChatClient as C, OpenAIResponsesClient
from clinical_harness.guided_eval import case_from_manifest_row, parse_json_object
from clinical_harness.retrieval_guided_eval import _gold_rank, _ranked_diagnoses

MODELS = {
 "gpt-5.4":         ("https://api.openai.com/v1", "XM_OPENAI_KEY", "gpt-5.4"),
 "gpt-5.5":         ("https://api.openai.com/v1", "XM_OPENAI_KEY", "gpt-5.5"),
 "gemini-3.1-pro":  ("https://generativelanguage.googleapis.com/v1beta/openai", "XM_GEMINI_KEY", "gemini-3.1-pro-preview"),
 "gemini-3.5-flash":("https://generativelanguage.googleapis.com/v1beta/openai", "XM_GEMINI_KEY", "gemini-3.5-flash"),
 "opus-4.8":        ("https://api.anthropic.com/v1", "XM_ANTHROPIC_KEY", "claude-opus-4-8"),
 "v4-pro":          ("https://api.deepseek.com", "DEEPSEEK_API_KEY", "deepseek-v4-pro"),
 "v4-flash":        ("https://api.deepseek.com", "DEEPSEEK_API_KEY", "deepseek-v4-flash"),
}
name, manifest, outdir = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(outdir, exist_ok=True)
base, key_env, model = MODELS[name]
key = os.environ[key_env]
if base == "https://api.openai.com/v1" and model.startswith("gpt-5"):
    answerer = OpenAIResponsesClient(base_url=base, api_key=key, model=model, timeout_seconds=300, max_retries=4,
                                     reasoning_effort=os.environ.get("OPENAI_REASONING_EFFORT", "medium"))
else:
    answerer = C(base_url=base, api_key=key, model=model, timeout_seconds=300,
                 max_retries=int(os.environ.get("BARE_MAX_RETRIES", "4")))
_throttle = float(os.environ.get("BARE_SLEEP", "0"))  # per-call delay to stay under tight RPM (e.g. gemini-3.1-pro)
judge = C(base_url="https://api.deepseek.com", api_key=os.environ["DEEPSEEK_API_KEY"], model="deepseek-v4-flash")
concurrency = int(os.environ.get("BARE_CONCURRENCY", "2"))

PROMPT = ('Give your TOP 5 most likely diagnoses for this case, ranked most likely first, as strict JSON '
          '{"ranked_differential":[{"rank":1,"diagnosis":"..."},...5 items]}. Use ONLY your own medical '
          'knowledge (no outside lookup). Be specific. Case:\n')

rows = [json.loads(l) for l in open(manifest) if l.strip()]

def one(r):
    case = case_from_manifest_row(r); cid = r.get("case_id") or r.get("id") or case.case_id
    ak = r.get("answer_key") or r.get("gold")
    if isinstance(ak, str): ak = {"diagnosis": ak}
    path = os.path.join(outdir, f"{cid}.bare5_response.json")
    if os.path.exists(path):  # skip_existing: reuse saved response, never re-spend
        payload = json.load(open(path)).get("content")
    else:
        try:
            if _throttle: time.sleep(_throttle)
            res = answerer.chat(prompt=PROMPT + case.prompt, temperature=0.0, max_tokens=16000)
            payload = parse_json_object(res.content)
            json.dump({"case_id": cid, "content": payload, "raw": res.content}, open(path, "w"))
        except Exception as e:
            json.dump({"case_id": cid, "error": str(e)}, open(path, "w")); return (cid, None, True)
    ranked = _ranked_diagnoses(payload, limit=5) if payload else []
    rank = _gold_rank(ranked, ak, judge_client=judge, fallback_client=None)
    return (cid, rank if isinstance(rank, int) else None, False)

with cf.ThreadPoolExecutor(max_workers=concurrency) as ex:
    res = list(ex.map(one, rows))
err = sum(1 for _, _, e in res if e)
ranks = [rk for _, rk, e in res if not e]
ladder = [sum(1 for rk in ranks if rk is not None and 1 <= rk <= k) for k in range(1, 6)]
json.dump({"model": name, "n": len(ranks), "err": err, "pass_at_1_5": ladder,
           "ranks": {cid: rk for cid, rk, e in res if not e}}, open(os.path.join(outdir, "bare5_summary.json"), "w"), indent=2)
print(f"{name} BARE top-5 (N={len(ranks)}, err={err}): @1..5 = {ladder}")
