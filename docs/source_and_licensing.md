# Source And Licensing Policy

ClinicalHarness retrieves evidence to answer benchmark cases. That is legally and ethically different from building a public dataset or training corpus, but source constraints still matter.

This document is research-engineering guidance, not legal advice.

NeurologyBM owns benchmark source licensing and release-tier decisions. ClinicalHarness should preserve those decisions in run manifests and should not independently publish transformed case prompts or answer keys.

## Use Categories

### Private Benchmarking

Locked or licensed case challenges may be used internally if access terms permit it. The repo should not commit or redistribute the case text unless permission or license allows it.

## Local Private Areas

ClinicalHarness reserves these paths for local-only material and ignores them in git:

- `docs/DO NOT COMMIT TO GITHUB/`
- `private/`
- `local_private/`

Use those paths for licensed paper notes, locked-source excerpts, private prompts, private run traces, or anything whose redistribution status is unclear. Public docs should contain only short paraphrased design lessons, public benchmark identifiers, and source/license metadata needed for evaluation provenance.

Allowed artifacts:

- source pointer
- citation
- case id
- aggregate scores
- private local run trace if access-controlled

Avoid committing:

- copied challenge text
- transformed prompts from locked sources
- answer keys from proprietary sources

### Public Benchmark Release

Public benchmark items need compatible rights for the transformed prompt, answer key, and rationale.

Preferred sources:

- CC0
- CC BY
- CC BY-SA after ShareAlike review
- explicitly permitted institutional datasets

### Training Data

Training data has the strictest requirements. Do not train on sources unless the license and terms permit the intended use.

Avoid by default:

- noncommercial content for commercial workflows
- no-derivatives content for transformed examples
- proprietary challenge text
- licensed articles without training permission

## PubMed Specific Notes

PubMed provides metadata and abstracts through NCBI services. PubMed retrieval does not imply that article full text is free to reuse or train on.

For every PubMed evidence record, store:

- PMID
- DOI if available
- journal
- publication year
- publication type
- URL
- query and rank

If full text is needed, use PMC/Open Access APIs or publisher-specific access with license checks.

## PMC Specific Notes

ClinicalHarness can fetch PMC JATS XML and parse article metadata, abstract, license marker, and body sections. PMC availability does not automatically make all downstream uses unrestricted. Preserve:

- PMCID
- PMID, when available
- DOI
- article title
- journal
- publication year
- license marker or license URL
- section titles and retrieved text summaries
- retrieval timestamp

For benchmark attempts, source-exclusion controls must block or flag matching PMCID when the original source PMCID is known.

## Practical Rules

- Keep raw benchmark case text out of git unless the source permits redistribution.
- Keep run traces with locked text local or encrypted if needed.
- For public papers, report aggregate scores and short compliant excerpts only when allowed.
- For training, use a separate license-reviewed dataset, not arbitrary retrieval logs.
- Preserve provenance for every evidence item.
