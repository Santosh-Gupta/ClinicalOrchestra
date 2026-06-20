import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { api, streamTimeline } from "./api";
import { EventCard } from "./components/EventCard";
import { Badge } from "./components/ui";
import type {
  ArtifactContent,
  CaseArtifact,
  CaseSummary,
  CaseTimeline,
  HealthResponse,
  NewCaseRequest,
  NewCaseResponse,
  RunSummary,
  SaveTraceResponse,
  Status,
  TraceEvent,
} from "./types";

type TraceFilter = "all" | "model" | "retrieval" | "reasoning" | "judgement" | "errors";

export default function App() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [activeRun, setActiveRun] = useState<string | null>(null);
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [caseFilter, setCaseFilter] = useState("");
  const [activeCase, setActiveCase] = useState<string | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [newCaseOpen, setNewCaseOpen] = useState(false);
  const [newCaseState, setNewCaseState] = useState<{
    submitting: boolean;
    result: NewCaseResponse | null;
    error: string | null;
  }>({ submitting: false, result: null, error: null });

  const [timeline, setTimeline] = useState<CaseTimeline | null>(null);
  const [shown, setShown] = useState<TraceEvent[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [traceFilter, setTraceFilter] = useState<TraceFilter>("all");
  const [traceSearch, setTraceSearch] = useState("");
  const [runsPanelOpen, setRunsPanelOpen] = useState(true);
  const [casesPanelOpen, setCasesPanelOpen] = useState(true);
  const [expandVersion, setExpandVersion] = useState(0);
  const [collapseVersion, setCollapseVersion] = useState(0);
  const [saveState, setSaveState] = useState<{
    saving: boolean;
    result: SaveTraceResponse | null;
    error: string | null;
  }>({ saving: false, result: null, error: null });
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
    api.health().then(setHealth).catch(console.error);
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
    const needsRefresh = cases.length === 0 || cases.some((c) => c.is_live || c.is_complete === false);
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
    setSaveState({ saving: false, result: null, error: null });
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
  const isWorking = Boolean(timeline && (streaming || activeCaseSummary?.is_live || activeCaseSummary?.is_complete === false));
  const workingStatus = useMemo(
    () => (timeline ? workingStatusText(shown.at(-1) ?? null, { streaming, isLive: Boolean(activeCaseSummary?.is_live) }) : null),
    [timeline, shown, streaming, activeCaseSummary?.is_live],
  );

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

  function submitNewCase(payload: NewCaseRequest) {
    setNewCaseState({ submitting: true, result: null, error: null });
    api
      .newCase(payload)
      .then((result) => {
        setNewCaseState({ submitting: false, result, error: null });
        setNewCaseOpen(false);
        refreshRuns();
        setActiveRun(result.run_id);
        window.setTimeout(() => {
          refreshRuns();
          refreshCases(result.run_id);
          setActiveCase(result.case_id);
        }, 700);
      })
      .catch((err) =>
        setNewCaseState({
          submitting: false,
          result: null,
          error: err instanceof Error ? err.message : String(err),
        }),
      );
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

  function saveTrace() {
    if (!timeline) return;
    setSaveState({ saving: true, result: null, error: null });
    api
      .saveTrace(timeline.run_id, timeline.case_id)
      .then((result) => setSaveState({ saving: false, result, error: null }))
      .catch((err) =>
        setSaveState({
          saving: false,
          result: null,
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
                className="panel-action new-case-action"
                onClick={() => setNewCaseOpen(true)}
                title="Create a new viewer-generated case"
              >
                New
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
        {newCaseState.result && (
          <div className="rail-note">
            started <code>{newCaseState.result.case_id}</code>
          </div>
        )}
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
              <button
                className="btn"
                onClick={() => setExpandVersion((version) => version + 1)}
                disabled={streaming || shown.length === 0}
              >
                Expand all
              </button>
              <button
                className="btn"
                onClick={() => setCollapseVersion((version) => version + 1)}
                disabled={streaming || shown.length === 0}
              >
                Collapse all
              </button>
              <button
                className="btn"
                onClick={() => exportTraceMarkdown(timeline, visibleEvents)}
                disabled={visibleEvents.length === 0}
              >
                Export MD
              </button>
              <button
                className="btn"
                onClick={saveTrace}
                disabled={saveState.saving || shown.length === 0}
                title="Save structured JSON and Markdown under viewer/user_generated/"
              >
                {saveState.saving ? "Saving…" : "Save"}
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
              {isWorking && workingStatus && (
                <div className="working-banner" role="status" aria-live="polite">
                  <span className="working-pulse" aria-hidden="true" />
                  <div>
                    <div className="working-title">Working<span className="working-dots" /></div>
                    <div className="working-text">{workingStatus}</div>
                  </div>
                </div>
              )}
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
              {saveState.result && (
                <div className="trace-save">
                  saved {saveState.result.event_count} events to <code>{saveState.result.directory}</code>
                </div>
              )}
              {saveState.error && <div className="trace-save error-text">{saveState.error}</div>}
            </div>
            {visibleEvents.map((e) => (
              <EventCard
                key={e.id}
                event={e}
                expandVersion={expandVersion}
                collapseVersion={collapseVersion}
              />
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
      {newCaseOpen && (
        <NewCaseDialog
          submitting={newCaseState.submitting}
          error={newCaseState.error}
          allowRetrieval={health?.allow_retrieval ?? false}
          allowModelRuns={health?.allow_model_runs ?? false}
          onSubmit={submitNewCase}
          onClose={() => setNewCaseOpen(false)}
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

function workingStatusText(event: TraceEvent | null, opts: { streaming: boolean; isLive: boolean }): string {
  if (!event) {
    return opts.isLive ? "Waiting for the first trace event from the running case." : "Preparing the trace.";
  }
  const round = event.round != null ? ` round ${event.round}` : "";
  switch (event.type) {
    case "case_started":
      return "Reading the case and setting up the diagnostic run.";
    case "problem_representation":
      return "Building the problem representation from the case text.";
    case "round_started":
      return `Starting retrieval${round}.`;
    case "query_generated":
      return `Planning a literature query${round}: ${event.title}`;
    case "tool_call":
    case "search_executed":
      return `Using a retrieval tool${round}: ${event.summary ?? event.title}`;
    case "evidence_retrieved":
      return `Reviewing retrieved evidence${round}: ${event.title}`;
    case "synthesis":
      return `Synthesizing evidence and discriminators${round}.`;
    case "round_completed":
      return `Finished retrieval${round}; deciding whether more information is needed.`;
    case "prompt_built":
      return "Assembling the final injected prompt packet.";
    case "model_call":
      return `Calling the model: ${event.summary ?? event.title}`;
    case "model_response":
      return "Parsing the model response and usage metadata.";
    case "answer":
      return "Preparing the final diagnosis answer.";
    case "judge":
      return "Comparing the answer against the expected diagnosis.";
    case "error":
      return `Run reported an error: ${event.summary ?? event.title}`;
    case "case_completed":
      return "Finalizing the run.";
    default:
      return opts.streaming ? `Streaming ${event.actor} activity: ${event.title}` : `Latest step: ${event.title}`;
  }
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

function NewCaseDialog({
  submitting,
  error,
  allowRetrieval,
  allowModelRuns,
  onSubmit,
  onClose,
}: {
  submitting: boolean;
  error: string | null;
  allowRetrieval: boolean;
  allowModelRuns: boolean;
  onSubmit: (payload: NewCaseRequest) => void;
  onClose: () => void;
}) {
  const [title, setTitle] = useState("");
  const [prompt, setPrompt] = useState("");
  const [correctAnswer, setCorrectAnswer] = useState("");
  const [aliases, setAliases] = useState("");
  const [dryRun, setDryRun] = useState(true);
  const [retrieve, setRetrieve] = useState(false);
  const [judge, setJudge] = useState(false);
  const [maxQueries, setMaxQueries] = useState(2);
  const [articlesPerQuery, setArticlesPerQuery] = useState(3);
  const [maxRounds, setMaxRounds] = useState(1);
  const [model, setModel] = useState("");

  const canSubmit = prompt.trim().length >= 20 && !submitting;
  const retrievalEnabled = allowRetrieval;
  const modelEnabled = allowModelRuns;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!canSubmit) return;
    onSubmit({
      title: title.trim() || "Untitled case",
      prompt: prompt.trim(),
      correct_answer: correctAnswer.trim() || null,
      aliases: aliases
        .split("\n")
        .map((alias) => alias.trim())
        .filter(Boolean),
      dry_run: modelEnabled ? dryRun : true,
      retrieve: retrievalEnabled ? retrieve : false,
      judge: modelEnabled && judge && Boolean(correctAnswer.trim()),
      max_queries: maxQueries,
      articles_per_query: articlesPerQuery,
      max_rounds: maxRounds,
      model: model.trim() || null,
    });
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <form className="new-case-dialog" onSubmit={submit}>
        <div className="artifact-panel-head">
          <div>
            <div className="eyebrow">viewer generated</div>
            <div className="artifact-title">New case</div>
          </div>
          <button type="button" className="icon-btn" onClick={onClose} title="Close">
            x
          </button>
        </div>
        <div className="new-case-body">
          <label className="field">
            <span>title optional</span>
            <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="leave blank for demo" />
          </label>
          <label className="field">
            <span>case text</span>
            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="Paste the de-identified case presentation..."
              rows={8}
            />
          </label>
          <div className="field-grid">
            <label className="field">
              <span>correct answer</span>
              <input
                value={correctAnswer}
                onChange={(event) => setCorrectAnswer(event.target.value)}
                placeholder="optional, for benchmarking the harness"
              />
            </label>
            <label className="field">
              <span>answer aliases</span>
              <textarea
                value={aliases}
                onChange={(event) => setAliases(event.target.value)}
                placeholder="one per line"
                rows={3}
              />
            </label>
          </div>
          <div className="option-row">
            <label><input type="checkbox" checked={retrieve && retrievalEnabled} onChange={(event) => setRetrieve(event.target.checked)} disabled={!retrievalEnabled} /> PubMed retrieval</label>
            {modelEnabled && (
              <>
                <label><input type="checkbox" checked={dryRun} onChange={(event) => setDryRun(event.target.checked)} /> dry run</label>
                <label><input type="checkbox" checked={judge} onChange={(event) => setJudge(event.target.checked)} disabled={!correctAnswer.trim()} /> judge</label>
              </>
            )}
          </div>
          <div className="option-help">
            <div><strong>PubMed retrieval</strong> lets the backend search PubMed for evidence.</div>
            {modelEnabled && (
              <>
                <div><strong>Dry run</strong> builds the trace artifacts without calling a model API.</div>
                <div><strong>Judge</strong> scores the model answer against the correct answer when one is provided.</div>
              </>
            )}
          </div>
          {(!retrievalEnabled || !modelEnabled) && (
            <div className="demo-note">
              This demo is configured for safe public use. {!retrievalEnabled && "PubMed retrieval is disabled. "}
              {!modelEnabled && "Model scoring controls are hidden in the public UI."}
            </div>
          )}
          <div className="field-grid compact">
            <label className="field">
              <span>queries</span>
              <input type="number" min={1} max={8} value={maxQueries} onChange={(event) => setMaxQueries(Number(event.target.value))} />
            </label>
            <label className="field">
              <span>articles/query</span>
              <input type="number" min={1} max={10} value={articlesPerQuery} onChange={(event) => setArticlesPerQuery(Number(event.target.value))} />
            </label>
            <label className="field">
              <span>rounds</span>
              <input type="number" min={1} max={4} value={maxRounds} onChange={(event) => setMaxRounds(Number(event.target.value))} />
            </label>
          </div>
          {modelEnabled && (
            <label className="field">
              <span>model</span>
              <input
                value={model}
                onChange={(event) => setModel(event.target.value)}
                placeholder="optional; uses environment default"
              />
            </label>
          )}
          {error && <div className="error-text">{error}</div>}
        </div>
        <div className="new-case-actions">
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn primary" disabled={!canSubmit}>
            {submitting ? "Starting..." : "Start case"}
          </button>
        </div>
      </form>
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

function exportTraceMarkdown(timeline: CaseTimeline, events: TraceEvent[]) {
  const lines = [
    `# ClinicalHarness Trace: ${timeline.case_id}`,
    "",
    `- Run: \`${timeline.run_id}\``,
    `- Case: \`${timeline.case_id}\``,
    `- Source: ${traceSourceLabel(timeline.trace_source)}`,
    timeline.score ? `- Score: ${timeline.score}` : null,
    timeline.expected_diagnosis ? `- Expected: ${timeline.expected_diagnosis}` : null,
    timeline.model_diagnosis ? `- Model diagnosis: ${timeline.model_diagnosis}` : null,
    `- Exported events: ${events.length}`,
    "",
    "## Events",
    "",
    ...events.flatMap((event) => eventMarkdown(event)),
  ].filter((line): line is string => line !== null);

  const blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${safeFilename(timeline.run_id)}__${safeFilename(timeline.case_id)}__trace.md`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function eventMarkdown(event: TraceEvent): string[] {
  const header = `### ${event.seq + 1}. ${event.type}: ${event.title}`;
  const meta = [
    `- Actor: ${event.actor}`,
    event.round != null ? `- Round: ${event.round}` : null,
    `- Status: ${event.status}`,
    event.summary ? `- Summary: ${event.summary}` : null,
  ].filter((line): line is string => line !== null);
  return [
    header,
    "",
    ...meta,
    "",
    "```json",
    JSON.stringify(event.payload, null, 2),
    "```",
    "",
  ];
}

function safeFilename(value: string): string {
  return value.replace(/[^a-z0-9._-]+/gi, "_").replace(/^_+|_+$/g, "") || "trace";
}

function truncate(s: string, n: number): string {
  return s.length <= n ? s : s.slice(0, n - 1) + "…";
}
