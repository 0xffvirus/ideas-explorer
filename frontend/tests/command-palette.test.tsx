import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CommandPalette } from "@/components/command-palette";
import { MOCK_IDEA_IDS } from "@/mocks/handlers";
import { renderWithProviders } from "./render";

const { pushMock } = vi.hoisted(() => ({ pushMock: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

describe("CommandPalette", () => {
  it("shows actions when opened with an empty query", async () => {
    renderWithProviders(<CommandPalette defaultOpen />);

    expect(await screen.findByPlaceholderText(/search ideas/i)).toBeInTheDocument();
    expect(await screen.findByText("New idea")).toBeInTheDocument();
    expect(screen.getByText("Go to library")).toBeInTheDocument();
  });

  it("searches ideas through the API and renders titles with their status", async () => {
    const user = userEvent.setup();
    renderWithProviders(<CommandPalette defaultOpen />);

    const input = await screen.findByPlaceholderText(/search ideas/i);
    await user.type(input, "litter");

    expect(await screen.findByText("Pet health tracker for busy owners")).toBeInTheDocument();
    expect(screen.getByText("Done")).toBeInTheDocument();
    expect(screen.queryByText("Neighborhood tool library")).not.toBeInTheDocument();
  });

  it("navigates to the selected idea", async () => {
    const user = userEvent.setup();
    renderWithProviders(<CommandPalette defaultOpen />);

    const input = await screen.findByPlaceholderText(/search ideas/i);
    await user.type(input, "litter");
    const option = await screen.findByText("Pet health tracker for busy owners");
    await user.click(option);

    expect(pushMock).toHaveBeenCalledWith(`/ideas/${MOCK_IDEA_IDS.petTracker}`);
  });

  it("shows an empty state for queries with no matches", async () => {
    const user = userEvent.setup();
    renderWithProviders(<CommandPalette defaultOpen />);

    const input = await screen.findByPlaceholderText(/search ideas/i);
    await user.type(input, "zzzzzz");

    await waitFor(() => {
      expect(screen.getByText("No ideas found.")).toBeInTheDocument();
    });
  });
});
