# PubMed Search Guide

This project starts with PubMed because it is a stable biomedical search API with structured identifiers and abstracts. PubMed is not enough to solve hard diagnosis cases by itself, but it is a useful first retrieval substrate.

## Query Construction

For diagnosis challenge work, useful queries usually combine:

- syndrome or localization
- temporal pattern
- distinctive symptom, lab, imaging phrase, or exposure
- demographic clue if it is diagnostically meaningful
- `case report` when looking for rare presentations

Examples:

```text
autoimmune encephalitis psychosis catatonia case report
```

```text
"new onset refractory status epilepticus" autoimmune case report
```

```text
(MOGAD OR "myelin oligodendrocyte") seizure adolescent case report
```

```text
"rapidly progressive dementia" ataxia neuropathy case report
```

```text
"optic neuritis" "area postrema" NMOSD case report
```

## High Recall vs High Precision

Use high-recall queries early:

```text
encephalitis psychosis seizure young woman
```

Use high-precision queries once the syndrome is clearer:

```text
"anti-NMDA receptor encephalitis" catatonia ovarian teratoma
```

The future query generator should produce both styles and label them.

## Neurology-Oriented Search Axes

Localization:

- cortex, brainstem, cerebellum, spinal cord, nerve root, peripheral nerve, neuromuscular junction, muscle

Tempo:

- hyperacute, acute, subacute, relapsing, progressive, episodic

Syndrome:

- seizure, aphasia, ataxia, myelopathy, neuropathy, psychosis, catatonia, movement disorder, headache, optic neuritis

Etiology:

- vascular, autoimmune, infectious, toxic-metabolic, genetic, neoplastic, paraneoplastic, degenerative, functional

## Case-Report Filters

Useful terms:

```text
case report
case reports[Publication Type]
case series
diagnostic challenge
differential diagnosis
```

The CLI currently accepts raw PubMed query text and lets NCBI translate terms.

## Output Fields

The PubMed CLI returns:

- query
- translated query
- total match count
- PMIDs
- title
- abstract
- journal
- publication year
- publication types
- DOI
- PubMed URL

These fields are enough for first-pass evidence retrieval and provenance.

## Future Query Generator

The LLM query generator should emit structured query candidates:

```json
{
  "query": "\"rapidly progressive dementia\" ataxia neuropathy case report",
  "intent": "rare syndrome search",
  "expected_evidence": "case reports with similar syndrome",
  "precision": "medium",
  "must_include": ["rapid progression", "ataxia"],
  "optional_terms": ["neuropathy", "myoclonus"]
}
```

Every generated query should be stored in the run trace.
