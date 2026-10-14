import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { IdeaForm } from "./idea-form";
import { Providers } from "@/app/providers";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn(), prefetch: vi.fn(), back: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

function renderForm() {
  return render(
    <Providers>
      <IdeaForm />
    </Providers>,
  );
}

describe("IdeaForm", () => {
  beforeEach(() => {
    localStorage.clear();
    push.mockClear();
  });

  it("disables submit until there is input", async () => {
    const user = userEvent.setup();
    renderForm();
    const button = screen.getByTestId("analyze-button");
    expect(button).toBeDisabled();
    await user.type(screen.getByTestId("idea-input"), "A tool for dog walkers");
    expect(button).toBeEnabled();
  });

  it("submits with Ctrl+Enter", async () => {
    const user = userEvent.setup();
    renderForm();
    await user.type(screen.getByTestId("idea-input"), "A tool for dog walkers");
    await user.keyboard("{Control>}{Enter}{/Control}");
    await waitFor(() => expect(push).toHaveBeenCalled());
    expect(push.mock.calls[0][0]).toMatch(/^\/ideas\//);
  });

  it("persists the draft to localStorage and restores it", async () => {
    const user = userEvent.setup();
    const { unmount } = renderForm();
    await user.type(screen.getByTestId("idea-input"), "Half-written idea");
    unmount();

    await waitFor(() => {
      const stored = localStorage.getItem("idea-forge.intake-draft.v1");
      expect(stored).toContain("Half-written idea");
    });

    renderForm();
    await waitFor(() => expect(screen.getByTestId("idea-input")).toHaveValue("Half-written idea"));
  });

  it("prefills from the ?draft= parameter when there is no saved draft", async () => {
    render(
      <Providers>
        <IdeaForm initialDraft="From a library search" />
      </Providers>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("idea-input")).toHaveValue("From a library search"),
    );
  });
});
