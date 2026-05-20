"""Command line interface for ClinicalOrchestra."""

from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.error import URLError

from .ncbi import NcbiClient, NcbiConfig
from .pubmed import pubmed_search


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
        prog="clinical-orchestra",
        description="ClinicalOrchestra research CLI.",
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

    return parser


def add_ncbi_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--email", default=os.getenv("NCBI_EMAIL"), help="Contact email for NCBI requests.")
    parser.add_argument("--api-key", default=os.getenv("NCBI_API_KEY"), help="Optional NCBI API key.")
    parser.add_argument("--tool", default="ClinicalOrchestra", help="NCBI tool name.")
    parser.add_argument("--sleep", type=float, default=0.34, help="Minimum seconds between requests.")
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification. Intended only for broken local certificate stores.",
    )


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


if __name__ == "__main__":
    raise SystemExit(main())
