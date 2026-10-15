import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import { CompareView } from "@/components/compare/compare-view";
import { API_BASE_URL } from "@/lib/api/client";
import { parseCompareIds } from "@/lib/compare";
import { MOCK_IDEA_IDS } from "@/mocks/fixtures";
import { renderWithProviders } from "./render";
import { server } from "./mocks/server";

const api = API_BASE_URL;

const A = MOCK_IDEA_IDS.petTracker;
const B = MOCK_IDEA_IDS.quantumBackup;

describe("parseCompareIds", () => {
  it("accepts 2 and 3 unique uuids", () => {
    expect(parseCompareIds(`${A},${B}`)).toEqual({ ok: true, ids: [A, B] });
    expect(parseCompareIds(`${A},${B},${MOCK_IDEA_IDS.toolLibrary}`)).toEqual({
      ok: true,
      ids: [A, B, MOCK_IDEA_IDS.toolLibrary],
    });
  });

  it("rejects a missing selection", () => {
    const result = parseCompareIds(null);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.message).toMatch(/pick 2–3 ideas/i);
  });

  it("rejects a single idea", () => {
    const result = parseCompareIds(A);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.message).toMatch(/at least 2 ideas/i);
  });

  it("rejects four ideas", () => {
    const result = parseCompareIds(`${A},${B},${MOCK_IDEA_IDS.toolLibrary},${MOCK_IDEA_IDS.mealPlanner}`);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.message).toMatch(/up to 3 ideas/i);
  });

  it("rejects duplicates", () => {
    const result = parseCompareIds(`${A},${A}`);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.message).toMatch(/more than once/i);
  });

  it("rejects non-uuid ids", () => {
    const result = parseCompareIds(`${A},not-a-uuid`);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.message).toMatch(/invalid id/i);
  });
});

describe("CompareView", () => {
  it("renders aligned scorecards and an Open report link", async () => {
    renderWithProviders(<CompareView rawIds={`${A},${B}`} />);

    expect(await screen.findByRole("heading", { name: "Compare" })).toBeInTheDocument();
    expect(
      await screen.findByRole("link", { name: "Pet health tracker for busy owners" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Quantum-safe backup for small teams" }),
    ).toBeInTheDocument();

    // Dimension rows are aligned by dimension.
    expect(screen.getByRole("rowheader", { name: "Problem severity" })).toBeInTheDocument();
    expect(screen.getByRole("rowheader", { name: "Business model" })).toBeInTheDocument();

    // Pet tracker (done) has a scorecard, quantum backup has no report yet.
    expect(screen.getAllByLabelText(/Score 4 out of 5/).length).toBeGreaterThan(0);
    // Overall scores render on the 0-100 scale, not /5.
    expect(screen.getByLabelText("Score 76.4 out of 100")).toHaveTextContent("76.4/100");
    expect(screen.getByLabelText("Score 58 out of 100")).toHaveTextContent("58/100");
    expect(screen.getByText("No completed report yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open report" })).toBeInTheDocument();
  });

  it("does not call the API for an invalid selection", async () => {
    const compareRequests = vi.fn();
    server.use(
      http.get(`${api}/compare`, () => {
        compareRequests();
        return HttpResponse.json({ dimensions: [], entries: [] });
      }),
    );

    renderWithProviders(<CompareView rawIds={A} />);

    expect(await screen.findByText("Pick at least 2 ideas to compare.")).toBeInTheDocument();
    expect(compareRequests).not.toHaveBeenCalled();
  });

  it("does not call the API for duplicates", async () => {
    const compareRequests = vi.fn();
    server.use(
      http.get(`${api}/compare`, () => {
        compareRequests();
        return HttpResponse.json({ dimensions: [], entries: [] });
      }),
    );

    renderWithProviders(<CompareView rawIds={`${A},${A}`} />);

    expect(
      await screen.findByText(/same idea is selected more than once/i),
    ).toBeInTheDocument();
    expect(compareRequests).not.toHaveBeenCalled();
  });

  it("shows a friendly empty state when no ideas match", async () => {
    renderWithProviders(
      <CompareView rawIds="99999999-9999-4999-8999-999999999999,88888888-8888-4888-8888-888888888888" />,
    );

    expect(
      await screen.findByText(/could not be found/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to library" })).toHaveAttribute(
      "href",
      "/ideas",
    );
  });
});
