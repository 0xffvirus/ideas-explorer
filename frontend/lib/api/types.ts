import type { components, operations } from "./schema";

/** Convenience aliases for the generated OpenAPI component schemas. */
export type IdeaSummary = components["schemas"]["IdeaSummary"];
export type IdeaDetail = components["schemas"]["IdeaDetail"];
export type IdeaListResponse = components["schemas"]["IdeaListResponse"];
export type IdeaCreate = components["schemas"]["IdeaCreate"];
export type IdeaUpdate = components["schemas"]["IdeaUpdate"];
export type IdeaVersionCreate = components["schemas"]["IdeaVersionCreate"];
export type IdeaStatus = components["schemas"]["IdeaStatus"];
export type IdeaVerdict = components["schemas"]["IdeaVerdict"];
export type SearchMode = components["schemas"]["SearchMode"];
export type SortField = components["schemas"]["SortField"];
export type TagCount = components["schemas"]["TagCount"];
export type RunRead = components["schemas"]["RunRead"];
export type RunStepRead = components["schemas"]["RunStepRead"];
export type SimilarIdea = components["schemas"]["SimilarIdea"];
export type IdeaVersionRead = components["schemas"]["IdeaVersionRead"];
export type Report = components["schemas"]["Report"];
export type ReportHeader = components["schemas"]["ReportHeader"];
export type ReportBrief = components["schemas"]["ReportBrief"];
export type ReportClaim = components["schemas"]["ReportClaim"];
export type ReportSection = components["schemas"]["ReportSection"];
export type ScorecardEntry = components["schemas"]["ScorecardEntry"];
export type NextStep = components["schemas"]["NextStep"];
export type Source = components["schemas"]["Source"];
export type CompareReport = components["schemas"]["CompareReport"];
export type CompareEntry = components["schemas"]["CompareEntry"];
export type CompareIdeaReport = components["schemas"]["CompareIdeaReport"];
export type ClarifyRequest = components["schemas"]["ClarifyRequest"];
export type ClarifyingQuestion = components["schemas"]["ClarifyingQuestion"];

/** Query parameters accepted by `GET /ideas`. */
export type IdeasQuery = NonNullable<operations["list_ideas_ideas_get"]["parameters"]["query"]>;
