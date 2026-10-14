import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TooltipProvider } from "@/components/ui/tooltip";
import { OverallScore, ScoreBadge, StatusBadge, VerdictBadge } from "./badges";

function renderWithTooltip(ui: React.ReactElement) {
  return render(<TooltipProvider delayDuration={0}>{ui}</TooltipProvider>);
}

describe("ScoreBadge", () => {
  it("renders a plain score when confidence is at or above the floor", () => {
    renderWithTooltip(<ScoreBadge score={4} confidence={0.82} />);
    const badge = screen.getByText("4/5");
    expect(badge).toBeInTheDocument();
    expect(badge).not.toHaveAttribute("data-uncertain");
  });

  it("flags low confidence with a dashed border and a question mark", () => {
    renderWithTooltip(<ScoreBadge score={3} confidence={0.51} />);
    const badge = screen.getByText(/3\/5/);
    expect(badge).toHaveAttribute("data-uncertain", "true");
    expect(badge.textContent).toContain("?");
  });

  it("explains the confidence in a tooltip", async () => {
    const user = userEvent.setup();
    renderWithTooltip(<ScoreBadge score={5} confidence={0.44} />);
    await user.hover(screen.getByText(/5\/5/));
    expect(await screen.findByRole("tooltip")).toHaveTextContent("Jev confidence 44%");
  });

  it("renders a not-scored state without a score", () => {
    renderWithTooltip(<ScoreBadge score={null} confidence={null} />);
    expect(screen.getByText("Not scored")).toBeInTheDocument();
  });
});

describe("OverallScore", () => {
  it("shows an em dash when unscored", () => {
    render(<OverallScore score={null} />);
    expect(screen.getByTestId("overall-score")).toHaveTextContent("—");
  });

  it("renders the score with a screen-reader suffix", () => {
    render(<OverallScore score={72.3} />);
    expect(screen.getByTestId("overall-score")).toHaveTextContent("72.3");
    expect(screen.getByTestId("overall-score")).toHaveTextContent("out of 100");
  });
});

describe("Status and verdict badges", () => {
  it.each([
    ["done", "Analyzed"],
    ["queued", "Queued"],
    ["failed", "Failed"],
  ] as const)("renders status %s as %s", (status, label) => {
    render(<StatusBadge status={status} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it("renders nothing for a missing verdict", () => {
    const { container } = render(<VerdictBadge verdict={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders pursue", () => {
    render(<VerdictBadge verdict="pursue" />);
    expect(screen.getByText("Pursue")).toBeInTheDocument();
  });
});
