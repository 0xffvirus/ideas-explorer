import { whenMockReady } from "./mock-ready";

/** Base URL of the FastAPI backend. Must be absolute so `EventSource` can use it. */
export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");

export type QueryPrimitive = string | number | boolean;
export type QueryValue = QueryPrimitive | QueryPrimitive[] | null | undefined;
export type QueryInput = Record<string, QueryValue>;

function isQueryPrimitive(value: unknown): value is QueryPrimitive {
  return typeof value === "string" || typeof value === "number" || typeof value === "boolean";
}

/** Keep only values the serializer understands, dropping anything else. */
export function toQueryInput(source: Record<string, unknown>): QueryInput {
  const out: QueryInput = {};
  for (const [key, value] of Object.entries(source)) {
    if (isQueryPrimitive(value) || value === null || value === undefined) {
      out[key] = value;
    }
  }
  return out;
}

/** Serialize query params, skipping undefined, null, empty-string and empty-array values. */
export function serializeQuery(query: QueryInput): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) {
      for (const item of value) {
        if (item === undefined || item === null || item === "") continue;
        params.append(key, String(item));
      }
      continue;
    }
    params.set(key, String(value));
  }
  return params.toString();
}

/** Build an absolute API URL for fetch, SSE, markdown and PDF links. */
export function apiUrl(path: string, query?: QueryInput): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const queryString = query ? serializeQuery(query) : "";
  return `${API_BASE_URL}${normalizedPath}${queryString ? `?${queryString}` : ""}`;
}

/** Error thrown by `apiFetch` for non-2xx responses and network failures. */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(status > 0 ? `API ${status}: ${detail}` : detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/** Turn a FastAPI error body (`detail: string | ValidationError[]`) into a human message. */
export function extractApiErrorDetail(payload: unknown, status: number): string {
  if (isRecord(payload) && "detail" in payload) {
    const detail = payload.detail;
    if (typeof detail === "string" && detail.trim() !== "") {
      return detail;
    }
    if (Array.isArray(detail)) {
      const messages = detail.flatMap((item): string[] => {
        if (!isRecord(item) || typeof item.msg !== "string" || item.msg === "") return [];
        const location = Array.isArray(item.loc)
          ? item.loc
              .filter(
                (part): part is string | number =>
                  typeof part === "string" || typeof part === "number",
              )
              .join(".")
          : "";
        return [location ? `${location}: ${item.msg}` : item.msg];
      });
      if (messages.length > 0) return messages.join("; ");
    }
  }
  return `Request failed with status ${status}`;
}

export interface ApiFetchOptions extends Omit<RequestInit, "body"> {
  /** JSON-serialized request body. */
  body?: unknown;
  /** Query parameters appended to the path. */
  query?: QueryInput;
}

/**
 * Typed fetch against the Idea Forge API.
 *
 * - Serializes `query` (skipping undefined/null/empty values).
 * - JSON-encodes `body` and sets `Content-Type`.
 * - Throws `ApiError` with the parsed FastAPI `detail` on failure.
 */
export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  // In API-mocking mode, hold requests until the MSW worker is active.
  const mockGate = whenMockReady();
  if (mockGate) await mockGate;

  const { body, query, headers, ...init } = options;
  const requestHeaders = new Headers(headers);
  let requestBody: string | undefined;
  if (body !== undefined) {
    requestHeaders.set("Content-Type", "application/json");
    requestBody = JSON.stringify(body);
  }

  let response: Response;
  try {
    response = await fetch(apiUrl(path, query), {
      ...init,
      headers: requestHeaders,
      body: requestBody,
    });
  } catch (cause) {
    throw new ApiError(0, cause instanceof Error ? cause.message : "Network request failed");
  }

  if (!response.ok) {
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    throw new ApiError(response.status, extractApiErrorDetail(payload, response.status));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  if (text === "") {
    return undefined as T;
  }
  return JSON.parse(text) as T;
}
