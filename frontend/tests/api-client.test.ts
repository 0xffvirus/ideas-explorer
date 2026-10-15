import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import {
  API_BASE_URL,
  ApiError,
  apiFetch,
  apiUrl,
  extractApiErrorDetail,
  serializeQuery,
  toQueryInput,
} from "@/lib/api/client";
import type { IdeaListResponse } from "@/lib/api/types";
import { server } from "./mocks/server";

describe("serializeQuery", () => {
  it("skips undefined, null and empty values", () => {
    expect(
      serializeQuery({
        q: "pets",
        mode: undefined,
        status: null,
        tag: "",
        archived: false,
        score_min: 0,
        limit: 30,
      }),
    ).toBe("q=pets&archived=false&score_min=0&limit=30");
  });

  it("preserves booleans and zero", () => {
    expect(serializeQuery({ archived: false, score_min: 0 })).toBe("archived=false&score_min=0");
  });

  it("repeats array values and drops empty items", () => {
    expect(serializeQuery({ tag: [" pets ", "", "health"] })).toBe("tag=+pets+&tag=health");
  });
});

describe("toQueryInput", () => {
  it("drops non-primitive values", () => {
    expect(
      toQueryInput({ a: "x", b: 2, c: true, d: null, e: undefined, f: { nested: 1 } }),
    ).toEqual({
      a: "x",
      b: 2,
      c: true,
      d: null,
      e: undefined,
    });
  });
});

describe("apiUrl", () => {
  it("builds absolute URLs with query strings", () => {
    expect(apiUrl("/ideas", { q: "pets", limit: 6 })).toBe(`${API_BASE_URL}/ideas?q=pets&limit=6`);
    expect(apiUrl("ideas")).toBe(`${API_BASE_URL}/ideas`);
    expect(apiUrl("/runs/1/events")).toBe(`${API_BASE_URL}/runs/1/events`);
  });
});

describe("extractApiErrorDetail", () => {
  it("reads a string detail", () => {
    expect(extractApiErrorDetail({ detail: "idea not found" }, 404)).toBe("idea not found");
  });

  it("joins FastAPI validation errors with their locations", () => {
    expect(
      extractApiErrorDetail(
        {
          detail: [
            { loc: ["body", "raw_input"], msg: "String should have at most 5000 characters" },
            { loc: ["body", "context"], msg: "Invalid context" },
          ],
        },
        422,
      ),
    ).toBe(
      "body.raw_input: String should have at most 5000 characters; body.context: Invalid context",
    );
  });

  it("falls back for unknown bodies", () => {
    expect(extractApiErrorDetail(null, 500)).toBe("Request failed with status 500");
    expect(extractApiErrorDetail("<html>oops</html>", 502)).toBe("Request failed with status 502");
  });
});

describe("apiFetch", () => {
  it("returns parsed JSON and forwards serialized query params", async () => {
    server.use(
      http.get(`${API_BASE_URL}/ideas`, ({ request }) => {
        const url = new URL(request.url);
        return HttpResponse.json<IdeaListResponse>({
          items: [],
          next_cursor: url.search,
        });
      }),
    );

    const response = await apiFetch<IdeaListResponse>("/ideas", {
      query: { q: "pets", mode: "hybrid", limit: 6, tag: "", status: null },
    });
    expect(response.next_cursor).toBe("?q=pets&mode=hybrid&limit=6");
  });

  it("throws ApiError with parsed validation detail", async () => {
    server.use(
      http.post(`${API_BASE_URL}/ideas`, () =>
        HttpResponse.json(
          {
            detail: [{ loc: ["body", "raw_input"], msg: "Field required", type: "missing" }],
          },
          { status: 422 },
        ),
      ),
    );

    await expect(apiFetch("/ideas", { method: "POST", body: {} })).rejects.toMatchObject({
      name: "ApiError",
      status: 422,
      detail: "body.raw_input: Field required",
    });
  });

  it("throws ApiError with the string detail for HTTP errors", async () => {
    server.use(
      http.get(`${API_BASE_URL}/ideas/boom`, () =>
        HttpResponse.json({ detail: "idea not found" }, { status: 404 }),
      ),
    );

    const error = await apiFetch("/ideas/boom").catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 404, detail: "idea not found" });
  });

  it("throws ApiError with a fallback for non-JSON error bodies", async () => {
    server.use(
      http.get(`${API_BASE_URL}/ideas/oops`, () =>
        HttpResponse.text("<html>oops</html>", { status: 500 }),
      ),
    );

    await expect(apiFetch("/ideas/oops")).rejects.toMatchObject({
      status: 500,
      detail: "Request failed with status 500",
    });
  });

  it("wraps network failures in an ApiError with status 0", async () => {
    server.use(http.get(`${API_BASE_URL}/ideas/offline`, () => HttpResponse.error()));

    await expect(apiFetch("/ideas/offline")).rejects.toMatchObject({
      name: "ApiError",
      status: 0,
    });
  });

  it("handles empty 204 responses", async () => {
    server.use(
      http.post(`${API_BASE_URL}/ideas/empty`, () => new HttpResponse(null, { status: 204 })),
    );
    await expect(apiFetch("/ideas/empty", { method: "POST" })).resolves.toBeUndefined();
  });
});
