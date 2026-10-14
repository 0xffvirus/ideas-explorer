import type {
  CompareResponse,
  CreateIdeaRequest,
  CreateVersionRequest,
  IdeaDetail,
  IdeaList,
  ListIdeasParams,
  Report,
  RespondRunRequest,
  Run,
  RunStatus,
  TagsResponse,
  UpdateIdeaRequest,
} from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

function buildQuery(params?: Record<string, unknown>): string {
  if (!params) return "";
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object" && "detail" in body) {
      const detail = (body as { detail: unknown }).detail;
      if (typeof detail === "string") return detail;
      if (Array.isArray(detail)) {
        const first = detail[0] as { msg?: string } | undefined;
        if (first?.msg) return first.msg;
      }
    }
  } catch {
    // fall through to status text
  }
  return response.statusText || `Request failed with status ${response.status}`;
}

async function fetchResponse(path: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const detail = await response
      .clone()
      .json()
      .catch(() => undefined);
    throw new ApiError(response.status, await errorMessage(response), detail);
  }
  return response;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetchResponse(path, init);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  listIdeas(params: ListIdeasParams = {}): Promise<IdeaList> {
    return request<IdeaList>(`/ideas${buildQuery(params)}`);
  },

  createIdea(body: CreateIdeaRequest): Promise<IdeaDetail> {
    return request<IdeaDetail>("/ideas", { method: "POST", body: JSON.stringify(body) });
  },

  getIdea(id: string): Promise<IdeaDetail> {
    return request<IdeaDetail>(`/ideas/${encodeURIComponent(id)}`);
  },

  updateIdea(id: string, body: UpdateIdeaRequest): Promise<IdeaDetail> {
    return request<IdeaDetail>(`/ideas/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },

  createVersion(id: string, body: CreateVersionRequest): Promise<IdeaDetail> {
    return request<IdeaDetail>(`/ideas/${encodeURIComponent(id)}/versions`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  getSimilar(id: string, limit = 5): Promise<IdeaList> {
    return request<IdeaList>(`/ideas/${encodeURIComponent(id)}/similar${buildQuery({ limit })}`);
  },

  listTags(): Promise<TagsResponse> {
    return request<TagsResponse>("/tags");
  },

  getReport(id: string, version?: number): Promise<Report> {
    return request<Report>(`/ideas/${encodeURIComponent(id)}/report${buildQuery({ version })}`);
  },

  async getReportMarkdown(id: string, version?: number): Promise<string> {
    const response = await fetchResponse(
      `/ideas/${encodeURIComponent(id)}/report.md${buildQuery({ version })}`,
      {
        headers: { Accept: "text/markdown" },
      },
    );
    return response.text();
  },

  async getReportPdf(id: string, version?: number): Promise<Blob> {
    const response = await fetchResponse(
      `/ideas/${encodeURIComponent(id)}/report.pdf${buildQuery({ version })}`,
      {
        headers: { Accept: "application/pdf" },
      },
    );
    return response.blob();
  },

  compare(ids: string[]): Promise<CompareResponse> {
    return request<CompareResponse>(
      `/compare${buildQuery({ ids: ids.map((id) => encodeURIComponent(id)).join(",") })}`,
    );
  },

  rerunStep(runId: string, step: string): Promise<Run> {
    return request<Run>(
      `/runs/${encodeURIComponent(runId)}/steps/${encodeURIComponent(step)}/rerun`,
      { method: "POST" },
    );
  },

  respondToRun(runId: string, body: RespondRunRequest): Promise<Run> {
    return request<Run>(`/runs/${encodeURIComponent(runId)}/respond`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },
};

export const RUN_TERMINAL_STATUSES: RunStatus[] = ["done", "failed", "partial"];
