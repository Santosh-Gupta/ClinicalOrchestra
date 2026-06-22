import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import type { TraceEvent } from "../types";
import { ACTOR_COLOR, Badge, TYPE_GLYPH } from "./ui";

// Event types whose body is worth expanding. Others render head-only.
const EXPANDABLE = new Set([
  "problem_representation",
  "query_generated",
  "tool_call",
  "search_executed",
  "evidence_retrieved",
  "synthesis",
  "prompt_built",
  "model_call",
  "model_response",
  "answer",
  "judge",
]);

export function EventCard({
  event,
  expandVersion = 0,
  collapseVersion = 0,
}: {
  event: TraceEvent;
  expandVersion?: number;
  collapseVersion?: number;
}) {
  const expandable = EXPANDABLE.has(event.type);
  const displayTitle = eventTitle(event);
  const displaySummary = eventSummary(event);
  // Auto-expand the high-signal terminal events.
  const [open, setOpen] = useState(event.type === "answer" || event.type === "judge");
  const monoTitle = event.type === "query_generated" || event.type === "answer";

  useEffect(() => {
    if (expandVersion > 0 && expandable) setOpen(true);
  }, [expandVersion, expandable]);

  useEffect(() => {
    if (collapseVersion > 0) setOpen(false);
  }, [collapseVersion]);

  return (
    <div className="event fade-in">
      <div className="node" style={{ borderColor: ACTOR_COLOR[event.actor] }}>
        {TYPE_GLYPH[event.type] ?? "·"}
      </div>
      <div className={`card ${expandable ? "clickable" : ""}`}>
        <div
          className="card-head"
          onClick={expandable ? () => setOpen((v) => !v) : undefined}
        >
          <span className="actor-tag" style={{ color: ACTOR_COLOR[event.actor] }}>
            {event.actor}
          </span>
          <span className={`card-title ${monoTitle ? "mono" : ""}`}>{displayTitle}</span>
          {event.round != null && <span className="chip">r{event.round}</span>}
          {(event.status === "pass" ||
            event.status === "fail" ||
            event.status === "warn" ||
            event.status === "error") && <Badge status={event.status} />}
        </div>
        {displaySummary && !open && <div className="card-summary">{displaySummary}</div>}
        {open && (
          <div className="card-body">
            <EventBody event={event} />
            <RawEventDetails event={event} />
          </div>
        )}
      </div>
    </div>
  );
}

function eventSummary(event: TraceEvent): string | null {
  const p = event.payload as Record<string, any>;
  if (event.type === "tool_call" && p.tool === "pubmed_search") {
    const returned = p.returned_count != null ? `${p.returned_count} returned` : null;
    const attempt = p.attempt && p.attempt !== "initial" ? String(p.attempt) : null;
    const reason = p.reason ? String(p.reason).replace(/_/g, " ") : null;
    return [returned, attempt, reason].filter(Boolean).join(" · ") || event.summary || null;
  }
  if (event.type === "model_call") {
    const stage = String(p.stage ?? "");
    if (stage === "paper_screening") {
      if (p.recovered_from_error) {
        const attempt = p.attempt ? `attempt ${p.attempt}` : "retry";
        return `fixed after ${attempt}`;
      }
      if (p.retry_will_continue) {
        const attempt = p.attempt && p.max_attempts ? `attempt ${p.attempt}/${p.max_attempts}` : "retrying";
        return `retrying · ${attempt} · ${String(p.error ?? "temporary failure")}`;
      }
      const relevant = isRecord(p.parsed_json) && typeof p.parsed_json.relevant === "boolean"
        ? p.parsed_json.relevant
        : null;
      const excerpt = isRecord(p.parsed_json) && typeof p.parsed_json.relevant_excerpt === "string"
        ? p.parsed_json.relevant_excerpt
        : null;
      if (excerpt) return `${relevant === false ? "not relevant" : "relevant"} · ${excerpt}`;
      if (relevant !== null) return relevant ? "relevant to the case" : "not relevant to the case";
    }
    if (stage === "initial_clinical_assessment" && p.response_text) {
      return truncateInline(String(p.response_text), 180);
    }
  }
  return event.summary ?? null;
}

function eventTitle(event: TraceEvent): string {
  const p = event.payload as Record<string, any>;
  if (event.type === "tool_call" && p.tool === "pubmed_search") {
    const exactQuery = p.query_translation ?? p.attempted_query ?? p.query;
    if (exactQuery) return `PubMed search · ${truncateInline(String(exactQuery), 160)}`;
  }
  if (event.type === "tool_call" && p.tool === "pmc_fetch") {
    const pmcids = Array.isArray(p.pmcids) ? p.pmcids.filter(Boolean).slice(0, 3).join(", ") : "";
    return pmcids ? `PMC full-text fetch · ${pmcids}` : "PMC full-text fetch";
  }
  if (event.type === "model_call") {
    return modelCallTitle(event.title, p, event.round);
  }
  return event.title;
}

function modelCallTitle(fallback: string, p: Record<string, any>, round: number | null): string {
  const stage = String(p.stage ?? "");
  const failed = Boolean(p.error);
  if (stage === "paper_screening") {
    const paper = typeof p.paper_title === "string" && p.paper_title.trim()
      ? p.paper_title.trim()
      : typeof p.pmid === "string" && p.pmid.trim()
        ? `PMID ${p.pmid.trim()}`
        : typeof p.evidence_id === "string" && p.evidence_id.trim()
          ? p.evidence_id.trim()
          : "paper";
    const prefix = p.recovered_from_error
      ? "Paper screening fixed"
      : p.retry_will_continue
        ? "Paper screening retrying"
        : failed
          ? "Paper screening failed"
          : "Paper screening";
    return `${prefix} · ${truncateInline(paper, 110)}`;
  }
  if (stage === "initial_clinical_assessment") {
    return failed ? "Initial differential and search plan failed" : "Initial differential and search plan";
  }
  if (stage === "evidence_distillation") {
    const roundLabel = round != null ? `round ${round}` : "retrieval round";
    return failed ? `Evidence synthesis failed · ${roundLabel}` : `Evidence synthesis · ${roundLabel}`;
  }
  if (stage === "rerank_differential") {
    return failed ? "Differential rerank failed" : "Differential rerank";
  }
  if (stage === "final_answer") {
    const sample = /sample\s+\d+/i.exec(fallback)?.[0];
    return failed
      ? `Final diagnosis generation failed${sample ? ` · ${sample}` : ""}`
      : `Final diagnosis generation${sample ? ` · ${sample}` : ""}`;
  }
  if (stage === "judge_equivalence") {
    return failed ? "Judge equivalence check failed" : "Judge equivalence check";
  }
  return fallback;
}

function truncateInline(value: string, max: number): string {
  const cleaned = value.replace(/\s+/g, " ").trim();
  return cleaned.length > max ? `${cleaned.slice(0, max - 3)}...` : cleaned;
}

function EventBody({ event }: { event: TraceEvent }) {
  const p = event.payload as Record<string, any>;
  switch (event.type) {
    case "problem_representation":
      return <ProblemRepresentation p={p} />;

    case "query_generated":
      return (
        <>
          <dl className="kv">
            <dt>query id</dt>
            <dd>{p.query_id ?? firstString(p.output_ids) ?? "—"}</dd>
            <dt>intent</dt>
            <dd>{p.intent ?? "—"}</dd>
            <dt>generated by</dt>
            <dd>{p.generated_by ?? p.ledger_actor ?? "—"}</dd>
            <dt>source</dt>
            <dd>{p.source ?? "—"}</dd>
            {p.executed != null && (
              <>
                <dt>executed</dt>
                <dd>{String(p.executed)}</dd>
              </>
            )}
            {p.result_count != null && (
              <>
                <dt>result count</dt>
                <dd>{String(p.result_count)}</dd>
              </>
            )}
          </dl>
          {p.query && <p className="snippet">{String(p.query)}</p>}
        </>
      );

    case "tool_call":
      return <ToolCall p={p} />;

    case "search_executed":
      return (
        <dl className="kv">
          <dt>records</dt>
          <dd>{String(p.total ?? "—")}</dd>
          <dt>kept</dt>
          <dd>{String(p.kept ?? "—")}</dd>
          {p.retrieve !== undefined && (
            <>
              <dt>retrieval enabled</dt>
              <dd>{String(p.retrieve)}</dd>
            </>
          )}
        </dl>
      );

    case "evidence_retrieved":
      return (
        <>
          <dl className="kv">
            <dt>evidence id</dt>
            <dd>{p.evidence_id ?? "—"}</dd>
            <dt>query id</dt>
            <dd>{p.query_id ?? "—"}</dd>
            <dt>rank</dt>
            <dd>{p.rank ?? "—"}</dd>
            <dt>source</dt>
            <dd>
              {p.source_api ?? "pubmed"} · {p.source_scope ?? "abstract"}
            </dd>
            {p.relevance != null && (
              <>
                <dt>relevance</dt>
                <dd>{String(p.relevance)}</dd>
              </>
            )}
            <dt>journal</dt>
            <dd>{p.journal ?? "—"}</dd>
            {p.publication_year && (
              <>
                <dt>year</dt>
                <dd>{p.publication_year}</dd>
              </>
            )}
            <dt>pmid</dt>
            <dd>
              {p.url ? (
                <a href={p.url} target="_blank" rel="noreferrer">
                  {p.pmid}
                </a>
              ) : (
                (p.pmid ?? "—")
              )}
            </dd>
            {p.pmcid && (
              <>
                <dt>pmcid</dt>
                <dd>{p.pmcid}</dd>
              </>
            )}
            {p.doi && (
              <>
                <dt>doi</dt>
                <dd>{p.doi}</dd>
              </>
            )}
            {p.excluded && (
              <>
                <dt>excluded</dt>
                <dd>{p.exclusion_reason ?? "source match"}</dd>
              </>
            )}
          </dl>
          {p.abstract_snippet && <p className="snippet">{p.abstract_snippet}</p>}
          {p.full_text_snippet && (
            <details className="details-block">
              <summary>Full-text snippet</summary>
              <pre className="code-block">{String(p.full_text_snippet)}</pre>
            </details>
          )}
          {Array.isArray(p.publication_types) && p.publication_types.length > 0 && (
            <DetailList title="PUBLICATION TYPES" items={p.publication_types.slice(0, 8)} />
          )}
        </>
      );

    case "synthesis":
      return <Synthesis p={p} />;

    case "prompt_built":
      return <PromptBuilt p={p} />;

    case "model_call":
      return <ModelCall p={p} />;

    case "model_response":
      return <ModelResponse p={p} />;

    case "answer":
      return <Answer p={p} />;

    case "judge":
      return (
        <dl className="kv">
          <dt>score</dt>
          <dd>{p.score}</dd>
          <dt>match type</dt>
          <dd>{p.judge_match_type ?? "—"}</dd>
          <dt>method</dt>
          <dd>{p.score_method ?? "—"}</dd>
          <dt>expected</dt>
          <dd>{p.expected_diagnosis ?? "—"}</dd>
          <dt>model said</dt>
          <dd>{p.model_final_diagnosis ?? "—"}</dd>
          {p.judge_rationale && (
            <>
              <dt>rationale</dt>
              <dd>{p.judge_rationale}</dd>
            </>
          )}
        </dl>
      );

    default:
      return <p className="snippet">{event.summary}</p>;
  }
}

function RawEventDetails({ event }: { event: TraceEvent }) {
  return (
    <details className="details-block raw-event">
      <summary>Raw event JSON</summary>
      <pre className="code-block">{JSON.stringify(event, null, 2)}</pre>
    </details>
  );
}

function ToolCall({ p }: { p: Record<string, any> }) {
  const parameters = p.parameters ?? {};
  const queryText = p.attempted_query ?? p.query;
  const translatedQuery = p.query_translation ? String(p.query_translation) : null;
  const pmids: string[] = Array.isArray(p.pmids) ? p.pmids : [];
  const pmcids: string[] = Array.isArray(p.pmcids) ? p.pmcids : [];
  const outputIds: string[] = Array.isArray(p.output_evidence_ids) ? p.output_evidence_ids : [];
  const articles: any[] = Array.isArray(p.articles) ? p.articles : [];
  return (
    <>
      <dl className="kv">
        <dt>tool</dt>
        <dd>{p.tool ?? "—"}</dd>
        <dt>query id</dt>
        <dd>{p.query_id ?? "—"}</dd>
        {queryText && (
          <>
            <dt>submitted query</dt>
            <dd>{String(queryText)}</dd>
          </>
        )}
        {translatedQuery && (
          <>
            <dt>PubMed query</dt>
            <dd>{translatedQuery}</dd>
          </>
        )}
        <dt>attempt</dt>
        <dd>{p.attempt ?? "—"}</dd>
        <dt>limit</dt>
        <dd>{parameters.limit ?? "—"}</dd>
        <dt>sort</dt>
        <dd>{parameters.sort ?? "—"}</dd>
        <dt>requested</dt>
        <dd>{String(p.requested_count ?? "—")}</dd>
        <dt>returned</dt>
        <dd>{String(p.returned_count ?? "—")}</dd>
        <dt>total matches</dt>
        <dd>{String(p.total_matches ?? "—")}</dd>
        {p.reason && (
          <>
            <dt>reason</dt>
            <dd>{p.reason}</dd>
          </>
        )}
      </dl>
      {queryText && <p className="snippet">{String(queryText)}</p>}
      {translatedQuery && (
        <details className="details-block">
          <summary>PubMed translation</summary>
          <pre className="code-block">{translatedQuery}</pre>
        </details>
      )}
      {pmids.length > 0 && <DetailList title="PMIDS" items={pmids.slice(0, 20)} />}
      {pmcids.length > 0 && <DetailList title="PMCIDS" items={pmcids.slice(0, 20)} />}
      {outputIds.length > 0 && <DetailList title="OUTPUT EVIDENCE IDS" items={outputIds.slice(0, 20)} />}
      {articles.length > 0 && (
        <details className="details-block">
          <summary>Returned articles ({articles.length})</summary>
          <pre className="code-block">{JSON.stringify(articles, null, 2)}</pre>
        </details>
      )}
    </>
  );
}

function ProblemRepresentation({ p }: { p: Record<string, any> }) {
  const keyFindings = arrayOfStrings(p.key_findings ?? p.key_features);
  const summary = p.text ?? p.summary ?? p.one_liner ?? p.problem_representation;
  return (
    <>
      <dl className="kv">
        {p.case_id && (
          <>
            <dt>case id</dt>
            <dd>{p.case_id}</dd>
          </>
        )}
        {p.age && (
          <>
            <dt>age</dt>
            <dd>{p.age}</dd>
          </>
        )}
        {p.sex && (
          <>
            <dt>sex</dt>
            <dd>{p.sex}</dd>
          </>
        )}
        {p.tempo && (
          <>
            <dt>tempo</dt>
            <dd>{p.tempo}</dd>
          </>
        )}
        {p.localization && (
          <>
            <dt>localization</dt>
            <dd>{p.localization}</dd>
          </>
        )}
      </dl>
      {summary && <p className="snippet">{String(summary)}</p>}
      {keyFindings.length > 0 && <DetailList title="KEY FINDINGS" items={keyFindings.slice(0, 12)} />}
    </>
  );
}

function ModelCall({ p }: { p: Record<string, any> }) {
  const usage = p.usage ?? {};
  return (
    <>
      <dl className="kv">
        <dt>stage</dt>
        <dd>{p.stage ?? "—"}</dd>
        <dt>model</dt>
        <dd>{p.model ?? "—"}</dd>
        <dt>latency</dt>
        <dd>{p.latency_ms != null ? `${p.latency_ms} ms` : "—"}</dd>
        <dt>prompt tokens</dt>
        <dd>{usage.prompt_tokens ?? "—"}</dd>
        <dt>completion tokens</dt>
        <dd>{usage.completion_tokens ?? "—"}</dd>
        <dt>total tokens</dt>
        <dd>{usage.total_tokens ?? "—"}</dd>
        <UsageDetails usage={usage} />
        <dt>max tokens</dt>
        <dd>{p.max_tokens ?? "—"}</dd>
        <dt>temperature</dt>
        <dd>{p.temperature ?? "—"}</dd>
        {p.attempt && (
          <>
            <dt>attempt</dt>
            <dd>
              {p.attempt}
              {p.max_attempts ? ` / ${p.max_attempts}` : ""}
            </dd>
          </>
        )}
        {p.retry_will_continue && (
          <>
            <dt>retry status</dt>
            <dd>retrying automatically</dd>
          </>
        )}
        {p.recovered_from_error && (
          <>
            <dt>retry status</dt>
            <dd>fixed after retry</dd>
          </>
        )}
        {p.evidence_id && (
          <>
            <dt>evidence id</dt>
            <dd>{p.evidence_id}</dd>
          </>
        )}
        {p.pmid && (
          <>
            <dt>pmid</dt>
            <dd>{p.pmid}</dd>
          </>
        )}
        {p.expected_diagnosis && (
          <>
            <dt>expected</dt>
            <dd>{p.expected_diagnosis}</dd>
          </>
        )}
        {p.candidate_diagnosis && (
          <>
            <dt>candidate</dt>
            <dd>{p.candidate_diagnosis}</dd>
          </>
        )}
        {p.error && (
          <>
            <dt>error</dt>
            <dd>{p.error}</dd>
          </>
      )}
      </dl>
      {p.paper_title && <p className="snippet">{p.paper_title}</p>}
      {isRecord(p.parsed_json) && <PrettyPayload p={p.parsed_json} />}
      {p.prompt && (
        <details className="details-block">
          <summary>Prompt</summary>
          <pre className="code-block">{String(p.prompt)}</pre>
        </details>
      )}
      {p.parsed_json && (
        <details className="details-block" open>
          <summary>Parsed JSON</summary>
          <pre className="code-block">{JSON.stringify(p.parsed_json, null, 2)}</pre>
        </details>
      )}
      {p.response_text && (
        <details className="details-block" open>
          <summary>Model response text</summary>
          <pre className="code-block">{String(p.response_text)}</pre>
        </details>
      )}
      {p.raw && (
        <details className="details-block">
          <summary>Raw API response</summary>
          <pre className="code-block">{JSON.stringify(p.raw, null, 2)}</pre>
        </details>
      )}
    </>
  );
}

function PromptBuilt({ p }: { p: Record<string, any> }) {
  const gates: string[] = p.finalization_gates ?? [];
  const entities: any[] = p.specific_entities_to_consider ?? [];
  const screened: any[] = p.screened_relevant_evidence ?? [];
  const evidence: any[] = p.retrieved_evidence ?? [];
  const synthesis: any[] = p.evidence_synthesis ?? [];
  const blockedShortcuts = p.blocked_shortcuts;
  return (
    <>
      <dl className="kv">
        <dt>preset</dt>
        <dd>{p.harness_preset ?? "—"}</dd>
        <dt>prompt size</dt>
        <dd>{p.prompt_chars ? `${p.prompt_chars} chars` : "—"}</dd>
        <dt>rounds</dt>
        <dd>
          {p.retrieval_rounds_completed ?? "—"} / {p.retrieval_rounds_allowed ?? "—"}
        </dd>
        <dt>evidence injected</dt>
        <dd>{String(p.retrieved_evidence_count ?? evidence.length ?? "—")}</dd>
        <dt>synthesis packets</dt>
        <dd>{String(p.synthesis_count ?? synthesis.length ?? 0)}</dd>
        <dt>screened notes</dt>
        <dd>{String(p.screened_relevant_evidence_count ?? screened.length ?? 0)}</dd>
        <dt>knowledge cards</dt>
        <dd>{String(p.specific_entities_count ?? entities.length ?? 0)}</dd>
      </dl>

      {isRecord(blockedShortcuts) && (
        <>
          <SectionLabel>BLOCKED RETRIEVAL SHORTCUTS</SectionLabel>
          <dl className="kv">
            {Object.entries(blockedShortcuts).map(([key, value]) => (
              <FragmentPair key={key} label={key} value={String(value)} />
            ))}
          </dl>
        </>
      )}

      {gates.length > 0 && (
        <DetailList title="FINALIZATION GATES" items={gates.slice(0, 12)} />
      )}

      {entities.length > 0 && (
        <>
          <SectionLabel>SPECIFIC ENTITIES TO CONSIDER</SectionLabel>
          {entities.slice(0, 8).map((entity, i) => (
            <div className="disc" key={i}>
              <div className="d-name">{entity.entity ?? entity.name ?? `entity ${i + 1}`}</div>
              {entity.discriminator && <div className="d-dir">{entity.discriminator}</div>}
              {entity.confirmatory_test && <div className="d-dir">{entity.confirmatory_test}</div>}
            </div>
          ))}
        </>
      )}

      {screened.length > 0 && (
        <>
          <SectionLabel>SCREENED RELEVANT EVIDENCE</SectionLabel>
          {screened.slice(0, 6).map((item, i) => (
            <div className="disc" key={i} style={{ borderColor: "var(--retriever)" }}>
              <div className="d-name">{item.title ?? item.evidence_id}</div>
              {item.relevant_excerpt && <div className="d-dir">{item.relevant_excerpt}</div>}
            </div>
          ))}
        </>
      )}

      {synthesis.length > 0 && (
        <>
          <SectionLabel>EVIDENCE SYNTHESIS</SectionLabel>
          {synthesis.slice(0, 5).map((item, i) => (
            <SynthesisPacket key={i} item={item} />
          ))}
        </>
      )}

      {synthesis.length > 0 && (
        <details className="details-block">
          <summary>Evidence synthesis packet ({synthesis.length})</summary>
          <pre className="code-block">{JSON.stringify(synthesis, null, 2)}</pre>
        </details>
      )}

      {evidence.length > 0 && (
        <details className="details-block">
          <summary>Retrieved evidence packet ({evidence.length})</summary>
          <pre className="code-block">{JSON.stringify(evidence, null, 2)}</pre>
        </details>
      )}

      {p.prompt && (
        <details className="details-block">
          <summary>Raw final prompt</summary>
          <pre className="code-block">{String(p.prompt)}</pre>
        </details>
      )}
    </>
  );
}

function ModelResponse({ p }: { p: Record<string, any> }) {
  const usage = p.usage ?? {};
  return (
    <>
      <dl className="kv">
        <dt>model</dt>
        <dd>{p.model ?? "—"}</dd>
        <dt>latency</dt>
        <dd>{p.latency_ms != null ? `${p.latency_ms} ms` : "—"}</dd>
        <dt>prompt tokens</dt>
        <dd>{usage.prompt_tokens ?? "—"}</dd>
        <dt>completion tokens</dt>
        <dd>{usage.completion_tokens ?? "—"}</dd>
        <dt>total tokens</dt>
        <dd>{usage.total_tokens ?? "—"}</dd>
        <UsageDetails usage={usage} />
        {p.error && (
          <>
            <dt>error</dt>
            <dd>{p.error}</dd>
          </>
        )}
      </dl>
      {p.self_consistency && (
        <details className="details-block">
          <summary>Self-consistency</summary>
          <pre className="code-block">{JSON.stringify(p.self_consistency, null, 2)}</pre>
        </details>
      )}
      {isRecord(p.content) && <PrettyPayload p={p.content} />}
      {p.content && (
        <details className="details-block" open>
          <summary>Parsed content</summary>
          <pre className="code-block">{JSON.stringify(p.content, null, 2)}</pre>
        </details>
      )}
      {p.raw_content && (
        <details className="details-block" open>
          <summary>Visible model response</summary>
          <pre className="code-block">{String(p.raw_content)}</pre>
        </details>
      )}
      {p.raw && (
        <details className="details-block">
          <summary>Raw API response</summary>
          <pre className="code-block">{JSON.stringify(p.raw, null, 2)}</pre>
        </details>
      )}
    </>
  );
}

function Synthesis({ p }: { p: Record<string, any> }) {
  const discs: any[] = p.useful_discriminators ?? [];
  return (
    <>
      <dl className="kv">
        <dt>resolved</dt>
        <dd>{String(p.differential_resolved)}</dd>
        <dt>more retrieval</dt>
        <dd>{String(p.more_retrieval_needed)}</dd>
        {Array.isArray(p.top_mimic_pair) && p.top_mimic_pair.length > 0 && (
          <>
            <dt>top mimic pair</dt>
            <dd>{p.top_mimic_pair.join(" vs ")}</dd>
          </>
        )}
      </dl>
      {discs.slice(0, 8).map((d, i) => (
        <div className="disc" key={i}>
          <div className="d-name">{d.discriminator}</div>
          {d.direction && <div className="d-dir">{d.direction}</div>}
          {d.supports_or_refutes && <div className="d-dir">{d.supports_or_refutes}</div>}
        </div>
      ))}
      {Array.isArray(p.notes) &&
        p.notes.map((n: string, i: number) => (
          <p className="snippet" key={`n${i}`}>
            • {n}
          </p>
        ))}
      <PrettyPayload p={p} skipKeys={new Set(["useful_discriminators", "notes"])} />
    </>
  );
}

function PrettyPayload({
  p,
  skipKeys = new Set(),
}: {
  p: Record<string, any>;
  skipKeys?: Set<string>;
}) {
  const usefulDiscriminators = arrayOfRecords(p.useful_discriminators);
  const rankedDifferential = arrayOfRecords(p.ranked_differential);
  const differential = rankedDifferential.length > 0 ? rankedDifferential : arrayOfRecords(p.differential);
  const citations = arrayOfRecords(p.citations);
  const keyPapers = arrayOfRecords(p.key_papers);
  const uncertainty = arrayOfStrings(p.remaining_uncertainty);
  const followups = arrayOfStrings(p.additional_queries);
  const fullText = arrayOfStrings(p.need_full_text_evidence_ids);
  const anchorRisks = arrayOfStrings(p.anchor_risks);
  const notes = skipKeys.has("notes") ? [] : arrayOfStrings(p.notes);
  const tests = arrayOfStrings(p.recommended_next_tests);
  const summaryRows = [
    ["resolved", p.differential_resolved],
    ["more retrieval", p.more_retrieval_needed],
    ["confidence", p.confidence],
    ["final diagnosis", p.final_diagnosis ?? p.diagnosis],
    ["next step", p.recommended_next_step],
    ["new entity", p.new_entity],
    ["relevant", p.relevant],
  ].filter(([, value]) => value !== undefined && value !== null && value !== "");
  const showDiscriminators = !skipKeys.has("useful_discriminators") && usefulDiscriminators.length > 0;
  const hasReadable =
    summaryRows.length > 0 ||
    showDiscriminators ||
    differential.length > 0 ||
    citations.length > 0 ||
    keyPapers.length > 0 ||
    uncertainty.length > 0 ||
    followups.length > 0 ||
    fullText.length > 0 ||
    anchorRisks.length > 0 ||
    notes.length > 0 ||
    tests.length > 0 ||
    typeof p.relevant_excerpt === "string";

  if (!hasReadable) return null;

  return (
    <>
      <SectionLabel>READABLE SUMMARY</SectionLabel>
      {summaryRows.length > 0 && (
        <dl className="kv">
          {summaryRows.map(([label, value]) => (
            <FragmentPair key={String(label)} label={String(label)} value={String(value)} />
          ))}
        </dl>
      )}
      {typeof p.relevant_excerpt === "string" && <p className="snippet">{p.relevant_excerpt}</p>}
      {differential.length > 0 && <PrettyDifferential items={differential} />}
      {showDiscriminators && <PrettyDiscriminators items={usefulDiscriminators} />}
      {uncertainty.length > 0 && <DetailList title="REMAINING UNCERTAINTY" items={uncertainty.slice(0, 8)} />}
      {followups.length > 0 && <DetailList title="FOLLOW-UP SEARCHES" items={followups.slice(0, 8)} />}
      {fullText.length > 0 && <DetailList title="FULL TEXT NEEDED" items={fullText.slice(0, 8)} />}
      {anchorRisks.length > 0 && <DetailList title="ANCHORING RISKS" items={anchorRisks.slice(0, 8)} />}
      {tests.length > 0 && <DetailList title="RECOMMENDED NEXT TESTS" items={tests.slice(0, 8)} />}
      {notes.length > 0 && <DetailList title="NOTES" items={notes.slice(0, 8)} />}
      {keyPapers.length > 0 && <PrettyPapers title="KEY PAPERS" items={keyPapers.slice(0, 8)} />}
      {citations.length > 0 && <PrettyPapers title="CITATIONS" items={citations.slice(0, 8)} />}
    </>
  );
}

function SynthesisPacket({ item }: { item: any }) {
  if (!isRecord(item)) {
    return <p className="snippet">{String(item)}</p>;
  }
  return (
    <div className="disc">
      <div className="d-name">Round {String(item.synthesis_round ?? "?")}</div>
      <div className="d-dir">
        resolved: {String(item.differential_resolved)} · more retrieval: {String(item.more_retrieval_needed)}
      </div>
      <PrettyPayload p={item} skipKeys={new Set(["notes"])} />
    </div>
  );
}

function PrettyDifferential({ items }: { items: Record<string, any>[] }) {
  return (
    <>
      <SectionLabel>DIFFERENTIAL</SectionLabel>
      {items.slice(0, 8).map((item, i) => (
        <div className="disc" key={i}>
          <div className="d-name">
            {item.rank ?? i + 1}. {item.diagnosis ?? item.name ?? item.entity ?? `candidate ${i + 1}`}
          </div>
          {item.confidence && <div className="d-dir">confidence: {item.confidence}</div>}
          {Array.isArray(item.supporting_features) && item.supporting_features.length > 0 && (
            <div className="d-dir">supports: {item.supporting_features.slice(0, 3).join("; ")}</div>
          )}
          {Array.isArray(item.refuting_features) && item.refuting_features.length > 0 && (
            <div className="d-dir">refutes: {item.refuting_features.slice(0, 3).join("; ")}</div>
          )}
        </div>
      ))}
    </>
  );
}

function PrettyDiscriminators({ items }: { items: Record<string, any>[] }) {
  return (
    <>
      <SectionLabel>DISCRIMINATORS</SectionLabel>
      {items.slice(0, 8).map((item, i) => (
        <div className="disc" key={i}>
          <div className="d-name">
            {item.discriminator ?? item.entity ?? item.evidence_id ?? `discriminator ${i + 1}`}
          </div>
          {item.required_test_or_marker && <div className="d-dir">test: {item.required_test_or_marker}</div>}
          {Array.isArray(item.supports) && item.supports.length > 0 && (
            <div className="d-dir">supports: {item.supports.slice(0, 3).join("; ")}</div>
          )}
          {Array.isArray(item.refutes) && item.refutes.length > 0 && (
            <div className="d-dir">refutes: {item.refutes.slice(0, 3).join("; ")}</div>
          )}
          {item.supports_or_refutes && <div className="d-dir">{item.supports_or_refutes}</div>}
          {item.direction && <div className="d-dir">{item.direction}</div>}
        </div>
      ))}
    </>
  );
}

function PrettyPapers({ title, items }: { title: string; items: Record<string, any>[] }) {
  return (
    <>
      <SectionLabel>{title}</SectionLabel>
      {items.map((item, i) => (
        <div className="disc" key={i} style={{ borderColor: "var(--diagnostician)" }}>
          <div className="d-name">{item.title ?? item.evidence_id ?? item.pmid ?? `paper ${i + 1}`}</div>
          {item.contribution && <div className="d-dir">{item.contribution}</div>}
          {item.pmid && <div className="d-dir">PMID {item.pmid}</div>}
        </div>
      ))}
    </>
  );
}

function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <p className="snippet" style={{ color: "var(--text-faint)", marginTop: 12 }}>
      {children}
    </p>
  );
}

function DetailList({ title, items }: { title: string; items: string[] }) {
  return (
    <>
      <SectionLabel>{title}</SectionLabel>
      {items.map((item, i) => (
        <p className="snippet" key={i}>
          • {item}
        </p>
      ))}
    </>
  );
}

function FragmentPair({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </>
  );
}

function UsageDetails({ usage }: { usage: Record<string, any> }) {
  const promptDetails = usage.prompt_tokens_details ?? {};
  const completionDetails = usage.completion_tokens_details ?? {};
  return (
    <>
      {usage.prompt_cache_hit_tokens != null && (
        <FragmentPair label="cache hit tokens" value={String(usage.prompt_cache_hit_tokens)} />
      )}
      {usage.prompt_cache_miss_tokens != null && (
        <FragmentPair label="cache miss tokens" value={String(usage.prompt_cache_miss_tokens)} />
      )}
      {promptDetails.cached_tokens != null && (
        <FragmentPair label="cached prompt tokens" value={String(promptDetails.cached_tokens)} />
      )}
      {completionDetails.reasoning_tokens != null && (
        <FragmentPair label="reasoning tokens" value={String(completionDetails.reasoning_tokens)} />
      )}
    </>
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function Answer({ p }: { p: Record<string, any> }) {
  const answer = isRecord(p.answer) ? p.answer : {};
  const papers: any[] = Array.isArray(p.key_papers) ? p.key_papers : [];
  const discs: any[] = Array.isArray(p.discriminator_summary) ? p.discriminator_summary : [];
  const rankedDifferential: any[] = Array.isArray(p.ranked_differential)
    ? p.ranked_differential
    : Array.isArray(answer.ranked_differential)
      ? answer.ranked_differential
      : [];
  const differential: any[] = rankedDifferential.length > 0
    ? rankedDifferential
    : Array.isArray(p.differential)
      ? p.differential
      : Array.isArray(answer.differential)
        ? answer.differential
        : [];
  const citations: any[] = Array.isArray(p.citations)
    ? p.citations
    : Array.isArray(answer.citations)
      ? answer.citations
      : [];
  const nextTests = arrayOfStrings(answer.recommended_next_tests ?? p.recommended_next_tests);
  const aliases = arrayOfStrings(answer.aliases ?? p.aliases);
  const finalDiagnosis = p.final_diagnosis ?? answer.final_diagnosis ?? p.diagnosis ?? "—";
  return (
    <>
      <dl className="kv">
        <dt>final diagnosis</dt>
        <dd>{String(finalDiagnosis)}</dd>
        {(p.etiology || answer.localization) && (
          <>
            <dt>{p.etiology ? "etiology" : "localization"}</dt>
            <dd>{p.etiology ?? answer.localization}</dd>
          </>
        )}
        <dt>confidence</dt>
        <dd>{p.confidence ?? answer.confidence ?? "—"}</dd>
        {(p.recommended_next_step || answer.recommended_next_step) && (
          <>
            <dt>next step</dt>
            <dd>{p.recommended_next_step ?? answer.recommended_next_step}</dd>
          </>
        )}
        {p.answer_path && (
          <>
            <dt>answer path</dt>
            <dd>{p.answer_path}</dd>
          </>
        )}
      </dl>
      {aliases.length > 0 && <DetailList title="ALIASES" items={aliases.slice(0, 10)} />}
      {nextTests.length > 0 && <DetailList title="RECOMMENDED NEXT TESTS" items={nextTests.slice(0, 10)} />}
      {differential.length > 0 && (
        <>
          <p className="snippet" style={{ color: "var(--text-faint)", marginTop: 12 }}>
            {rankedDifferential.length > 0 ? "RANKED DIFFERENTIAL (TOP 5)" : "DIFFERENTIAL"}
          </p>
          {differential.slice(0, rankedDifferential.length > 0 ? 5 : 8).map((candidate, i) => (
            <div className="disc" key={i}>
              <div className="d-name">
                {candidate.rank ?? i + 1}. {candidate.diagnosis ?? candidate.name ?? `candidate ${i + 1}`}
              </div>
              {candidate.confidence && <div className="d-dir">confidence: {candidate.confidence}</div>}
              {Array.isArray(candidate.supporting_features) && candidate.supporting_features.length > 0 && (
                <div className="d-dir">supports: {candidate.supporting_features.slice(0, 3).join("; ")}</div>
              )}
              {Array.isArray(candidate.refuting_features) && candidate.refuting_features.length > 0 && (
                <div className="d-dir">refutes: {candidate.refuting_features.slice(0, 3).join("; ")}</div>
              )}
              {Array.isArray(candidate.supporting_evidence) && candidate.supporting_evidence.length > 0 && (
                <div className="d-dir">supports: {candidate.supporting_evidence.slice(0, 3).join("; ")}</div>
              )}
              {Array.isArray(candidate.refuting_evidence) && candidate.refuting_evidence.length > 0 && (
                <div className="d-dir">refutes: {candidate.refuting_evidence.slice(0, 3).join("; ")}</div>
              )}
            </div>
          ))}
        </>
      )}
      {citations.length > 0 && (
        <details className="details-block">
          <summary>Citations ({citations.length})</summary>
          <pre className="code-block">{JSON.stringify(citations, null, 2)}</pre>
        </details>
      )}
      {discs.length > 0 && (
        <>
          <p className="snippet" style={{ color: "var(--text-faint)", marginTop: 12 }}>
            DISCRIMINATORS USED
          </p>
          {discs.map((d, i) => (
            <div className="disc" key={i}>
              <div className="d-name">{d.discriminator ?? d.case_finding}</div>
              {d.direction && <div className="d-dir">{d.direction}</div>}
            </div>
          ))}
        </>
      )}
      {papers.length > 0 && (
        <>
          <p className="snippet" style={{ color: "var(--text-faint)", marginTop: 12 }}>
            KEY PAPERS
          </p>
          {papers.map((paper, i) => (
            <div className="disc" key={i} style={{ borderColor: "var(--diagnostician)" }}>
              <div className="d-name">
                {paper.pmid ? (
                  <a
                    href={`https://pubmed.ncbi.nlm.nih.gov/${paper.pmid}/`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {paper.title}
                  </a>
                ) : (
                  paper.title
                )}
              </div>
              {paper.contribution && <div className="d-dir">{paper.contribution}</div>}
            </div>
          ))}
        </>
      )}
      {Object.keys(answer).length > 0 && (
        <details className="details-block">
          <summary>Structured answer JSON</summary>
          <pre className="code-block">{JSON.stringify(answer, null, 2)}</pre>
        </details>
      )}
    </>
  );
}

function firstString(value: unknown): string | null {
  if (Array.isArray(value) && typeof value[0] === "string") return value[0];
  return null;
}

function arrayOfStrings(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string");
}

function arrayOfRecords(value: unknown): Record<string, any>[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is Record<string, any> => isRecord(item));
}
