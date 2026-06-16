import { useEffect, useMemo, useRef, useState } from "react";
import { api, streamTimeline } from "./api";
import { EventCard } from "./components/EventCard";
import { Badge } from "./components/ui";
import type { ArtifactContent, CaseArtifact, CaseSummary, CaseTimeline, RunSummary, Status, TraceEvent } from "./types";

type TraceFilter = "all" | "model" | "retrieval" | "reasoning" | "judgement" | "errors";

export default function App() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [activeRun, setActiveRun] = useState<string | null>(null);
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [caseFilter, setCaseFilter] = useState("");
  const [activeCase, setActiveCase] = useState<string | null>(null);

  const [timeline, setTimeline] = useState<CaseTimeline | null>(null);
  const [shown, setShown] = useState<TraceEvent[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [traceFilter, setTraceFilter] = useState<TraceFilter>("all");
  const [traceSearch, setTraceSearch] = useState("");
  const [runsPanelOpen, setRunsPanelOpen] = useState(true);
  const [casesPanelOpen, setCasesPanelOpen] = useState(true);
  const [artifactView, setArtifactView] = useState<{
    artifact: CaseArtifact;
    content: ArtifactContent | null;
    loading: boolean;
    error: string | null;
  } | null>(null);
  const streamCleanupRef = useRef<(() => void) | null>(null);

  function refreshRuns() {
    api.runs().then(setRuns).catch(console.error);
  }

  function refreshCases(runId = activeRun) {
    if (!runId) return;
    api.cases(runId).then(setCases).catch(console.error);
  }

  useEffect(() => {
    refreshRuns();
  }, []);

  useEffect(() => () => stopStream(), []);

  useEffect(() => {
    if (!activeRun) return;
    stopStream();
    setCases([]);
    setActiveCase(null);
    setTimeline(null);
    setShown([]);
    setArtifactView(null);
    refreshCases(activeRun);
  }, [activeRun]);

  useEffect(() => {
    if (!activeRun) return;
    const needsRefresh = cases.some((c) => c.is_live || c.is_complete === false);
    if (!needsRefresh) return;
    const id = window.setInterval(() => {
      refreshRuns();
      refreshCases(activeRun);
    }, 2500);
    return () => window.clearInterval(id);
  }, [activeRun, cases]);

  useEffect(() => {
    if (!activeRun || !activeCase) return;
    stopStream();
    setTimeline(null);
    setShown([]);
    setTraceFilter("all");
    setTraceSearch("");
    setArtifactView(null);
    api
      .timeline(activeRun, activeCase)
      .then((tl) => {
        setTimeline(tl);
        setShown(tl.events); // show full timeline immediately; "Replay" animates it
      })
      .catch(console.error);
  }, [activeRun, activeCase]);

  const activeCaseSummary = useMemo(
    () => cases.find((c) => c.case_id === activeCase) ?? null,
    [cases, activeCase],
  );

  useEffect(() => {
    if (!activeRun || !activeCase || !activeCaseSummary?.is_live) return;
    return startStream({ delayMs: 0, reset: false });
  }, [activeRun, activeCase, activeCaseSummary?.is_live]);

  const filteredCases = useMemo(
    () =>
      cases.filter((c) => c.case_id.toLowerCase().includes(caseFilter.toLowerCase())),
    [cases, caseFilter],
  );

  const visibleEvents = useMemo(
    () =>
      shown.filter((event) => {
        if (!matchesTraceFilter(event, traceFilter)) return false;
        const query = traceSearch.trim().toLowerCase();
        if (!query) return true;
        return eventSearchText(event).includes(query);
      }),
    [shown, traceFilter, traceSearch],
  );

  const eventCounts = useMemo(() => traceFilterCounts(shown), [shown]);
  const traceSummary = useMemo(() => summarizeTrace(shown), [shown]);

  function stopStream() {
    streamCleanupRef.current?.();
    streamCleanupRef.current = null;
    setStreaming(false);
  }

  function startStream({ delayMs, reset }: { delayMs: number; reset: boolean }) {
    if (!activeRun || !activeCase) return;
    stopStream();
    if (reset) setShown([]);
    setStreaming(true);
    const cleanup = streamTimeline(activeRun, activeCase, {
      delayMs,
      onEvent: (e) => setShown((prev) => mergeEvent(prev, e)),
      onDone: () => setStreaming(false),
    });
    streamCleanupRef.current = cleanup;
    return cleanup;
  }

  function replay() {
    startStream({ delayMs: activeCaseSummary?.is_live ? 0 : 300, reset: true });
  }

  function openArtifact(artifact: CaseArtifact) {
    if (!timeline) return;
    setArtifactView({ artifact, content: null, loading: true, error: null });
    api
      .artifact(timeline.run_id, timeline.case_id, artifact.name)
      .then((content) => setArtifactView({ artifact, content, loading: false, error: null }))
      .catch((err) =>
        setArtifactView({
          artifact,
          content: null,
          loading: false,
          error: err instanceof Error ? err.message : String(err),
        }),
      );
  }

  return (
    <div
      className={[
        "app",
        !runsPanelOpen ? "runs-collapsed" : "",
        !casesPanelOpen ? "cases-collapsed" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {/* Rail: runs */}
      <div className="rail" aria-hidden={!runsPanelOpen}>
        <div className="rail-head">
          <div className="eyebrow">ClinicalHarness</div>
          <div className="title-row">
            <div className="title">Runs</div>
            <div className="header-actions">
              <button className="icon-btn" onClick={refreshRuns} title="Refresh runs">
                ↻
              </button>
              <button
                className="panel-action"
                onClick={() => setRunsPanelOpen(false)}
                title="Hide runs panel"
              >
                Hide
              </button>
            </div>
          </div>
        </div>
        {runs.map((r) => (
          <button
            key={r.run_id}
            className={`row ${activeRun === r.run_id ? "active" : ""}`}
            onClick={() => setActiveRun(r.run_id)}
          >
            <div className="row-title">{r.run_id}</div>
            <div className="row-meta">
              <span>{r.case_count} cases</span>
              {r.live_case_count > 0 && <Badge status="running" label={`${r.live_case_count} live`} />}
              {r.incomplete_case_count > 0 && (
                <Badge status="info" label={`${r.incomplete_case_count} growing`} />
              )}
              {r.native_event_case_count > 0 && (
                <span>{r.native_event_case_count} traces</span>
              )}
              {r.pass_count != null && (
                <>
                  <span style={{ color: "var(--pass)" }}>{r.pass_count}✓</span>
                  <span style={{ color: "var(--fail)" }}>{r.fail_count}✗</span>
                </>
              )}
            </div>
          </button>
        ))}
      </div>

      {/* Column: cases */}
      <div className="column" aria-hidden={!casesPanelOpen}>
        <div className="column-head">
          <div className="eyebrow">{activeRun ?? "select a run"}</div>
          <div className="title-row">
            <div className="title">Cases</div>
            <div className="header-actions">
              {activeRun && (
                <button className="icon-btn" onClick={() => refreshCases()} title="Refresh cases">
                  ↻
                </button>
              )}
              <button
                className="panel-action"
                onClick={() => setCasesPanelOpen(false)}
                title="Hide cases panel"
              >
                Hide
              </button>
            </div>
          </div>
          {cases.length > 0 && (
            <input
              className="search"
              placeholder="filter cases…"
              value={caseFilter}
              onChange={(e) => setCaseFilter(e.target.value)}
            />
          )}
        </div>
        {filteredCases.map((c) => (
          <button
            key={c.case_id}
            className={`row ${activeCase === c.case_id ? "active" : ""}`}
            onClick={() => setActiveCase(c.case_id)}
          >
            <div className="row-title">{c.case_id}</div>
            <div className="row-meta">
              {c.is_live && <Badge status="running" label="live" />}
              {!c.is_live && c.is_complete === false && <Badge status="info" label="growing" />}
              {c.has_native_events && <Badge status="ok" label={`${c.event_count ?? "?"} events`} />}
              {c.score && <Badge status={c.score === "pass" ? "pass" : "fail"} />}
              {c.expected_diagnosis && <span>{truncate(c.expected_diagnosis, 48)}</span>}
            </div>
          </button>
        ))}
        {activeRun && cases.length === 0 && <div className="empty">no cases found</div>}
      </div>

      {/* Main: timeline */}
      <div className="main">
        <div className="main-head">
          <div className="main-title-row">
            <div>
              <div className="eyebrow">trace</div>
              <div className="title">{activeCase ?? "—"}</div>
            </div>
            <div className="panel-controls" aria-label="Panel visibility">
              {!runsPanelOpen && (
                <button
                  className="panel-toggle"
                  onClick={() => setRunsPanelOpen(true)}
                  title="Show runs panel"
                >
                  Show Runs
                </button>
              )}
              {!casesPanelOpen && (
                <button
                  className="panel-toggle"
                  onClick={() => setCasesPanelOpen(true)}
                  title="Show cases panel"
                >
                  Show Cases
                </button>
              )}
            </div>
          </div>
          {timeline && (
            <div className="controls">
              <button
                className="btn"
                onClick={() => activeRun && activeCase && api.timeline(activeRun, activeCase).then((tl) => {
                  setTimeline(tl);
                  setShown(tl.events);
                }).catch(console.error)}
                disabled={streaming}
              >
                Refresh
              </button>
              <button className="btn primary" onClick={replay} disabled={streaming}>
                {streaming
                  ? activeCaseSummary?.is_live
                    ? "● watching…"
                    : "▶ replaying…"
                  : activeCaseSummary?.is_live
                    ? "● Watch live"
                    : "▶ Replay"}
              </button>
              <button
                className="btn"
                onClick={() => setShown(timeline.events)}
                disabled={streaming}
              >
                Show all
              </button>
              {timeline.score && (
                <Badge status={timeline.score === "pass" ? "pass" : "fail"} />
              )}
            </div>
          )}
        </div>

        {!activeCase && <div className="empty">Select a run, then a case to watch the harness work.</div>}

        {timeline && (
          <div className="timeline">
            <div className="tl-header">
              <div className="trace-source">
                <Badge status={traceSourceStatus(timeline.trace_source)} label={traceSourceLabel(timeline.trace_source)} />
                {activeCaseSummary?.is_complete === false && <Badge status="info" label="growing" />}
                {timeline.trace_notice && <span>{timeline.trace_notice}</span>}
              </div>
              {timeline.artifacts.length > 0 && (
                <div className="artifact-links">
                  {timeline.artifacts.map((artifact) => (
                    <button
                      key={artifact.name}
                      type="button"
                      onClick={() => openArtifact(artifact)}
                      title={artifact.filename}
                    >
                      {artifact.label}
                    </button>
                  ))}
                </div>
              )}
              {timeline.expected_diagnosis && (
                <div className="dx-row">
                  <span className="dx-label">expected</span>
                  <span className="dx">{timeline.expected_diagnosis}</span>
                </div>
              )}
              {timeline.model_diagnosis && (
                <div className="dx-row">
                  <span className="dx-label">model</span>
                  <span className="dx">{timeline.model_diagnosis}</span>
                </div>
              )}
              <div className="trace-summary">
                <Metric label="events" value={traceSummary.events} />
                <Metric label="model calls" value={traceSummary.modelCalls} />
                <Metric label="responses" value={traceSummary.modelResponses} />
                <Metric label="tool calls" value={traceSummary.toolCalls} />
                <Metric label="tokens" value={formatNumber(traceSummary.totalTokens)} />
                <Metric label="prompt" value={formatNumber(traceSummary.promptTokens)} />
                <Metric label="completion" value={formatNumber(traceSummary.completionTokens)} />
                <Metric label="reasoning" value={formatNumber(traceSummary.reasoningTokens)} />
                <Metric label="evidence" value={traceSummary.evidence} />
                <Metric label="warnings" value={traceSummary.warnings} />
                <Metric label="errors" value={traceSummary.errors} />
                {traceSummary.lastEvent && <Metric label="latest" value={traceSummary.lastEvent} />}
              </div>
              <div className="trace-tools">
                <div className="filter-pills">
                  {TRACE_FILTERS.map((filter) => (
                    <button
                      key={filter.id}
                      className={`pill ${traceFilter === filter.id ? "active" : ""}`}
                      onClick={() => setTraceFilter(filter.id)}
                    >
                      {filter.label}
                      <span>{eventCounts[filter.id]}</span>
                    </button>
                  ))}
                </div>
                <input
                  className="trace-search"
                  placeholder="search trace…"
                  value={traceSearch}
                  onChange={(e) => setTraceSearch(e.target.value)}
                />
              </div>
              {visibleEvents.length !== shown.length && (
                <div className="trace-count">
                  showing {visibleEvents.length} of {shown.length} events
                </div>
              )}
            </div>
            {visibleEvents.map((e) => (
              <EventCard key={e.id} event={e} />
            ))}
            {shown.length > 0 && visibleEvents.length === 0 && (
              <div className="empty">no events match this trace filter</div>
            )}
          </div>
        )}
      </div>
      {artifactView && timeline && (
        <ArtifactPanel
          runId={timeline.run_id}
          caseId={timeline.case_id}
          artifact={artifactView.artifact}
          content={artifactView.content}
          loading={artifactView.loading}
          error={artifactView.error}
          onClose={() => setArtifactView(null)}
        />
      )}
    </div>
  );
}

const TRACE_FILTERS: { id: TraceFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "model", label: "Models" },
  { id: "retrieval", label: "Retrieval" },
  { id: "reasoning", label: "Reasoning" },
  { id: "judgement", label: "Judge" },
  { id: "errors", label: "Errors" },
];

function matchesTraceFilter(event: TraceEvent, filter: TraceFilter): boolean {
  switch (filter) {
    case "all":
      return true;
    case "model":
      return event.type === "model_call" || event.type === "model_response" || event.type === "prompt_built";
    case "retrieval":
      return (
        event.actor === "retriever" ||
        event.type === "query_generated" ||
        event.type === "tool_call" ||
        event.type === "evidence_retrieved"
      );
    case "reasoning":
      return (
        event.type === "problem_representation" ||
        event.type === "synthesis" ||
        event.type === "answer" ||
        event.actor === "synthesizer" ||
        event.actor === "diagnostician"
      );
    case "judgement":
      return event.actor === "judge" || event.type === "judge";
    case "errors":
      return event.status === "error" || event.status === "warn";
  }
}

function traceFilterCounts(events: TraceEvent[]): Record<TraceFilter, number> {
  return TRACE_FILTERS.reduce(
    (acc, filter) => {
      acc[filter.id] = events.filter((event) => matchesTraceFilter(event, filter.id)).length;
      return acc;
    },
    {} as Record<TraceFilter, number>,
  );
}

function mergeEvent(events: TraceEvent[], incoming: TraceEvent): TraceEvent[] {
  const idx = events.findIndex((event) => event.id === incoming.id || event.seq === incoming.seq);
  if (idx >= 0) {
    const next = [...events];
    next[idx] = incoming;
    return next.sort(bySeq);
  }
  return [...events, incoming].sort(bySeq);
}

function bySeq(a: TraceEvent, b: TraceEvent): number {
  return a.seq - b.seq;
}

function eventSearchText(event: TraceEvent): string {
  return `${event.title} ${event.summary ?? ""} ${event.actor} ${event.type} ${JSON.stringify(event.payload)}`.toLowerCase();
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ArtifactPanel({
  runId,
  caseId,
  artifact,
  content,
  loading,
  error,
  onClose,
}: {
  runId: string;
  caseId: string;
  artifact: CaseArtifact;
  content: ArtifactContent | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
}) {
  return (
    <div className="artifact-panel" role="dialog" aria-modal="true" aria-label={artifact.label}>
      <div className="artifact-panel-head">
        <div>
          <div className="eyebrow">artifact</div>
          <div className="artifact-title">{content?.filename ?? artifact.filename}</div>
        </div>
        <div className="artifact-actions">
          <a
            className="btn"
            href={artifactUrl(runId, caseId, artifact.name)}
            target="_blank"
            rel="noreferrer"
          >
            Open API
          </a>
          <button className="icon-btn" onClick={onClose} title="Close artifact">
            x
          </button>
        </div>
      </div>
      {loading && <div className="artifact-empty">loading…</div>}
      {error && <div className="artifact-empty error-text">{error}</div>}
      {content && <pre className="artifact-code">{content.content}</pre>}
    </div>
  );
}

function summarizeTrace(events: TraceEvent[]) {
  let totalTokens = 0;
  let promptTokens = 0;
  let completionTokens = 0;
  let reasoningTokens = 0;
  let hasTokens = false;
  let modelCalls = 0;
  let modelResponses = 0;
  let toolCalls = 0;
  let evidence = 0;
  let warnings = 0;
  let errors = 0;
  for (const event of events) {
    if (event.type === "model_call") modelCalls += 1;
    if (event.type === "model_response") modelResponses += 1;
    if (event.type === "tool_call") toolCalls += 1;
    if (event.type === "evidence_retrieved") evidence += 1;
    if (event.status === "warn") warnings += 1;
    if (event.status === "error") errors += 1;
    const usage = event.payload.usage;
    if (isUsage(usage)) {
      if (typeof usage.total_tokens === "number") {
        totalTokens += usage.total_tokens;
        hasTokens = true;
      }
      if (typeof usage.prompt_tokens === "number") promptTokens += usage.prompt_tokens;
      if (typeof usage.completion_tokens === "number") completionTokens += usage.completion_tokens;
      const completionDetails = usage.completion_tokens_details;
      if (isUsageDetails(completionDetails) && typeof completionDetails.reasoning_tokens === "number") {
        reasoningTokens += completionDetails.reasoning_tokens;
      }
      hasTokens = true;
    }
  }
  return {
    events: events.length,
    modelCalls,
    modelResponses,
    toolCalls,
    totalTokens: hasTokens ? totalTokens : 0,
    promptTokens,
    completionTokens,
    reasoningTokens,
    evidence,
    warnings,
    errors,
    lastEvent: events.at(-1)?.type ?? null,
  };
}

function isUsage(value: unknown): value is {
  total_tokens?: number;
  prompt_tokens?: number;
  completion_tokens?: number;
  completion_tokens_details?: unknown;
} {
  return typeof value === "object" && value !== null;
}

function isUsageDetails(value: unknown): value is { reasoning_tokens?: number } {
  return typeof value === "object" && value !== null;
}

function formatNumber(n: number): string {
  return n ? n.toLocaleString() : "—";
}

function traceSourceStatus(source: CaseTimeline["trace_source"]): Status {
  return source === "replay" ? "warn" : source === "live" ? "running" : "ok";
}

function traceSourceLabel(source: CaseTimeline["trace_source"]) {
  switch (source) {
    case "native":
      return "native trace";
    case "live":
      return "live trace";
    case "replay":
      return "replay trace";
  }
}

function artifactUrl(runId: string, caseId: string, name: string): string {
  return `/api/runs/${encodeURIComponent(runId)}/cases/${encodeURIComponent(caseId)}/artifacts/${encodeURIComponent(name)}`;
}

function truncate(s: string, n: number): string {
  return s.length <= n ? s : s.slice(0, n - 1) + "…";
}
