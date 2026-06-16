import type { Actor, Status } from "../types";

export function Badge({ status, label }: { status: Status; label?: string }) {
  return <span className={`badge ${status}`}>{label ?? status}</span>;
}

export const ACTOR_COLOR: Record<Actor, string> = {
  runner: "var(--runner)",
  planner: "var(--planner)",
  retriever: "var(--retriever)",
  synthesizer: "var(--synthesizer)",
  diagnostician: "var(--diagnostician)",
  judge: "var(--judge)",
  system: "var(--system)",
};

// A short glyph per event-type for the timeline node.
export const TYPE_GLYPH: Record<string, string> = {
  run_started: "▶",
  case_started: "◆",
  problem_representation: "≡",
  round_started: "↻",
  query_generated: "?",
  tool_call: "⚙",
  search_executed: "⌕",
  evidence_retrieved: "¶",
  synthesis: "∴",
  round_completed: "✓",
  prompt_built: "▣",
  model_call: "◇",
  model_response: "↩",
  answer: "★",
  judge: "⚖",
  case_completed: "■",
  note: "·",
  error: "!",
};
