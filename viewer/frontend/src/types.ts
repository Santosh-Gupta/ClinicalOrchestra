// Mirror of viewer/backend/clinical_viewer/events.py. Keep in sync by hand;
// when the schema stabilizes, consider generating this from the OpenAPI spec
// exposed at /openapi.json.

export type EventType =
  | "run_started"
  | "case_started"
  | "problem_representation"
  | "round_started"
  | "query_generated"
  | "tool_call"
  | "search_executed"
  | "evidence_retrieved"
  | "synthesis"
  | "round_completed"
  | "prompt_built"
  | "model_call"
  | "model_response"
  | "answer"
  | "judge"
  | "case_completed"
  | "note"
  | "error";

export type Actor =
  | "runner"
  | "planner"
  | "retriever"
  | "synthesizer"
  | "diagnostician"
  | "judge"
  | "system";

export type Status = "ok" | "running" | "warn" | "error" | "pass" | "fail" | "info";

export interface TraceEvent {
  id: string;
  seq: number;
  ts: string | null;
  run_id: string;
  case_id: string;
  round: number | null;
  type: EventType;
  actor: Actor;
  title: string;
  summary: string | null;
  status: Status;
  payload: Record<string, unknown>;
}

export interface CaseTimeline {
  run_id: string;
  case_id: string;
  title: string | null;
  trace_source: "native" | "live" | "replay";
  trace_notice: string | null;
  expected_diagnosis: string | null;
  model_diagnosis: string | null;
  score: string | null;
  score_method: string | null;
  artifacts: CaseArtifact[];
  events: TraceEvent[];
}

export interface CaseArtifact {
  name: string;
  label: string;
  filename: string;
}

export interface ArtifactContent {
  name: string;
  filename: string;
  content: string;
}

export interface SaveTraceResponse {
  status: "ok";
  saved_at: string;
  directory: string;
  files: {
    json: string;
    markdown: string;
  };
  event_count: number;
  correct_answer: string | null;
  model_diagnosis: string | null;
  score: string | null;
}

export interface CaseSummary {
  case_id: string;
  expected_diagnosis: string | null;
  model_diagnosis: string | null;
  score: string | null;
  judge_match_type: string | null;
  query_count: number | null;
  evidence_count: number | null;
  error: string | null;
  has_native_events: boolean;
  is_live: boolean;
  is_complete: boolean | null;
  event_count: number | null;
  last_event_type: string | null;
}

export interface RunSummary {
  run_id: string;
  path: string;
  modified_at: string | null;
  case_count: number;
  pass_count: number | null;
  fail_count: number | null;
  has_results: boolean;
  native_event_case_count: number;
  live_case_count: number;
  incomplete_case_count: number;
}
