"""Run a non-DeepSeek frontier model on a manifest, judged by DeepSeek-flash (for comparability)."""
import argparse
import os
import sys
sys.path.insert(0, "src")
from clinical_harness.model_client import OpenAICompatibleChatClient as C
from clinical_harness.model_client import OpenAIResponsesClient
from clinical_harness.baseline_eval import run_baseline_manifest_eval, summarize_baseline_results

MODELS = {
 "gpt-5.4":      ("https://api.openai.com/v1", "XM_OPENAI_KEY", "gpt-5.4"),
 "gpt-5.5":      ("https://api.openai.com/v1", "XM_OPENAI_KEY", "gpt-5.5"),
 "gemini-3.1-pro":("https://generativelanguage.googleapis.com/v1beta/openai", "XM_GEMINI_KEY", "gemini-3.1-pro-preview"),
 "gemini-3.5-flash":("https://generativelanguage.googleapis.com/v1beta/openai", "XM_GEMINI_KEY", "gemini-3.5-flash"),
 "opus-4.7":     ("https://api.anthropic.com/v1", "XM_ANTHROPIC_KEY", "claude-opus-4-7"),
 "opus-4.8":     ("https://api.anthropic.com/v1", "XM_ANTHROPIC_KEY", "claude-opus-4-8"),
}
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("model", choices=sorted(MODELS))
parser.add_argument("manifest")
parser.add_argument("outdir")
parser.add_argument("--temperature", type=float, default=0.0)
parser.add_argument("--concurrency", type=int, default=2)
parser.add_argument("--max-tokens", type=int, default=16000)
parser.add_argument("--reasoning-effort", default="medium")
args = parser.parse_args()

name, manifest, outdir = args.model, args.manifest, args.outdir
base, key_env, model = MODELS[name]
key = os.environ[key_env]
if base == "https://api.openai.com/v1" and model.startswith("gpt-5"):
    answerer = OpenAIResponsesClient(
        base_url=base,
        api_key=key,
        model=model,
        timeout_seconds=300,
        max_retries=4,
        reasoning_effort=args.reasoning_effort,
    )
else:
    answerer = C(base_url=base, api_key=key, model=model, timeout_seconds=300, max_retries=4)
judge = C(base_url=os.environ.get("DEEPSEEK_BASE_URL","https://api.deepseek.com"),
          api_key=os.environ["DEEPSEEK_API_KEY"], model="deepseek-v4-flash")
rows = run_baseline_manifest_eval(
    manifest_path=manifest, out_dir=outdir, model_client=answerer, model_name=model,
    judge=True, judge_client=judge, skip_existing=True, progress=True, concurrency=args.concurrency,
    temperature=args.temperature, max_tokens=args.max_tokens)
print(name, summarize_baseline_results(rows), {"temperature": args.temperature, "reasoning_effort": args.reasoning_effort})
