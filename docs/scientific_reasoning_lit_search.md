# Scientific Reasoning Literature Search

Last refreshed: 2026-06-05.

This page tracks scientific reasoning systems that can inspire ClinicalHarness's diagnosis-attempt engine. The main interest is not whether a system is open source. It is the reusable design pattern: verifiable subgoals, test-time search, evidence synthesis, multi-agent critique, cost-aware workups, and benchmarkable run traces.

ClinicalHarness is still a research system for diagnostic benchmark attempts. It should not become clinical decision support or patient-specific medical advice.

## Diagnosis-Relevant Patterns

1. Formal math is ahead because it has hard verifiers. Lean compiler feedback gives systems like LEAP and AlphaProof a reliable accept/reject signal. Diagnosis needs approximate verifiers: source-exclusion checks, citation support, evidence contradiction checks, phenotype ontology consistency, and held-out answer-key scoring.
2. The best systems decompose the problem before solving it. The diagnosis analogue is a DAG of subclaims: demographics, tempo, localization, syndrome, disease mechanisms, discriminating findings, differential branches, and evidence requirements.
3. Test-time compute works when it is structured. Useful patterns include MCTS, beam search, evolutionary search, verifier-guided retry, and multi-agent debate. "Think longer" is less useful than "search more branches and verify each one."
4. Scientific agents need domain tools. For diagnosis this means PubMed, source exclusion, HPO/Monarch-style phenotype matching, PubTator-style entity normalization, disease ontologies, guideline retrieval, and benchmark scoring.
5. Literature synthesis should be measured at the claim level. The answer should cite evidence records for specific claims, not merely list papers.
6. Diagnostic systems should evaluate process, not just final answer. Sequential diagnosis benchmarks and trajectory benchmarks are especially relevant because they score what evidence the system asks for and when it stops.

## High-Priority Inspiration

| Work | Domain | Pattern to Borrow | Diagnosis Transfer |
| --- | --- | --- | --- |
| [LEAP: Supercharging LLMs for Formal Mathematics with Agentic Frameworks](https://arxiv.org/abs/2606.03303) | Formal math | Blueprint DAG, informal-to-formal translation, compiler-feedback repair, recursive subgoal proving. | Build a diagnosis DAG where each subclaim requires a structured verifier: cited evidence, source-exclusion status, ontology match, or answer-key rubric. |
| [Advancing Mathematics Research with AI-Driven Formal Proof Search](https://arxiv.org/abs/2605.22763) | Open math problems | Formal proof search on real open problems with cost-aware agents. | Treat hard cases as search problems with explicit budget, branch records, and verification events. |
| [Olympiad-Level Formal Mathematical Reasoning with Reinforcement Learning](https://www.nature.com/articles/s41586-025-09833-y) | Formal math | AlphaProof-style RL using Lean as an environment and verifier. | Train or tune query/action policies on synthetic cases where feedback is deterministic, then evaluate on held-out diagnostic challenges. |
| [Solving Olympiad Geometry Without Human Demonstrations](https://www.nature.com/articles/s41586-023-06747-5) | Geometry | Neuro-symbolic system plus synthetic data generation. | Combine LLM search with symbolic phenotype graphs. Synthetic neurology cases can stress rare localizations and syndromes. |
| [DeepSeek-Prover-V2](https://arxiv.org/abs/2504.21801) | Formal math | Recursive theorem proving and subgoal decomposition in Lean. | Decompose diagnosis into localized subproblems: syndrome, localization, etiology, confirmatory test, and mimics. |
| [Goedel-Prover-V2](https://arxiv.org/abs/2508.03613) | Formal math | Scaffolded data synthesis and self-correction for theorem proving. | Generate scaffolded diagnostic reasoning traces from public/synthetic cases, then enforce evidence-backed self-correction. |
| [AlphaEvolve](https://arxiv.org/abs/2506.13131) | Algorithm discovery | Evolutionary code/search loop with automatic evaluators. | Evolve query templates, ranking heuristics, and multi-agent policies against benchmark score, cost, and leakage penalties. |
| [FunSearch](https://www.nature.com/articles/s41586-023-06924-6) | Program search for math/algorithms | LLM generates candidate programs; evaluator selects reusable discoveries. | Ask models to generate retrieval and scoring functions, not just answers. Keep only variants that improve held-out case performance. |
| [AI Co-Scientist](https://arxiv.org/abs/2502.18864) | Biomedical hypothesis generation | Generate-debate-evolve multi-agent system for testable hypotheses. | Use separate agents for differential proposal, evidence hunting, mechanism checking, and skeptical critique. |
| [Robin: A Multi-Agent System for Automating Scientific Discovery](https://arxiv.org/abs/2505.13400) | Lab-in-the-loop biomedical discovery | Integrates literature search, hypothesis generation, experiment planning, data analysis, and hypothesis update. | Strong model for a closed-loop diagnosis research agent that updates a differential after each evidence batch. |
| [OpenScholar](https://www.nature.com/articles/s41586-025-10072-4) | Scientific literature synthesis | Retrieval over large paper corpora, citation-backed synthesis, self-feedback. | Model the answer generator around claim-specific PubMed evidence and citation correctness. |
| [PaperQA2](https://arxiv.org/abs/2409.13740) | Scientific literature QA | Agentic literature retrieval, citation traversal, contradiction detection, LitQA2 benchmark. | Add contradiction mining and evidence recall metrics to case runs. |
| [The AI Scientist-v2](https://arxiv.org/abs/2504.08066) | Automated AI research | Progressive agentic tree search and experiment-manager orchestration. | Use tree search over diagnostic strategies while a run manager enforces budget, provenance, and stopping rules. |
| [Sequential Diagnosis with Language Models / MAI-DxO](https://arxiv.org/abs/2506.22405) | Diagnostic reasoning | Sequential workup, virtual physician panel, cost-aware test selection. | Add a mode where the agent requests evidence/tests in steps and records diagnostic value versus cost. |
| [PULSE: Human-AI Co-reasoning for Clinical Diagnosis](https://arxiv.org/abs/2603.10492) | Clinical diagnosis | Evidence-integrated medical language agent with case-report benchmark. | Directly relevant to ClinicalHarness's literature-grounded diagnosis attempts, with caution around clinical safety framing. |
| [DeepRare](https://pubmed.ncbi.nlm.nih.gov/41708847/) | Rare disease diagnosis | Multi-agent rare disease diagnosis using HPO terms, genetic variants, and many tools. | Strong model for phenotype-first rare/neurologic differential ranking with traceable evidence. |

## Formal Reasoning And Verifiable Search

| Work | Domain | Notes for ClinicalHarness |
| --- | --- | --- |
| [LEAP](https://arxiv.org/abs/2606.03303) | Lean theorem proving | Best immediate inspiration for a diagnosis-plan DAG and verifier-driven repair loop. |
| [AlphaProof](https://www.nature.com/articles/s41586-025-09833-y) | Lean theorem proving | Shows the value of grounded RL environments. Diagnosis lacks a perfect kernel, so the verifier layer must be explicit and plural. |
| [AlphaProof Nexus / AI-driven formal proof search](https://arxiv.org/abs/2605.22763) | Open math research | Good example of deploying agents against unsolved problems with per-problem cost accounting. |
| [DeepSeek-Prover-V2](https://arxiv.org/abs/2504.21801) | Lean theorem proving | Subgoal decomposition is a useful pattern for localizing and etiologic reasoning. |
| [Goedel-Prover-V2](https://arxiv.org/abs/2508.03613) | Lean theorem proving | Scaffolded data synthesis suggests using synthetic public cases for process-supervision data. |
| [Leanabell-Prover-V2](https://arxiv.org/abs/2507.08649) | Lean theorem proving | Verifier-integrated RL pattern; lower priority than LEAP/AlphaProof but useful for reward design. |
| [AlphaGeometry](https://www.nature.com/articles/s41586-023-06747-5) | Geometry | Neuro-symbolic architecture: LLM proposes constructions, symbolic system verifies. |
| [AlphaGeometry2](https://arxiv.org/abs/2502.03544) | Geometry | Follow-up geometry system; useful for seeing how a domain-specific formal language grows. |
| [TongGeometry](https://www.nature.com/articles/s42256-025-01164-x) | Geometry problem generation | Proposes and solves new geometry problems. Suggests generating adversarial synthetic diagnostic cases. |
| [AIPS: Proving Olympiad Algebraic Inequalities](https://arxiv.org/abs/2406.14219) | Inequality proving | Another synthetic-data plus solver system, useful mainly for benchmark generation ideas. |
| [Achieving Gold-Medal-Level Olympiad Reasoning via Simple and Unified Scaling](https://arxiv.org/abs/2605.13301) | Math and physics reasoning | Watch for recipes that combine SFT, RL with verifiable rewards, proof-level RL, and test-time scaling. |
| [P1: Mastering Physics Olympiads with Reinforcement Learning](https://arxiv.org/abs/2511.13612) | Physics | Physics is closer to biomed than pure math in needing models of the world, units, and constraints. |

## Program, Algorithm, And Evolutionary Discovery

| Work | Domain | Notes for ClinicalHarness |
| --- | --- | --- |
| [AlphaEvolve](https://arxiv.org/abs/2506.13131) | Algorithm and scientific discovery | Best template for evolving ClinicalHarness components against objective metrics. |
| [Mathematical Exploration and Discovery at Scale](https://arxiv.org/abs/2511.02864) | Mathematical constructions | Shows how AlphaEvolve-style search can be combined with reasoning and proof assistants. |
| [FunSearch](https://www.nature.com/articles/s41586-023-06924-6) | LLM-guided program search | Use the pattern for query planners and rankers that can be automatically scored. |
| [AlphaTensor](https://www.nature.com/articles/s41586-022-05172-4) | Matrix multiplication | Classic example of framing discovery as search in a verifiable environment. |
| [AlphaDev](https://www.nature.com/articles/s41586-023-06004-9) | Sorting/hash algorithms | Reinforcement learning over code/actions with executable feedback. |
| [FunBO](https://arxiv.org/abs/2406.04824) | Bayesian optimization | Shows reuse of FunSearch for discovering acquisition functions; relevant to optimizing search budgets. |

## Scientific Literature Synthesis And Research Agents

| Work | Domain | Notes for ClinicalHarness |
| --- | --- | --- |
| [OpenScholar](https://www.nature.com/articles/s41586-025-10072-4) | Scientific literature synthesis | Strong reference for claim-grounded answers and ScholarQABench-style evaluation. |
| [PaperQA](https://arxiv.org/abs/2312.07559) | Scientific RAG | Earlier retrieval-augmented scientific QA agent. |
| [PaperQA2](https://arxiv.org/abs/2409.13740) | Scientific literature QA | High priority for citation traversal and contradiction detection. |
| [SciRAG](https://arxiv.org/abs/2511.14362) | Citation-aware RAG | Useful for adaptive retrieval, citation-graph reasoning, and outline-guided synthesis. |
| [STORM](https://arxiv.org/abs/2402.14207) | Long-form research writing | Perspective-guided question asking can map to differential-specific search perspectives. |
| [ResearchAgent](https://arxiv.org/abs/2404.07738) | Research ideation | Uses academic graph retrieval and reviewing agents for iterative refinement. |
| [IRIS](https://arxiv.org/abs/2504.16728) | Research ideation | Human-in-the-loop MCTS and query-based literature synthesis. |
| [ResearchBench](https://arxiv.org/abs/2503.21248) | Scientific discovery benchmark | Decomposes discovery into inspiration retrieval, hypothesis composition, and hypothesis ranking. |
| [HypoAgents](https://arxiv.org/abs/2508.01746) | Hypothesis generation | Bayesian and entropy-driven agent collaboration. Maps to uncertainty-driven evidence search. |
| [BioDisco](https://arxiv.org/abs/2508.01285) | Biomedical hypothesis generation | Dual-mode evidence and temporal evaluation are useful for testing whether agents predict later discoveries. |
| [Robin](https://arxiv.org/abs/2505.13400) | Automated scientific discovery | Lab-in-the-loop discovery system from literature search through data analysis and revised hypotheses. |
| [The AI Scientist-v2](https://arxiv.org/abs/2504.08066) | Automated AI research | Progressive agentic tree-search framework with an experiment-manager agent. |
| [Towards End-to-End Automation of AI Research](https://www.nature.com/articles/s41586-026-10265-5) | Automated AI research | Peer-reviewed AI Scientist line; useful for seeing how end-to-end research artifacts are evaluated. |
| [SciResearcher](https://arxiv.org/abs/2605.01489) | Frontier scientific reasoning | Watch for bio/chem reasoning agent training data and tool-use policies. |
| [DeepResearcher](https://arxiv.org/abs/2504.03160) | Deep research agents | End-to-end training of search-enabled research agents with real web interactions. |
| [OR-Agent](https://arxiv.org/abs/2602.13769) | Automated algorithm discovery | Structured hypothesis management, environment interaction, verbal gradients, and long-term reflection. |
| [AgenticSciML](https://arxiv.org/abs/2511.07262) | Scientific machine learning | Multi-agent propose-critique-refine loop for scientific modeling. |
| [DeepResearch Bench](https://arxiv.org/abs/2506.11763) | Deep research evaluation | Useful for report-level rubric design, effective citations, and citation accuracy. |
| [FrontierScience](https://arxiv.org/abs/2601.21165) | Expert scientific tasks | Useful because it scores research process with granular rubrics, not only final answers. |
| [Humanity's Last Exam](https://labs.scale.com/papers/humanitys-last-exam) | Expert knowledge benchmark | Useful as a hard closed-ended benchmark, but not sufficient for autonomous research capability. |
| [FutureHouse HLE Bio/Chem audit](https://www.futurehouse.org/research-announcements/hle-exam) | Benchmark QA | Important caution: expert benchmarks can contain wrong answers, especially in biology and chemistry. |

## Biomedical, Chemistry, And Medical Agents

| Work | Domain | Notes for ClinicalHarness |
| --- | --- | --- |
| [AI Co-Scientist](https://arxiv.org/abs/2502.18864) | Biomedical discovery | Generate, debate, evolve, and rank hypotheses with scientist objectives. |
| [From Literature to Hypotheses: AI Co-Scientist CoDHy](https://arxiv.org/abs/2603.00612) | Cancer drug combinations | Knowledge-graph-backed hypothesis generation from structured databases plus literature. |
| [Towards a Medical AI Scientist](https://arxiv.org/abs/2603.28589) | Clinical research ideation | Clinician-engineer co-reasoning and traceable evidence conversion. |
| [Biomni](https://pubmed.ncbi.nlm.nih.gov/40501924/) | General biomedical agent | Broad biomedical action space; useful for tool registry and biological task automation ideas. |
| [Biomni GitHub](https://github.com/snap-stanford/Biomni) | Biomedical agent implementation | Useful implementation reference if we later add biomedical tool execution. |
| [TxAgent](https://arxiv.org/abs/2503.10970) | Therapeutic reasoning | ToolUniverse-style registry of biomedical APIs; not a diagnosis target, but strong tool-routing inspiration. |
| [Coscientist](https://www.nature.com/articles/s41586-023-06792-0) | Autonomous chemistry lab | Full loop from planning to hardware execution; useful for thinking about action traces and safety gates. |
| [ChemCrow](https://arxiv.org/abs/2304.05376) | Chemistry tool agent | Domain tools can compensate for generic LLM weaknesses. |
| [SciAgents](https://pubmed.ncbi.nlm.nih.gov/39696898/) | Materials/biomedical graph reasoning | Bioinspired multi-agent graph reasoning; useful for knowledge graph traversal patterns. |
| [BioAgents](https://www.nature.com/articles/s41598-025-25919-z) | Bioinformatics multi-agent system | Useful for agent roles around data analysis, validation, and report generation. |
| [BioLab](https://sciety.org/articles/activity/10.1101/2025.09.03.674085) | Life-sciences research automation | Watchlist item for end-to-end bio workflows with biological foundation models. |
| [BioMARS](https://arxiv.org/abs/2507.01485) | Autonomous biological experiments | Multi-agent robotic system for biological experiments; useful for safety-gated action planning. |
| [PubTator3](https://www.ncbi.nlm.nih.gov/research/pubtator3/) | Biomedical entity annotation | Not an agent, but important infrastructure for normalizing diseases, genes, chemicals, and variants. |
| [Human Phenotype Ontology](https://hpo.jax.org/) | Phenotype ontology | Essential for neurology and rare disease query generation, matching, and evidence checks. |
| [Monarch Initiative](https://monarchinitiative.org/) | Phenotype-genotype-disease graph | Useful for phenotype-first candidate diagnosis expansion. |

## Diagnosis-Specific Benchmarks And Systems

| Work | Domain | Notes for ClinicalHarness |
| --- | --- | --- |
| [Sequential Diagnosis with Language Models / SDBench / MAI-DxO](https://arxiv.org/abs/2506.22405) | Sequential diagnosis | Strongest current public pattern for cost-aware diagnostic workups and virtual panel orchestration. |
| [Microsoft AI: The Path to Medical Superintelligence](https://microsoft.ai/news/the-path-to-medical-superintelligence/) | Diagnostic orchestrator | Product/research framing around MAI-DxO; use cautiously because it is company-authored. |
| [PULSE](https://arxiv.org/abs/2603.10492) | Evidence-integrated clinical diagnosis | Closest architectural peer for literature-grounded diagnosis attempts. |
| [DeepRare](https://pubmed.ncbi.nlm.nih.gov/41708847/) | Rare disease diagnosis | Highly relevant for neurology cases with HPO terms, genetics, and traceable evidence. |
| [MedClarify](https://arxiv.org/abs/2602.17308) | Diagnostic information seeking | Follow-up question generation maps to sequential case unfolding. |
| [DDX-TRACE](https://arxiv.org/abs/2605.23629) | Diagnostic trajectories in VLMs | Process benchmark for evidence acquisition, differential updates, and stopping behavior. |
| [DiagnosisArena](https://arxiv.org/abs/2505.14107) | Diagnostic reasoning benchmark | 1,113 case/diagnosis pairs; useful caution against MCQ-style overestimation. |
| [Towards Accurate Differential Diagnosis with LLMs](https://arxiv.org/abs/2312.00164) | Differential diagnosis | Earlier NEJM-CPC style benchmark with clinician comparison. |
| [Superhuman Performance on the Reasoning Tasks of a Physician](https://arxiv.org/abs/2412.10849) | Physician reasoning tasks | Useful for task taxonomy and physician-judged rubrics, but treat "superhuman" claims cautiously. |
| [Agentic memory-augmented retrieval and evidence grounding for medical QA](https://pubmed.ncbi.nlm.nih.gov/41713127/) | Medical QA | Recent open-source agentic retrieval/evidence grounding pattern. |
| [Active Knowledge Retrieval for Large Medical Reasoning Models](https://pubmed.ncbi.nlm.nih.gov/41528309/) | Medical retrieval | Reasoning-retrieval-information integration pattern. |

## Concrete Backlog Ideas

1. Add a `DiagnosisDAG` or `ReasoningGraph` schema inspired by LEAP. Nodes should be problem representation, localization claim, syndrome claim, candidate diagnosis, evidence need, evidence record, contradiction, and final answer.
2. Add verifier events to the run ledger. Examples: `source_exclusion_checked`, `citation_support_checked`, `phenotype_match_checked`, `contradiction_checked`, and `answer_key_scored`.
3. Add a branch-search runner. Start with deterministic beam search over PubMed query templates and candidate diagnoses before adding LLM calls.
4. Add a "skeptic" evidence miner that searches for mimics and refuting evidence, not just supporting articles.
5. Add citation-level scoring: each answer claim should map to one or more `EvidenceRecord` ids and a support status.
6. Add diagnosis-process metrics: evidence recall, source leakage, final diagnosis match, localization match, differential quality, contradiction handling, token/API cost, latency, and unsafe recommendation flags.
7. Add phenotype normalization using HPO/Monarch/PubTator-style infrastructure before query generation.
8. Add synthetic case generation for public, redistributable tests. Use synthetic cases to tune search policies without contaminating locked benchmarks.
9. Add evolutionary optimization for query templates and ranking heuristics, borrowing from AlphaEvolve/FunSearch, with source leakage and cost as penalties.
10. Add sequential diagnosis mode later: the runner should decide what information to request or retrieve next, update the differential, and stop when confidence and evidence support are sufficient.

## Watch Criteria

Prioritize new papers if they include at least one of:

- a public benchmark with hard, expert-written tasks;
- a verifiable environment or explicit verifier;
- evidence-grounded biomedical reasoning;
- multi-step tool use with traceable actions;
- source/citation correctness evaluation;
- cost-aware search or test selection;
- open code or enough implementation detail to reproduce the workflow.
