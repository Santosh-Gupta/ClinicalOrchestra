"""Command line interface for ClinicalHarness."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from .case_runner import RUN_MODES, run_case
from .deepseek_failures import DeepSeekFailurePaths, load_failure_analysis_packets, write_packets_jsonl
from .diagnostic_harness import (
    HARNESS_PRESETS,
    build_answer_packet,
    build_discriminator_packet,
    build_query_ideas_packet,
    load_evidence_notes,
    validate_retrieval_queries,
)
from .guided_eval import (
    DEFAULT_ALL_PUBLIC_PRO_FAILED_MANIFEST,
    answer_key_from_manifest_row,
    load_failed_manifest,
    run_guided_manifest_eval,
    summarize_guided_results,
)
from .baseline_eval import run_baseline_manifest_eval, summarize_baseline_results
from .judge import score_diagnosis
from .model_client import OpenAICompatibleChatClient
from .ncbi import NcbiClient, NcbiConfig
from .pmc import fetch_pmc_articles, pmc_search
from .pubmed import pubmed_search
from .retrieval_guided_eval import (
    HarnessConfig,
    run_retrieval_guided_manifest_eval,
    summarize_retrieval_guided_results,
)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, URLError, TimeoutError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clinical-harness",
        description="ClinicalHarness research CLI.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    pubmed_parser = subparsers.add_parser("pubmed", help="PubMed retrieval commands.")
    pubmed_subparsers = pubmed_parser.add_subparsers(dest="pubmed_command", required=True)

    search_parser = pubmed_subparsers.add_parser("search", help="Search PubMed and fetch abstracts.")
    search_parser.add_argument("query", help="PubMed query string.")
    search_parser.add_argument("--limit", type=int, default=10, help="Maximum articles to fetch.")
    search_parser.add_argument("--sort", default="relevance", choices=("relevance", "pub+date"))
    search_parser.add_argument("--format", choices=("json", "text"), default="text")
    add_ncbi_args(search_parser)
    search_parser.set_defaults(func=cmd_pubmed_search)

    pmc_parser = subparsers.add_parser("pmc", help="PMC retrieval commands.")
    pmc_subparsers = pmc_parser.add_subparsers(dest="pmc_command", required=True)

    pmc_search_parser = pmc_subparsers.add_parser("search", help="Search PMC and fetch full-text XML.")
    pmc_search_parser.add_argument("query", help="PMC query string.")
    pmc_search_parser.add_argument("--limit", type=int, default=5, help="Maximum PMC articles to fetch.")
    pmc_search_parser.add_argument("--sort", default="relevance", choices=("relevance", "pub+date"))
    pmc_search_parser.add_argument("--format", choices=("json", "text"), default="text")
    add_ncbi_args(pmc_search_parser)
    pmc_search_parser.set_defaults(func=cmd_pmc_search)

    pmc_fetch_parser = pmc_subparsers.add_parser("fetch", help="Fetch PMC full text by PMCID.")
    pmc_fetch_parser.add_argument("pmcid", nargs="+", help="PMCID, with or without PMC prefix.")
    pmc_fetch_parser.add_argument("--format", choices=("json", "text"), default="text")
    add_ncbi_args(pmc_fetch_parser)
    pmc_fetch_parser.set_defaults(func=cmd_pmc_fetch)

    case_parser = subparsers.add_parser("case", help="Case attempt commands.")
    case_subparsers = case_parser.add_subparsers(dest="case_command", required=True)

    run_parser = case_subparsers.add_parser("run", help="Run one case through a diagnosis workflow.")
    run_parser.add_argument("case_path", help="Path to a ClinicalCase JSON file.")
    run_parser.add_argument("--mode", choices=RUN_MODES, default="pubmed_only")
    run_parser.add_argument("--out", default="runs", help="Directory where run artifacts are written.")
    run_parser.add_argument("--run-id", help="Optional deterministic run id.")
    run_parser.add_argument("--limit", type=int, default=5, help="Maximum PubMed articles per query.")
    run_parser.add_argument("--sort", default="relevance", choices=("relevance", "pub+date"))
    run_parser.add_argument(
        "--no-retrieve",
        action="store_true",
        help="Generate queries and run artifacts without calling external retrieval APIs.",
    )
    add_ncbi_args(run_parser)
    run_parser.set_defaults(func=cmd_case_run)

    query_prompt_parser = case_subparsers.add_parser(
        "query-prompt",
        help="Build a guarded prompt asking a model for diagnostic retrieval query ideas.",
    )
    query_prompt_parser.add_argument("case_path", help="Path to a ClinicalCase JSON file.")
    query_prompt_parser.add_argument("--round", dest="round_index", type=int, default=1)
    query_prompt_parser.add_argument("--max-rounds", type=int, default=3)
    query_prompt_parser.add_argument("--preset", choices=HARNESS_PRESETS, default="general")
    query_prompt_parser.add_argument("--previous-query", action="append", default=[])
    query_prompt_parser.add_argument("--out", help="Optional JSON output path.")
    query_prompt_parser.set_defaults(func=cmd_case_query_prompt)

    answer_prompt_parser = case_subparsers.add_parser(
        "answer-prompt",
        help="Build a diagnostic update prompt from distilled evidence notes.",
    )
    answer_prompt_parser.add_argument("case_path", help="Path to a ClinicalCase JSON file.")
    answer_prompt_parser.add_argument("--notes", required=True, help="Evidence notes JSONL path.")
    answer_prompt_parser.add_argument("--round", dest="round_index", type=int, default=2)
    answer_prompt_parser.add_argument("--max-rounds", type=int, default=3)
    answer_prompt_parser.add_argument("--preset", choices=HARNESS_PRESETS, default="general")
    answer_prompt_parser.add_argument("--previous-query", action="append", default=[])
    answer_prompt_parser.add_argument("--out", help="Optional JSON output path.")
    answer_prompt_parser.set_defaults(func=cmd_case_answer_prompt)

    discriminator_prompt_parser = case_subparsers.add_parser(
        "discriminator-prompt",
        help="Build a prompt for discriminator-focused retrieval planning from a current differential.",
    )
    discriminator_prompt_parser.add_argument("case_path", help="Path to a ClinicalCase JSON file.")
    discriminator_prompt_parser.add_argument("--differential", required=True, help="Current differential JSON path.")
    discriminator_prompt_parser.add_argument("--round", dest="round_index", type=int, default=2)
    discriminator_prompt_parser.add_argument("--max-rounds", type=int, default=3)
    discriminator_prompt_parser.add_argument("--preset", choices=HARNESS_PRESETS, default="general")
    discriminator_prompt_parser.add_argument("--previous-query", action="append", default=[])
    discriminator_prompt_parser.add_argument("--out", help="Optional JSON output path.")
    discriminator_prompt_parser.set_defaults(func=cmd_case_discriminator_prompt)

    validate_queries_parser = case_subparsers.add_parser(
        "validate-queries",
        help="Check proposed retrieval queries for source shortcuts and exact prompt overlap.",
    )
    validate_queries_parser.add_argument("case_path", help="Path to a ClinicalCase JSON file.")
    validate_queries_parser.add_argument("--query", action="append", default=[], help="Query to validate.")
    validate_queries_parser.add_argument("--queries-jsonl", help="JSONL file containing query strings or objects.")
    validate_queries_parser.set_defaults(func=cmd_case_validate_queries)

    benchmark_parser = subparsers.add_parser("benchmark", help="Benchmark preparation commands.")
    benchmark_subparsers = benchmark_parser.add_subparsers(dest="benchmark_command", required=True)

    packets_parser = benchmark_subparsers.add_parser(
        "deepseek-packets",
        help="Export DeepSeek failure-analysis packets for retrieval-workflow design.",
    )
    packets_parser.add_argument("--out", required=True, help="Output JSONL path.")
    packets_parser.add_argument("--subset", choices=("all", "neuro_psych"), default="all")
    packets_parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="Specific still-failed case id to export. May be passed multiple times.",
    )
    packets_parser.add_argument(
        "--max-answer-rest-chars",
        type=int,
        default=5000,
        help="Maximum evaluator-only paper discussion/outcome characters per packet.",
    )
    packets_parser.add_argument("--ready-manifest", help="Override ready manifest JSONL path.")
    packets_parser.add_argument("--still-failed-ids", help="Override still-failed case-id file.")
    packets_parser.add_argument("--pro-comparison", help="Override Pro comparison TSV path.")
    packets_parser.add_argument("--pro-results", help="Override Pro results TSV path.")
    packets_parser.add_argument("--pro-scores", help="Override Pro scores TSV path.")
    packets_parser.add_argument("--flash-results", help="Override Flash results TSV path.")
    packets_parser.add_argument("--flash-scores", help="Override Flash scores TSV path.")
    packets_parser.set_defaults(func=cmd_benchmark_deepseek_packets)

    guided_eval_parser = benchmark_subparsers.add_parser(
        "guided-eval",
        help="Run guided direct final-answer prompts on a Pro-failed manifest.",
    )
    guided_eval_parser.add_argument(
        "--manifest",
        default=str(DEFAULT_ALL_PUBLIC_PRO_FAILED_MANIFEST),
        help="Manifest JSONL containing Pro-failed public cases.",
    )
    guided_eval_parser.add_argument("--out-dir", required=True, help="Directory for prompts, responses, and scores.")
    guided_eval_parser.add_argument("--case-id", action="append", default=[], help="Case id to run; repeatable.")
    guided_eval_parser.add_argument("--limit", type=int, help="Limit selected cases.")
    guided_eval_parser.add_argument("--dry-run", action="store_true", help="Write prompts and not call a model API.")
    guided_eval_parser.add_argument("--skip-existing", action="store_true", help="Reuse existing response files.")
    guided_eval_parser.add_argument("--progress", action="store_true", help="Print per-case progress to stderr.")
    guided_eval_parser.add_argument("--model", help="Model name for the OpenAI-compatible API.")
    guided_eval_parser.set_defaults(func=cmd_benchmark_guided_eval)

    baseline_eval_parser = benchmark_subparsers.add_parser(
        "baseline-eval",
        help="Bare model baseline: answer the case cold (no harness, retrieval, gates, or rounds).",
    )
    baseline_eval_parser.add_argument("--manifest", required=True, help="Manifest JSONL of cases.")
    baseline_eval_parser.add_argument("--out-dir", required=True, help="Directory for prompts, responses, scores.")
    baseline_eval_parser.add_argument("--case-id", action="append", default=[], help="Case id to run; repeatable.")
    baseline_eval_parser.add_argument("--limit", type=int, help="Limit selected cases.")
    baseline_eval_parser.add_argument("--dry-run", action="store_true", help="Write prompts and not call a model API.")
    baseline_eval_parser.add_argument("--skip-existing", action="store_true", help="Reuse existing response files.")
    baseline_eval_parser.add_argument("--progress", action="store_true", help="Print per-case progress to stderr.")
    baseline_eval_parser.add_argument("--model", help="Answer model name (e.g. deepseek-v4-flash or deepseek-v4-pro).")
    baseline_eval_parser.add_argument("--judge", action="store_true", help="Score with the LLM judge in addition to lexical.")
    baseline_eval_parser.add_argument("--judge-model", help="Judge model name (defaults to DEEPSEEK_JUDGE_MODEL or the answer model).")
    baseline_eval_parser.add_argument("--concurrency", type=int, default=1, help="Cases to evaluate in parallel.")
    baseline_eval_parser.add_argument(
        "--max-tokens", type=int, default=8192,
        help="Completion-token budget. Reasoning models (deepseek-v4-pro) spend tokens on hidden "
             "reasoning before the answer, so keep this generous or hard cases return empty.",
    )
    baseline_eval_parser.add_argument(
        "--temperature", type=float, default=0.0,
        help="Sampling temperature. Default 0.0 is deterministic; set >0 (e.g. 0.4) for multi-seed "
             "variance runs (re-run to different --out-dir per seed, then aggregate mean±range).",
    )
    baseline_eval_parser.set_defaults(func=cmd_benchmark_baseline_eval)

    retrieval_guided_eval_parser = benchmark_subparsers.add_parser(
        "retrieval-guided-eval",
        help="Run PubMed retrieval-guided final-answer prompts on a Pro-failed manifest.",
    )
    retrieval_guided_eval_parser.add_argument(
        "--manifest",
        default=str(DEFAULT_ALL_PUBLIC_PRO_FAILED_MANIFEST),
        help="Manifest JSONL containing Pro-failed public cases.",
    )
    retrieval_guided_eval_parser.add_argument("--out-dir", required=True)
    retrieval_guided_eval_parser.add_argument("--case-id", action="append", default=[])
    retrieval_guided_eval_parser.add_argument("--limit", type=int)
    retrieval_guided_eval_parser.add_argument("--dry-run", action="store_true", help="Write artifacts without model call.")
    retrieval_guided_eval_parser.add_argument(
        "--no-retrieve",
        action="store_true",
        help="Generate retrieval plans without calling PubMed.",
    )
    retrieval_guided_eval_parser.add_argument("--max-queries", type=int, default=2)
    retrieval_guided_eval_parser.add_argument("--articles-per-query", type=int, default=3)
    retrieval_guided_eval_parser.add_argument(
        "--max-rounds", type=int, default=1,
        help="Safety cap on retrieval rounds. With adaptive rounds on (default), the distillation "
             "subagent stops earlier once its differential is resolved; raise this (e.g. 4) to let "
             "it gather more when needed.",
    )
    retrieval_guided_eval_parser.add_argument(
        "--min-rounds", type=int, default=1,
        help="Minimum retrieval rounds to always run before adaptive stopping applies.",
    )
    retrieval_guided_eval_parser.add_argument(
        "--no-adaptive-rounds", action="store_true",
        help="Disable agent-decided rounds; run the legacy fixed-round heuristic up to --max-rounds.",
    )
    retrieval_guided_eval_parser.add_argument(
        "--concurrency", type=int, default=1,
        help="Number of cases to evaluate in parallel (bounded thread pool). NCBI rate limits are "
             "serialized globally and the model client retries on 429, so this is bounded in "
             "practice by DeepSeek concurrency (500 pro / 2500 flash) and NCBI's ~3-10 req/s.",
    )
    retrieval_guided_eval_parser.add_argument(
        "--distill-evidence",
        action="store_true",
        help="Use a model subagent to distill retrieved evidence into discriminator tables.",
    )
    retrieval_guided_eval_parser.add_argument(
        "--use-full-text",
        action="store_true",
        help="Fetch available PMC full text for top retrieved articles and inject compact snippets.",
    )
    retrieval_guided_eval_parser.add_argument("--skip-existing", action="store_true")
    retrieval_guided_eval_parser.add_argument("--progress", action="store_true")
    retrieval_guided_eval_parser.add_argument(
        "--viewer-url",
        help="Optional ClinicalHarness Viewer backend URL. When set, live Event objects are POSTed "
        "to <viewer-url>/api/live/events while the run executes, e.g. http://127.0.0.1:8000.",
    )
    retrieval_guided_eval_parser.add_argument("--model", help="Model name for the OpenAI-compatible API.")
    retrieval_guided_eval_parser.add_argument(
        "--judge",
        action="store_true",
        help="Score correctness with an LLM diagnostic-equivalence judge (lexical pass is a cheap pre-pass).",
    )
    retrieval_guided_eval_parser.add_argument(
        "--judge-model",
        help="Independent model for the judge (e.g. deepseek-v4-pro). Defaults to the answer model "
        "or the DEEPSEEK_JUDGE_MODEL env var.",
    )
    retrieval_guided_eval_parser.add_argument(
        "--samples",
        type=int,
        default=1,
        help="Self-consistency: sample the answer model this many times and majority-vote the "
        "diagnosis. >1 also records an agreement (confidence) fraction.",
    )
    retrieval_guided_eval_parser.add_argument(
        "--sample-temperature",
        type=float,
        default=0.5,
        help="Sampling temperature when --samples > 1 (default 0.5).",
    )
    retrieval_guided_eval_parser.add_argument(
        "--no-gates", action="store_true",
        help="Ablation: do not inject finalization gates / anchor mimic pairs into prompts.",
    )
    retrieval_guided_eval_parser.add_argument(
        "--no-contrast-queries", action="store_true",
        help="Ablation: do not add the symmetric mimic-contrast retrieval query.",
    )
    retrieval_guided_eval_parser.add_argument(
        "--no-relevance-filter", action="store_true",
        help="Ablation: do not relevance-filter/re-query retrieved evidence.",
    )
    retrieval_guided_eval_parser.add_argument(
        "--rerank", action="store_true",
        help="Discriminator-driven re-rank: a focused second pass reorders the top-5 by case-specific "
             "discriminator match (not familiarity), targeting the gold-in-top-5-but-not-#1 ranking error.",
    )
    retrieval_guided_eval_parser.add_argument(
        "--paper-extractor", action="store_true",
        help="Context-isolated scaled retrieval: screen EVERY retrieved paper in its own Flash call and "
             "feed only the distilled relevant notes (not capped top-8 abstracts). Lets you raise "
             "--articles-per-query / --max-queries without context blowup.",
    )
    retrieval_guided_eval_parser.add_argument(
        "--frontier-mode", action="store_true",
        help="Frontier answerer owns round-1 query planning and writes the reader extraction brief; "
             "also enables the skeptical evidence contract. Use with --max-rounds >=3 for multi-round runs.",
    )
    retrieval_guided_eval_parser.add_argument(
        "--answerer-query-planner", action="store_true",
        help="Ablation: ask the final answerer to generate round-1 retrieval queries, without enabling "
             "the rest of --frontier-mode.",
    )
    retrieval_guided_eval_parser.add_argument(
        "--no-answerer-query-fallback", action="store_true",
        help="Ablation: when answerer query planning is enabled, do not fill unused/failed query slots "
             "with deterministic fallback queries.",
    )
    retrieval_guided_eval_parser.add_argument(
        "--answerer-query-fallback", action="store_true",
        help="When --frontier-mode is enabled, explicitly allow deterministic fallback queries to fill "
             "unused answerer-planned query slots. Off by default in frontier mode.",
    )
    retrieval_guided_eval_parser.add_argument(
        "--skeptical-evidence-mode", action="store_true",
        help="Tell reader/final prompts to treat every inserted artifact as a noisy lead that needs "
             "case-fact matching before it can move the differential.",
    )
    retrieval_guided_eval_parser.add_argument(
        "--bare-answer-preservation", action="store_true",
        help="Keep the frontier answerer's closed-book diagnostic state visible through final ranking; "
             "enabled automatically by --frontier-mode.",
    )
    retrieval_guided_eval_parser.add_argument(
        "--no-knowledge-pack", action="store_true",
        help="Ablation: do not inject stored knowledge-pack cards (rare-entity discriminators) into the prompt.",
    )
    retrieval_guided_eval_parser.add_argument(
        "--no-eval-mode", action="store_true",
        help="Doctor-assist mode: do NOT exclude the source paper or inject anti-cheat guards. "
             "Default (eval mode on) forbids retrieving/reading the source paper for honest benchmarking.",
    )
    retrieval_guided_eval_parser.add_argument(
        "--axis-breadth", action="store_true",
        help="EXPERIMENTAL (ADR-043 REJECTED — null A/B). Left for reproducibility; do not enable.",
    )
    retrieval_guided_eval_parser.add_argument(
        "--max-specificity", action="store_true",
        help="EXPERIMENTAL (ADR-044 REJECTED — null A/B). Left for reproducibility; do not enable.",
    )
    retrieval_guided_eval_parser.add_argument(
        "--ensemble", action="store_true",
        help="EXPERIMENTAL (A/B pending): run the 6-angle diagnostic ensemble + skeptical coordinator "
             "(ADR-041) as a reasoning pre-pass and inject its reconciled view into the final answerer. "
             "~7 extra Flash calls/case. Validate via A/B against JUDGE_VOTES=3 before adopting.",
    )
    retrieval_guided_eval_parser.add_argument(
        "--feature-presets-only", action="store_true",
        help="Select every case's preset from its features (ignore the case_id override map). "
             "Use to measure how the feature selector generalizes on the originally-tuned cases.",
    )
    add_ncbi_args(retrieval_guided_eval_parser)
    retrieval_guided_eval_parser.set_defaults(func=cmd_benchmark_retrieval_guided_eval)

    judge_rescore_parser = benchmark_subparsers.add_parser(
        "judge-rescore",
        help="Re-score an existing retrieval-guided run directory with the LLM judge (no retrieval/answer re-run).",
    )
    judge_rescore_parser.add_argument("--run-dir", required=True, help="Existing run directory to re-score.")
    judge_rescore_parser.add_argument(
        "--manifest",
        default=str(DEFAULT_ALL_PUBLIC_PRO_FAILED_MANIFEST),
        help="Manifest JSONL providing answer keys and aliases.",
    )
    judge_rescore_parser.add_argument(
        "--model",
        help="Model name for the judge API (e.g. deepseek-v4-pro for independent scoring).",
    )
    judge_rescore_parser.add_argument("--progress", action="store_true")
    judge_rescore_parser.set_defaults(func=cmd_benchmark_judge_rescore)

    return parser


def add_ncbi_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--email", default=os.getenv("NCBI_EMAIL"), help="Contact email for NCBI requests.")
    parser.add_argument("--api-key", default=os.getenv("NCBI_API_KEY"), help="Optional NCBI API key.")
    parser.add_argument("--tool", default="ClinicalHarness", help="NCBI tool name.")
    parser.add_argument("--sleep", type=float, default=0.34, help="Minimum seconds between requests.")
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification. Intended only for broken local certificate stores.",
    )


def _viewer_emitter(viewer_url: str):
    endpoint = viewer_url.rstrip("/") + "/api/live/events"
    warned = False

    def emit(event: dict) -> None:
        nonlocal warned
        request = Request(
            endpoint,
            data=json.dumps(event).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=2) as response:
                response.read()
        except Exception as exc:  # noqa: BLE001 - viewer is observational; never fail the run.
            if not warned:
                print(f"warning: could not post live event to viewer: {exc}", file=sys.stderr)
                warned = True

    return emit


def cmd_pubmed_search(args: argparse.Namespace) -> int:
    if args.limit < 1:
        raise ValueError("--limit must be at least 1")
    if not args.email:
        print(
            "warning: set --email or NCBI_EMAIL so NCBI can contact you about automated traffic.",
            file=sys.stderr,
        )
    client = NcbiClient(
        NcbiConfig(
            tool=args.tool,
            email=args.email,
            api_key=args.api_key,
            verify_tls=not args.insecure,
            min_interval_seconds=args.sleep,
        )
    )
    result = pubmed_search(client, args.query, limit=args.limit, sort=args.sort)
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        _print_text_result(result)
    return 0


def cmd_pmc_search(args: argparse.Namespace) -> int:
    if args.limit < 1:
        raise ValueError("--limit must be at least 1")
    client = _ncbi_client_from_args(args)
    result = pmc_search(client, args.query, limit=args.limit, sort=args.sort)
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        _print_pmc_text_result(result)
    return 0


def cmd_pmc_fetch(args: argparse.Namespace) -> int:
    client = _ncbi_client_from_args(args)
    articles = fetch_pmc_articles(client, args.pmcid)
    result = {
        "pmcids": args.pmcid,
        "articles": [article.to_dict() for article in articles],
    }
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        _print_pmc_articles(articles)
    return 0


def cmd_case_run(args: argparse.Namespace) -> int:
    if args.limit < 1:
        raise ValueError("--limit must be at least 1")

    retrieve = not args.no_retrieve and args.mode.startswith("pubmed")
    client = None
    if retrieve:
        if not args.email:
            print(
                "warning: set --email or NCBI_EMAIL so NCBI can contact you about automated traffic.",
                file=sys.stderr,
            )
        client = NcbiClient(
            NcbiConfig(
                tool=args.tool,
                email=args.email,
                api_key=args.api_key,
                verify_tls=not args.insecure,
                min_interval_seconds=args.sleep,
            )
        )

    result = run_case(
        args.case_path,
        mode=args.mode,
        out_dir=args.out,
        run_id=args.run_id,
        limit=args.limit,
        sort=args.sort,
        retrieve=retrieve,
        client=client,
        cli_args={
            "mode": args.mode,
            "limit": args.limit,
            "sort": args.sort,
            "no_retrieve": args.no_retrieve,
        },
    )
    print(f"Run: {result.run_id}")
    print(f"Artifacts: {result.run_dir}")
    print(f"Queries: {len(result.queries)}")
    print(f"Evidence records: {len(result.evidence)}")
    print(f"Answer: {result.answer.final_diagnosis} ({result.answer.confidence})")
    return 0


def cmd_case_query_prompt(args: argparse.Namespace) -> int:
    packet = build_query_ideas_packet(
        args.case_path,
        round_index=args.round_index,
        max_rounds=args.max_rounds,
        previous_queries=tuple(args.previous_query),
        preset=args.preset,
    )
    _emit_json(packet.to_dict(), args.out)
    return 0


def cmd_case_answer_prompt(args: argparse.Namespace) -> int:
    notes = load_evidence_notes(args.notes)
    packet = build_answer_packet(
        args.case_path,
        evidence_notes=notes,
        round_index=args.round_index,
        max_rounds=args.max_rounds,
        previous_queries=tuple(args.previous_query),
        preset=args.preset,
    )
    _emit_json(packet.to_dict(), args.out)
    return 0


def cmd_case_discriminator_prompt(args: argparse.Namespace) -> int:
    differential = _read_json_object(args.differential, "differential")
    packet = build_discriminator_packet(
        args.case_path,
        differential=differential,
        round_index=args.round_index,
        max_rounds=args.max_rounds,
        previous_queries=tuple(args.previous_query),
        preset=args.preset,
    )
    _emit_json(packet.to_dict(), args.out)
    return 0


def cmd_case_validate_queries(args: argparse.Namespace) -> int:
    queries = list(args.query)
    if args.queries_jsonl:
        queries.extend(_read_queries_jsonl(args.queries_jsonl))
    if not queries:
        raise ValueError("provide at least one --query or --queries-jsonl")
    violations = validate_retrieval_queries(args.case_path, tuple(queries))
    payload = {
        "valid": not violations,
        "query_count": len(queries),
        "violations": [violation.to_dict() for violation in violations],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 1 if violations else 0


def cmd_benchmark_deepseek_packets(args: argparse.Namespace) -> int:
    if args.max_answer_rest_chars < 1:
        raise ValueError("--max-answer-rest-chars must be at least 1")
    default_paths = DeepSeekFailurePaths()
    paths = DeepSeekFailurePaths(
        ready_manifest=_path_arg(args.ready_manifest, default_paths.ready_manifest),
        still_failed_ids=_path_arg(args.still_failed_ids, default_paths.still_failed_ids),
        pro_comparison=_path_arg(args.pro_comparison, default_paths.pro_comparison),
        pro_results=_path_arg(args.pro_results, default_paths.pro_results),
        pro_scores=_path_arg(args.pro_scores, default_paths.pro_scores),
        flash_results=_path_arg(args.flash_results, default_paths.flash_results),
        flash_scores=_path_arg(args.flash_scores, default_paths.flash_scores),
    )
    packets = load_failure_analysis_packets(
        paths,
        subset=args.subset,
        case_ids=tuple(args.case_id),
        max_answer_rest_chars=args.max_answer_rest_chars,
    )
    write_packets_jsonl(packets, args.out)
    print(f"Wrote {len(packets)} DeepSeek failure-analysis packets: {args.out}")
    return 0


def cmd_benchmark_baseline_eval(args: argparse.Namespace) -> int:
    if args.limit is not None and args.limit < 1:
        raise ValueError("--limit must be at least 1")
    rows = run_baseline_manifest_eval(
        manifest_path=args.manifest,
        out_dir=args.out_dir,
        case_ids=tuple(args.case_id),
        limit=args.limit,
        dry_run=args.dry_run,
        model_name=args.model,
        judge=args.judge,
        judge_model=args.judge_model,
        skip_existing=args.skip_existing,
        progress=args.progress,
        concurrency=args.concurrency,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
    )
    counts = summarize_baseline_results(rows)
    print(f"Wrote baseline (no-harness) eval artifacts: {args.out_dir}")
    print(f"Cases: {len(rows)}")
    for key in sorted(counts):
        print(f"{key}: {counts[key]}")
    if args.dry_run:
        print("Dry run: model API was not called.")
    return 0


def cmd_benchmark_guided_eval(args: argparse.Namespace) -> int:
    if args.limit is not None and args.limit < 1:
        raise ValueError("--limit must be at least 1")
    rows = run_guided_manifest_eval(
        manifest_path=args.manifest,
        out_dir=args.out_dir,
        case_ids=tuple(args.case_id),
        limit=args.limit,
        dry_run=args.dry_run,
        model_name=args.model,
        skip_existing=args.skip_existing,
        progress=args.progress,
    )
    counts = summarize_guided_results(rows)
    print(f"Wrote guided eval artifacts: {args.out_dir}")
    print(f"Cases: {len(rows)}")
    for key in sorted(counts):
        print(f"{key}: {counts[key]}")
    if args.dry_run:
        print("Dry run: model API was not called.")
    return 0


def cmd_benchmark_retrieval_guided_eval(args: argparse.Namespace) -> int:
    if args.limit is not None and args.limit < 1:
        raise ValueError("--limit must be at least 1")
    if args.max_queries < 1:
        raise ValueError("--max-queries must be at least 1")
    if args.articles_per_query < 1:
        raise ValueError("--articles-per-query must be at least 1")
    if args.max_rounds < 1:
        raise ValueError("--max-rounds must be at least 1")
    if args.samples < 1:
        raise ValueError("--samples must be at least 1")
    retrieve = not args.no_retrieve
    pubmed_client = _ncbi_client_from_args(args) if retrieve else None
    pmc_client = _ncbi_client_from_args(args) if retrieve and args.use_full_text else None
    viewer_emitter = _viewer_emitter(args.viewer_url) if args.viewer_url else None
    rows = run_retrieval_guided_manifest_eval(
        manifest_path=args.manifest,
        out_dir=args.out_dir,
        case_ids=tuple(args.case_id),
        limit=args.limit,
        dry_run=args.dry_run,
        retrieve=retrieve,
        pubmed_client=pubmed_client,
        model_name=args.model,
        max_queries=args.max_queries,
        articles_per_query=args.articles_per_query,
        max_rounds=args.max_rounds,
        distill_evidence=args.distill_evidence,
        use_full_text=args.use_full_text,
        pmc_client=pmc_client,
        skip_existing=args.skip_existing,
        progress=args.progress,
        judge=args.judge,
        judge_model=args.judge_model,
        samples=args.samples,
        sample_temperature=args.sample_temperature,
        use_preset_overrides=not args.feature_presets_only,
        concurrency=args.concurrency,
        emitter=viewer_emitter,
        config=HarnessConfig(
            use_gates=not args.no_gates,
            use_contrast_queries=not args.no_contrast_queries,
            use_relevance_filter=not args.no_relevance_filter,
            adaptive_rounds=not args.no_adaptive_rounds,
            min_rounds=args.min_rounds,
            eval_mode=not args.no_eval_mode,
            use_knowledge_pack=not args.no_knowledge_pack,
            use_paper_extractor=args.paper_extractor,
            use_answerer_query_planner=args.frontier_mode or args.answerer_query_planner,
            answerer_query_fallback=(
                args.answerer_query_fallback
                or (not args.frontier_mode and not args.no_answerer_query_fallback)
            ),
            skeptical_evidence_mode=args.frontier_mode or args.skeptical_evidence_mode,
            use_bare_answer_preservation=args.frontier_mode or args.bare_answer_preservation,
            use_rerank=args.rerank,
            use_axis_breadth=args.axis_breadth,
            use_max_specificity=args.max_specificity,
            use_ensemble=args.ensemble,
        ),
    )
    counts = summarize_retrieval_guided_results(rows)
    print(f"Wrote retrieval-guided eval artifacts: {args.out_dir}")
    print(f"Cases: {len(rows)}")
    for key in sorted(counts):
        print(f"{key}: {counts[key]}")
    if args.dry_run:
        print("Dry run: model API was not called.")
    if args.no_retrieve:
        print("Retrieval disabled: PubMed was not called.")
    if args.viewer_url:
        print(f"Viewer live stream: {args.viewer_url.rstrip('/')}")
    return 0


def cmd_benchmark_judge_rescore(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir)
    results_path = run_dir / "retrieval_guided_results.jsonl"
    if not results_path.exists():
        raise FileNotFoundError(f"no retrieval_guided_results.jsonl in {run_dir}")
    answer_keys = {
        row["case_id"]: answer_key_from_manifest_row(row)
        for row in load_failed_manifest(args.manifest)
    }
    judge_client = OpenAICompatibleChatClient.from_env(model=args.model)
    rescored: list[dict[str, object]] = []
    counts: dict[str, int] = {}
    rows = [json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for index, row in enumerate(rows, start=1):
        case_id = row.get("case_id")
        final = row.get("model_final_diagnosis")
        key = answer_keys.get(case_id)
        if key is None:
            verdict_fields = {"score": "not_run", "score_method": "missing_answer_key"}
        else:
            verdict = score_diagnosis(
                candidate=final,
                expected=key["diagnosis"],
                aliases=tuple(key.get("aliases", ())),
                judge_client=judge_client,
            )
            verdict_fields = {
                "score": verdict.score,
                "score_method": verdict.method,
                "judge_match_type": verdict.match_type,
                "judge_rationale": verdict.rationale,
            }
        counts[verdict_fields["score"]] = counts.get(verdict_fields["score"], 0) + 1
        merged = {**row, **verdict_fields}
        rescored.append(merged)
        if args.progress:
            print(
                f"[{index}/{len(rows)}] {case_id} lexical={row.get('lexical_score')} "
                f"judge={verdict_fields['score']} ({verdict_fields.get('judge_match_type')})",
                file=sys.stderr,
            )
    out_path = run_dir / "judge_rescored_results.jsonl"
    with out_path.open("w", encoding="utf-8") as handle:
        for row in rescored:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    print(f"Wrote {out_path}")
    print(f"Cases: {len(rescored)}")
    for key_name in sorted(counts):
        print(f"{key_name}: {counts[key_name]}")
    return 0


def _path_arg(value: str | None, default: Path) -> Path:
    if value:
        return Path(value)
    return default


def _emit_json(payload: dict[str, object], out: str | None) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if out:
        output_path = Path(out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
        print(f"Wrote {out}")
    else:
        print(text, end="")


def _read_queries_jsonl(path: str | Path) -> list[str]:
    queries: list[str] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if isinstance(payload, str):
                queries.append(payload)
            elif isinstance(payload, dict) and isinstance(payload.get("query"), str):
                queries.append(payload["query"])
            else:
                raise ValueError(f"query row must be a string or object with query at {path}:{line_number}")
    return queries


def _read_json_object(path: str | Path, label: str) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} JSON must be an object")
    return payload


def _ncbi_client_from_args(args: argparse.Namespace) -> NcbiClient:
    if not args.email:
        print(
            "warning: set --email or NCBI_EMAIL so NCBI can contact you about automated traffic.",
            file=sys.stderr,
        )
    return NcbiClient(
        NcbiConfig(
            tool=args.tool,
            email=args.email,
            api_key=args.api_key,
            verify_tls=not args.insecure,
            min_interval_seconds=args.sleep,
        )
    )


def _print_text_result(result: dict[str, object]) -> None:
    print(f"Query: {result['query']}")
    print(f"Total PubMed matches: {result['count']}")
    translation = result.get("query_translation")
    if translation:
        print(f"Translated query: {translation}")
    print()
    articles = result.get("articles", [])
    assert isinstance(articles, list)
    for index, article in enumerate(articles, start=1):
        assert isinstance(article, dict)
        print(f"{index}. {article.get('title') or '[no title]'}")
        journal = article.get("journal") or "[unknown journal]"
        year = article.get("publication_year") or "n.d."
        print(f"   PMID: {article.get('pmid')} | {journal} | {year}")
        doi = article.get("doi")
        if doi:
            print(f"   DOI: {doi}")
        abstract = article.get("abstract")
        if abstract:
            abstract_text = str(abstract)
            if len(abstract_text) > 600:
                abstract_text = abstract_text[:597].rstrip() + "..."
            print(f"   Abstract: {abstract_text}")
        print(f"   URL: {article.get('url')}")
        print()


def _print_pmc_text_result(result: dict[str, object]) -> None:
    print(f"Query: {result['query']}")
    print(f"Total PMC matches: {result['count']}")
    translation = result.get("query_translation")
    if translation:
        print(f"Translated query: {translation}")
    print()
    articles = result.get("articles", [])
    assert isinstance(articles, list)
    _print_pmc_article_dicts(articles)


def _print_pmc_articles(articles: object) -> None:
    if not isinstance(articles, list):
        articles = list(articles)
    _print_pmc_article_dicts([article.to_dict() for article in articles])


def _print_pmc_article_dicts(articles: list[dict[str, object]]) -> None:
    for index, article in enumerate(articles, start=1):
        print(f"{index}. {article.get('title') or '[no title]'}")
        journal = article.get("journal") or "[unknown journal]"
        year = article.get("publication_year") or "n.d."
        print(f"   PMCID: {article.get('pmcid')} | PMID: {article.get('pmid') or 'n/a'} | {journal} | {year}")
        doi = article.get("doi")
        if doi:
            print(f"   DOI: {doi}")
        abstract = article.get("abstract")
        if abstract:
            abstract_text = str(abstract)
            if len(abstract_text) > 600:
                abstract_text = abstract_text[:597].rstrip() + "..."
            print(f"   Abstract: {abstract_text}")
        sections = article.get("sections", [])
        if isinstance(sections, list):
            print(f"   Sections: {len(sections)}")
        print(f"   URL: {article.get('url')}")
        print()


if __name__ == "__main__":
    raise SystemExit(main())
