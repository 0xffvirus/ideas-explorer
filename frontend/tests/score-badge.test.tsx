import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { ScoreBadge } from "@/components/score-badge";
import { renderWithProviders } from "./render";

describe("ScoreBadge", () => {
  it("shows the score without a flag when confidence is high", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ScoreBadge score={4} confidence={0.9} />);

    const badge = screen.getByLabelText("Score 4 out of 5. Confidence 90%");
    expect(badge).toHaveTextContent("4/5");
    expect(badge).not.toHaveTextContent("?");
    expect(badge).not.toHaveClass("border-dashed");

    await user.hover(badge);
    expect(await screen.findByRole("tooltip")).toHaveTextContent("Confidence 90%");
  });

  it("flags low confidence with a dashed border, a question mark and a tooltip", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ScoreBadge score={3} confidence={0.42} />);

    const badge = screen.getByLabelText("Score 3 out of 5. Confidence 42%");
    expect(badge).toHaveTextContent("3/5");
    expect(badge).toHaveTextContent("?");
    expect(badge).toHaveClass("border-dashed");

    await user.hover(badge);
    expect(await screen.findByRole("tooltip")).toHaveTextContent("Confidence 42%");
  });

  it("treats exactly 0.6 as confident (threshold is exclusive)", () => {
    renderWithProviders(<ScoreBadge score={5} confidence={0.6} />);
    const badge = screen.getByLabelText("Score 5 out of 5. Confidence 60%");
    expect(badge).not.toHaveTextContent("?");
    expect(badge).not.toHaveClass("border-dashed");
  });

  it("shows an em dash when the idea has no score", () => {
    renderWithProviders(<ScoreBadge score={null} />);
    expect(screen.getByLabelText("Not scored")).toHaveTextContent("—");
  });

  it("formats fractional scores with one decimal", () => {
    renderWithProviders(<ScoreBadge score={4.25} confidence={0.8} />);
    expect(screen.getByLabelText("Score 4.3 out of 5. Confidence 80%")).toHaveTextContent("4.3/5");
  });

  it("renders overall scores on the 0-100 scale", () => {
    renderWithProviders(<ScoreBadge score={76.4} scale={100} />);
    expect(screen.getByLabelText("Score 76.4 out of 100")).toHaveTextContent("76.4/100");
  });

  it("renders integer overall scores without a decimal", () => {
    renderWithProviders(<ScoreBadge score={58} scale={100} />);
    expect(screen.getByLabelText("Score 58 out of 100")).toHaveTextContent("58/100");
  });

  it("keeps dashed low-confidence styling on the 0-100 scale", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ScoreBadge score={41.2} scale={100} confidence={0.42} />);

    const badge = screen.getByLabelText("Score 41.2 out of 100. Confidence 42%");
    expect(badge).toHaveTextContent("41.2/100");
    expect(badge).toHaveTextContent("?");
    expect(badge).toHaveClass("border-dashed");

    await user.hover(badge);
    expect(await screen.findByRole("tooltip")).toHaveTextContent("Confidence 42%");
  });

  it("renders an em dash for a missing overall score", () => {
    renderWithProviders(<ScoreBadge score={null} scale={100} />);
    expect(screen.getByLabelText("Not scored")).toHaveTextContent("—");
  });
});
