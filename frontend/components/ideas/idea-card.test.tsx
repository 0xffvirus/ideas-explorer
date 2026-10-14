import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { IdeaCard } from "./idea-card";
import type { IdeaSummary } from "@/lib/api/types";

const idea: IdeaSummary = {
  id: "00000000-0000-4000-8000-000000000001",
  title: "Dog walking marketplace for pet owners",
  status: "done",
  verdict: "pursue",
  category: "marketplace",
  overall_score: 78.5,
  one_liner: "Book trusted walkers in minutes.",
  pinned: false,
  archived_at: null,
  tags: ["marketplace", "community"],
  created_at: "2026-10-01T09:00:00.000Z",
  updated_at: "2026-10-01T10:00:00.000Z",
};

describe("IdeaCard", () => {
  it("links to the idea and shows the score and verdict", () => {
    render(<IdeaCard idea={idea} />);
    expect(screen.getByRole("link", { name: idea.title })).toHaveAttribute(
      "href",
      "/ideas/00000000-0000-4000-8000-000000000001",
    );
    expect(screen.getByText("Pursue")).toBeInTheDocument();
    expect(screen.getByTestId("overall-score")).toHaveTextContent("78.5");
    expect(screen.getByText("#marketplace")).toBeInTheDocument();
  });

  it("renders no checkbox without a selection handler", () => {
    render(<IdeaCard idea={idea} />);
    expect(screen.queryByTestId("idea-select")).not.toBeInTheDocument();
  });

  it("toggles selection through the checkbox", async () => {
    const user = userEvent.setup();
    const onToggle = vi.fn();
    render(<IdeaCard idea={idea} selected={false} onToggleSelected={onToggle} />);
    await user.click(screen.getByTestId("idea-select"));
    expect(onToggle).toHaveBeenCalledWith(idea.id);
  });

  it("shows a queued status with a spinner affordance", () => {
    render(<IdeaCard idea={{ ...idea, status: "queued", overall_score: null, verdict: null }} />);
    expect(screen.getByText("Queued")).toBeInTheDocument();
    expect(screen.queryByTestId("overall-score")).not.toBeInTheDocument();
  });
});
