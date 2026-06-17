import type {
  ArtifactContent,
  CaseSummary,
  CaseTimeline,
  NewCaseRequest,
  NewCaseResponse,
  RunSummary,
  SaveTraceResponse,
  TraceEvent,
} from "./types";

async function getJSON<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} for ${url}`);
  return res.json() as Promise<T>;
}

async function postJSON<T>(url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: body == null ? undefined : { "Content-Type": "application/json" },
    body: body == null ? undefined : JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} for ${url}`);
  return res.json() as Promise<T>;
}

export const api = {
  newCase: (payload: NewCaseRequest) => postJSON<NewCaseResponse>("/api/new-case", payload),
  runs: () => getJSON<RunSummary[]>("/api/runs"),
  cases: (runId: string) =>
    getJSON<CaseSummary[]>(`/api/runs/${encodeURIComponent(runId)}/cases`),
  timeline: (runId: string, caseId: string) =>
    getJSON<CaseTimeline>(
      `/api/runs/${encodeURIComponent(runId)}/cases/${encodeURIComponent(caseId)}/timeline`,
    ),
  artifact: (runId: string, caseId: string, name: string) =>
    getJSON<ArtifactContent>(
      `/api/runs/${encodeURIComponent(runId)}/cases/${encodeURIComponent(caseId)}/artifacts/${encodeURIComponent(name)}`,
    ),
  saveTrace: (runId: string, caseId: string) =>
    postJSON<SaveTraceResponse>(
      `/api/runs/${encodeURIComponent(runId)}/cases/${encodeURIComponent(caseId)}/save`,
    ),
};

// Subscribe to the SSE replay stream. Returns a cleanup function.
export function streamTimeline(
  runId: string,
  caseId: string,
  opts: { delayMs?: number; onEvent: (e: TraceEvent) => void; onDone?: () => void },
): () => void {
  const params = new URLSearchParams();
  if (opts.delayMs != null) params.set("delay_ms", String(opts.delayMs));
  const url = `/api/runs/${encodeURIComponent(runId)}/cases/${encodeURIComponent(
    caseId,
  )}/stream?${params.toString()}`;
  const es = new EventSource(url);
  es.addEventListener("trace", (ev) => {
    opts.onEvent(JSON.parse((ev as MessageEvent).data) as TraceEvent);
  });
  es.addEventListener("done", () => {
    opts.onDone?.();
    es.close();
  });
  es.onerror = () => {
    opts.onDone?.();
    es.close();
  };
  return () => es.close();
}
