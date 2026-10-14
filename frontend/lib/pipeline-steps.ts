import type { RunStepName } from "@/lib/api/types";

export const PIPELINE_STEPS: { id: RunStepName; label: string }[] = [
  { id: "refine", label: "Refine brief" },
  { id: "clarify", label: "Clarify" },
  { id: "market", label: "Market" },
  { id: "competitors", label: "Competitors" },
  { id: "customers", label: "Customers" },
  { id: "feasibility", label: "Feasibility" },
  { id: "business_model", label: "Business model" },
  { id: "critic", label: "Critic & scorecard" },
];

export const STEP_LABELS = Object.fromEntries(PIPELINE_STEPS.map((s) => [s.id, s.label])) as Record<
  RunStepName,
  string
>;

export const STEP_STATUS_LABELS = {
  pending: "Queued",
  running: "Running",
  done: "Done",
  failed: "Failed",
  skipped: "Skipped",
} as const;
