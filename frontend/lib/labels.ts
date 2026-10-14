import type { IdeaStatus, SearchMode, Sort, Verdict } from "@/lib/api/types";

export const CATEGORY_LABELS: Record<string, string> = {
  b2b_saas: "B2B SaaS",
  b2c_app: "Consumer app",
  marketplace: "Marketplace",
  hardware: "Hardware",
  service: "Service",
  content: "Content",
  fintech: "Fintech",
  health: "Health",
  other: "Other",
};

export const CATEGORY_OPTIONS = Object.entries(CATEGORY_LABELS).map(([value, label]) => ({
  value,
  label,
}));

export const STATUS_OPTIONS: { value: IdeaStatus; label: string }[] = [
  { value: "draft", label: "Draft" },
  { value: "queued", label: "Queued" },
  { value: "analyzing", label: "Analyzing" },
  { value: "done", label: "Analyzed" },
  { value: "failed", label: "Failed" },
];

export const VERDICT_OPTIONS: { value: Verdict; label: string }[] = [
  { value: "pursue", label: "Pursue" },
  { value: "refine", label: "Refine" },
  { value: "park", label: "Park" },
];

export const SORT_OPTIONS: { value: Sort; label: string }[] = [
  { value: "recent", label: "Recently updated" },
  { value: "score", label: "Highest score" },
  { value: "title", label: "Title A-Z" },
];

export const MODE_OPTIONS: { value: SearchMode; label: string; hint: string }[] = [
  { value: "hybrid", label: "Hybrid", hint: "Keyword + meaning" },
  { value: "keyword", label: "Keyword", hint: "Exact terms" },
  { value: "semantic", label: "Meaning", hint: "Semantic match" },
];

export const MATCH_HINTS: Record<SearchMode, string> = {
  hybrid: "hybrid match (keyword + meaning)",
  keyword: "keyword match",
  semantic: "semantic match",
};

export function scoreBandLabel(min?: number, max?: number): string {
  if (min != null && max != null) return `Score ${min}–${max}`;
  if (min != null) return `Score ${min}+`;
  if (max != null) return `Score ≤ ${max}`;
  return "Score";
}
