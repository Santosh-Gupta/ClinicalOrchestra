"""Harness with a split answerer/reader: <answerer> writes the final diagnosis; <reader> does the cheap
high-volume sub-tasks (per-paper screening, distillation, initial assessment). DeepSeek-flash judges.
Usage: crossmodel_harness.py <answerer> <reader> <manifest> <outdir>"""
import sys, os
sys.path.insert(0, "src")
from clinical_harness.model_client import OpenAICompatibleChatClient as C, OpenAIResponsesClient
from clinical_harness.ncbi import NcbiClient, NcbiConfig
from clinical_harness.retrieval_guided_eval import (
    run_retrieval_guided_manifest_eval, summarize_retrieval_guided_results, HarnessConfig)

MODELS = {
 "v4-flash":  ("https://api.deepseek.com", "DEEPSEEK_API_KEY", "deepseek-v4-flash"),
 "v4-pro":    ("https://api.deepseek.com", "DEEPSEEK_API_KEY", "deepseek-v4-pro"),
 "gpt-5.5":   ("https://api.openai.com/v1", "XM_OPENAI_KEY", "gpt-5.5"),
 "gpt-5.4":   ("https://api.openai.com/v1", "XM_OPENAI_KEY", "gpt-5.4"),
 "opus-4.8":  ("https://api.anthropic.com/v1", "XM_ANTHROPIC_KEY", "claude-opus-4-8"),
 "opus-4.7":  ("https://api.anthropic.com/v1", "XM_ANTHROPIC_KEY", "claude-opus-4-7"),
 "gemini-3.1-pro": ("https://generativelanguage.googleapis.com/v1beta/openai", "XM_GEMINI_KEY", "gemini-3.1-pro-preview"),
 "gemini-3.5-flash": ("https://generativelanguage.googleapis.com/v1beta/openai", "XM_GEMINI_KEY", "gemini-3.5-flash"),
}
def client(name):
    base,key_env,model = MODELS[name]
    key = os.environ[key_env]
    if base == "https://api.openai.com/v1" and model.startswith("gpt-5"):
        return OpenAIResponsesClient(
            base_url=base,
            api_key=key,
            model=model,
            timeout_seconds=300,
            max_retries=4,
            reasoning_effort=os.environ.get("OPENAI_REASONING_EFFORT", "medium"),
        )
    return C(base_url=base, api_key=key, model=model, timeout_seconds=300, max_retries=4)

answerer_name, reader_name, manifest, outdir = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
answerer = client(answerer_name); reader = client(reader_name)
# Judge defaults to DeepSeek-flash (the established paper judge); override with HARNESS_JUDGE=<MODELS key>
# when DeepSeek is unavailable (iteration only — a different judge is not comparable to the paper numbers).
_judge_name = os.environ.get("HARNESS_JUDGE", "")
judge = client(_judge_name) if _judge_name in MODELS else C(
    base_url="https://api.deepseek.com", api_key=os.environ["DEEPSEEK_API_KEY"], model="deepseek-v4-flash")
ncbi_verify_tls = os.environ.get("NCBI_VERIFY_TLS", "1").lower() not in {"0", "false", "no"}
ncbi = NcbiClient(NcbiConfig(tool="clinical-harness", email=os.environ.get("NCBI_EMAIL",""),
                             api_key=os.environ.get("NCBI_API_KEY"), verify_tls=ncbi_verify_tls, min_interval_seconds=float(os.environ.get("NCBI_MIN_INTERVAL","0.1"))))
frontier_mode = os.environ.get("HARNESS_FRONTIER_MODE", "").lower() in {"1", "true", "yes", "on"}
max_queries = int(os.environ.get("HARNESS_MAX_QUERIES", "4"))
max_rounds = int(os.environ.get("HARNESS_MAX_ROUNDS", "3" if frontier_mode else "2"))
min_rounds = int(os.environ.get("HARNESS_MIN_ROUNDS", "2" if frontier_mode else "1"))
concurrency = int(os.environ.get("HARNESS_CONCURRENCY", "1"))
answerer_query_fallback = os.environ.get(
    "HARNESS_ANSWERER_QUERY_FALLBACK",
    "0" if frontier_mode else "1",
).lower() in {"1", "true", "yes", "on"}
bare_preservation = os.environ.get("HARNESS_BARE_PRESERVATION", "1" if frontier_mode else "0").lower() in {"1", "true", "yes", "on"}
union_sampling = os.environ.get("HARNESS_UNION_SAMPLING", "").lower() in {"1", "true", "yes", "on"}
samples = int(os.environ.get("HARNESS_SAMPLES", "3" if union_sampling else "1"))
sample_temperature = float(os.environ.get("HARNESS_SAMPLE_TEMPERATURE", "0.0"))  # ALWAYS 0.0
# Provenance for the post-run validator (scripts/validate_run.py): record every comparability-critical
# setting so a run can be certified (or rejected) as a canonical number without guessing.
import json as _json, time as _time
os.makedirs(outdir, exist_ok=True)
_expected_n = sum(1 for _l in open(manifest) if _l.strip())
_json.dump({
    "answerer": MODELS[answerer_name][2], "answerer_key": answerer_name,
    "reader": reader_name, "judge": _judge_name or "deepseek-v4-flash",
    "manifest": manifest, "expected_n": _expected_n,
    "frontier_mode": frontier_mode, "bare_preservation": bare_preservation,
    "closed_book_samples": int(os.environ.get("HARNESS_CLOSED_BOOK_SAMPLES", "1")),
    "sample_temperature": sample_temperature,
    "closed_book_sample_temperature": float(os.environ.get("HARNESS_CB_SAMPLE_TEMP", "0.0")),
    "judge_votes": int(os.environ.get("JUDGE_VOTES", "1")),
    "max_queries": max_queries, "max_rounds": max_rounds, "min_rounds": min_rounds,
    "concurrency": concurrency, "written_at": _time.strftime("%Y-%m-%dT%H:%M:%S"),
}, open(os.path.join(outdir, "run_config.json"), "w"), indent=2)
rows = run_retrieval_guided_manifest_eval(
    manifest_path=manifest, out_dir=outdir, retrieve=True, pubmed_client=ncbi, pmc_client=ncbi,
    model_client=answerer, model_name=MODELS[answerer_name][2], reader_client=reader,
    judge=True, judge_client=judge, max_queries=max_queries, articles_per_query=5, max_rounds=max_rounds,
    distill_evidence=True, use_full_text=True, skip_existing=True, progress=True,
    concurrency=concurrency, samples=samples, sample_temperature=sample_temperature,
    config=HarnessConfig(
        eval_mode=True,
        min_rounds=min_rounds,
        use_answerer_query_planner=frontier_mode,
        answerer_query_fallback=answerer_query_fallback,
        skeptical_evidence_mode=frontier_mode,
        use_bare_answer_preservation=bare_preservation,
        use_union_sampling=union_sampling,
        closed_book_samples=int(os.environ.get("HARNESS_CLOSED_BOOK_SAMPLES", "1")),
        closed_book_union_freq_weight=float(os.environ.get("HARNESS_CB_FREQ_WEIGHT", "0")),
        closed_book_sample_temperature=float(os.environ.get("HARNESS_CB_SAMPLE_TEMP", "0.0")),  # ALWAYS 0.0
        use_inclusive_floor=os.environ.get("HARNESS_INCLUSIVE_FLOOR", "").lower() in {"1", "true", "yes", "on"},
        floor_protect_n=int(os.environ.get("HARNESS_FLOOR_PROTECT_N", "4")),
        floor_from_bare5_dir=os.environ.get("HARNESS_FLOOR_BARE5_DIR", ""),
        use_paper_extractor=True,
        paper_extractor_concurrency=6,
        use_compact_final_prompt=os.environ.get("HARNESS_COMPACT_FINAL", "").lower() in {"1", "true", "yes"},
    ))
print(
    f"answerer={answerer_name} reader={reader_name} frontier_mode={frontier_mode} "
    f"max_queries={max_queries} max_rounds={max_rounds} min_rounds={min_rounds} "
    f"concurrency={concurrency} bare_preservation={bare_preservation} "
    f"answerer_query_fallback={answerer_query_fallback} union_sampling={union_sampling} "
    f"samples={samples} sample_temperature={sample_temperature} "
    f"closed_book_samples={os.environ.get('HARNESS_CLOSED_BOOK_SAMPLES', '1')} "
    f"closed_book_sample_temperature={os.environ.get('HARNESS_CB_SAMPLE_TEMP', '0.0')} "
    f"judge={_judge_name or 'deepseek-v4-flash'} JUDGE_VOTES={os.environ.get('JUDGE_VOTES', '1')}",
    summarize_retrieval_guided_results(rows),
)
