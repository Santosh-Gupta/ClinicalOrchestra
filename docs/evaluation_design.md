# Evaluation Design

ClinicalHarness is meant to compare models and tool policies on hard diagnosis cases. The key experimental variable is what information and tools the model can use.

Benchmark case construction and license tiering are owned by NeurologyBM. ClinicalHarness should preserve NeurologyBM case metadata in every run and apply source-exclusion controls when PMIDs, PMCIDs, DOIs, or source titles are available.

## Evaluation Modes

### Closed Book

The model receives only the case prompt.

Use for:

- measuring intrinsic medical knowledge
- comparing with NeurologyBM-style closed-book benchmarks
- checking whether retrieval actually helps

### PubMed Only

The model can search PubMed and read titles/abstracts.

Use for:

- realistic literature-supported diagnosis without general web noise
- rare disease and unusual presentation cases
- early agentic retrieval experiments

### Open Literature

The model can use PubMed, PMC full text where allowed, citation metadata, and guidelines where access permits.

Use for:

- deeper evidence synthesis
- comparing abstracts-only vs full-text retrieval
- evaluating citation-backed answers

### Web Enabled

The model can use general search and web pages where terms permit.

Use for:

- final challenge-solving mode
- source-diverse evidence gathering
- comparing medical literature vs broad web retrieval

## Scoring Dimensions

Final answer:

- exact diagnosis match
- acceptable alias match
- broader disease-family match
- wrong diagnosis

Clinical reasoning:

- localization quality
- differential quality
- key supporting evidence included
- key refuting evidence included
- missing red flags
- unsafe recommendation

Retrieval quality:

- relevant searches generated
- relevant articles retrieved
- evidence correctly interpreted
- citations support claims
- retrieval introduced distraction or bias

Efficiency:

- number of searches
- number of articles read
- total tokens
- latency
- API cost

## Diagnosis Answer Format

Future answer generation should emit structured JSON:

```json
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
```

## Leakage Controls

When using benchmark cases:

- Do not search exact title text unless the evaluation mode explicitly allows source lookup.
- Track whether the model retrieves the original case report.
- Optionally run two modes: `source_allowed` and `source_excluded`.
- Keep answer keys out of prompts and retrieval context.
- Preserve the case's license tier and split label in the run manifest.

For challenge sites with locked content, store pointers and aggregate scores rather than redistributing prompt text.
