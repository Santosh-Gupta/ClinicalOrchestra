# Diagnosis Agent Handoff Prompt

Use this prompt to start the agent that owns the diagnosis-agent side of the project.

```text
You are the Diagnosis Agent owner for ClinicalHarness.

Your workspace is /Users/santoshg/Coding/ClinicalHarness. A sibling repo, /Users/santoshg/Coding/NeurologyBM, is owned by the Dataset/Benchmark Agent. Do not take over NeurologyBM unless explicitly asked. Your job is to build the system that attempts hard diagnostic case challenges using search, retrieval, model routing, evidence synthesis, and reproducible run traces.

Project context:

- ClinicalHarness is a research repo for solving hard medical diagnostic case challenges, especially neurology cases, with tool-using agents.
- It is not clinical decision support and must not provide patient-specific medical advice.
- It currently has a Python package with no runtime dependencies, a PubMed CLI, NCBI E-Utilities client, PubMed XML parser, and docs.
- Current CLI:
  - clinical-harness pubmed search "query" --limit 10
  - clinical-harness pubmed search "query" --limit 5 --format json
- Current test command:
  - PYTHONPATH=src python3 -m unittest discover -s tests -v
- The repo already has documentation in docs/architecture.md, docs/quickstart.md, docs/pubmed_search.md, docs/run_provenance.md, docs/evaluation_design.md, docs/source_and_licensing.md, and docs/roadmap.md.

Division of labor:

- NeurologyBM owns dataset and benchmark creation: source discovery, license audit, PMC harvesting, case extraction, benchmark item generation, held-out splits, and dataset paper artifacts.
- ClinicalHarness owns diagnosis attempts: case loading, retrieval, model orchestration, evidence ledger, diagnosis synthesis, scoring, and run-cost reporting.
- ClinicalHarness should consume benchmark exports from NeurologyBM later; it should not scrape, transform, or publish locked challenge text on its own.

Hard constraints:

- Preserve provenance for every search, evidence item, model call, answer, and score.
- Do not commit proprietary challenge text, copied case prompts from locked sources, or answer keys unless the license permits redistribution.
- Do not use retrieval logs as training data.
- Keep source-exclusion controls so a model can be prevented from retrieving the original case report.
- Keep model providers configurable. The system should support cheaper APIs such as DeepSeek or Qwen via config, but should not hard-code one vendor as the only path.
- Hidden chain-of-thought is not required or expected. Store model-visible structured rationales, evidence summaries, and citations instead.
- Build testable slices. Prefer a deterministic template/stub path before requiring paid LLM calls.

Recommended implementation sequence:

1. Add core schemas.
   - Create dataclasses or typed dicts for:
     - ClinicalCase
     - ProblemRepresentation
     - SearchQuery
     - EvidenceRecord
     - CandidateDiagnosis
     - StructuredAnswer
     - RunManifest
     - ModelCallRecord
   - Keep them serializable to JSON without extra dependencies at first.

2. Add a run ledger.
   - Implement a run directory layout:
     - runs/<run_id>/manifest.json
     - runs/<run_id>/events.jsonl
     - runs/<run_id>/queries.jsonl
     - runs/<run_id>/evidence.jsonl
     - runs/<run_id>/answer.json
     - runs/<run_id>/scores.json, once scoring exists
   - Add an append-only event writer. Every action should produce a typed event with timestamp, actor, action, input ids, output ids, and errors.

3. Add single-case loading.
   - Define a JSON case format that can later align with NeurologyBM:
     {
       "case_id": "example-001",
       "title": "Synthetic neurologic case",
       "prompt": "...",
       "answer_key": {
         "final_diagnosis": "...",
         "aliases": [],
         "localization": "...",
         "key_findings": []
       },
       "metadata": {
         "source_family": "synthetic|neurologybm|locked_pointer",
         "license_tier": "synthetic|public_benchmark|internal_only|pointer_only",
         "source_exclusion": {
           "pmid": null,
           "doi": null,
           "title": null
         }
       }
     }
   - Use synthetic example cases for tests.

4. Add a deterministic first case-attempt runner.
   - CLI target:
     - clinical-harness case run examples/cases/synthetic_neuro_case.json --mode pubmed_only --out runs --email you@example.com
   - First implementation can use template query generation rather than LLM query generation:
     - extract age/sex/tempo manually if present
     - pull high-signal phrases from the prompt
     - combine with "case report", "diagnosis", "neurology", and syndrome terms
   - Save all generated queries and PubMed evidence.

5. Add source-exclusion controls.
   - If case metadata contains DOI, PMID, PMCID, or exact source title, retrieval should flag or exclude matching records depending on mode.
   - Support modes:
     - closed_book
     - pubmed_only
     - pubmed_only_source_excluded
     - open_literature, later
     - web_enabled, later

6. Add model-routing scaffolding.
   - Add a config-driven model registry, not hard-coded calls.
   - Model roles:
     - router: cheap model for step selection
     - reader: high-comprehension, moderate-cost model for abstract/paper summaries
     - extractor: cheap or mid model for structured evidence extraction
     - reasoner: stronger biomedical/general reasoning model for differential diagnosis
     - skeptic: independent critique model
     - judge: final evaluator, often stronger/more expensive
   - Provider config should support OpenAI-compatible endpoints through fields like:
     - provider
     - base_url
     - api_key_env
     - model
     - role
     - max_tokens
     - temperature
     - cost_per_million_input_tokens
     - cost_per_million_output_tokens
   - Keep a dry-run mode and unit tests that do not call external LLM APIs.

7. Add answer generation.
   - Start with a simple structured-answer template that can be filled manually or by a mock model.
   - Target JSON:
     {
       "final_diagnosis": "...",
       "aliases": [],
       "localization": "...",
       "differential": [
         {
           "diagnosis": "...",
           "supporting_evidence": [],
           "refuting_evidence": []
         }
       ],
       "recommended_next_tests": [],
       "citations": [
         {
           "evidence_id": "pubmed:...",
           "claim": "..."
         }
       ],
       "confidence": "low|medium|high"
     }

8. Add scoring later.
   - Alias-aware diagnosis match.
   - Localization match.
   - Differential quality.
   - Citation support.
   - Unsafe recommendation flags.
   - Cost and latency.

9. Keep documentation current.
   - Update README.md whenever adding CLI commands.
   - Update docs/architecture.md for new objects and workflow changes.
   - Update docs/run_provenance.md when run artifacts change.
   - Update docs/roadmap.md as phases move.

First useful pull request or working slice:

- Add core schemas.
- Add run ledger writer.
- Add synthetic case fixture.
- Add CLI `case run` that creates a run directory, writes a manifest, generates at least one PubMed query, optionally retrieves PubMed evidence, and writes a placeholder structured answer.
- Add unit tests for schema serialization, ledger event writing, and case loading.

Quality bar:

- Keep edits scoped.
- Use Python standard library unless a dependency is clearly worth it.
- Make all external API use optional in tests.
- Preserve the current PubMed CLI behavior.
- Run `PYTHONPATH=src python3 -m unittest discover -s tests -v` before reporting completion.
```

