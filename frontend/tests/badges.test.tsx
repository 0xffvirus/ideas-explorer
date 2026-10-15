import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusBadge } from "@/components/status-badge";
import { UnverifiedPill } from "@/components/unverified-pill";
import { VerdictBadge } from "@/components/verdict-badge";

describe("StatusBadge", () => {
  it("renders a label for every status", () => {
    const statuses = ["draft", "queued", "analyzing", "done", "failed"] as const;
    const labels = ["Draft", "Queued", "Analyzing", "Done", "Failed"];
    statuses.forEach((status, index) => {
      const { unmount } = render(<StatusBadge status={status} />);
      expect(screen.getByText(labels[index] as string)).toBeInTheDocument();
      unmount();
    });
  });

  it("uses distinct tones for done and failed", () => {
    const { unmount: unmountDone } = render(<StatusBadge status="done" />);
    expect(screen.getByText("Done").className).toContain("emerald");
    unmountDone();

    render(<StatusBadge status="failed" />);
    expect(screen.getByText("Failed").className).toContain("red");
  });
});

describe("VerdictBadge", () => {
  it("renders a label for every verdict", () => {
    const verdicts = ["pursue", "refine", "park"] as const;
    const labels = ["Pursue", "Refine", "Park"];
    verdicts.forEach((verdict, index) => {
      const { unmount } = render(<VerdictBadge verdict={verdict} />);
      expect(screen.getByText(labels[index] as string)).toBeInTheDocument();
      unmount();
    });
  });

  it("renders nothing without a verdict", () => {
    const { container } = render(<VerdictBadge verdict={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("UnverifiedPill", () => {
  it("labels unverified claims with a dashed pill", () => {
    render(<UnverifiedPill />);
    const pill = screen.getByText("unverified");
    expect(pill).toBeInTheDocument();
    expect(pill.className).toContain("border-dashed");
  });
});
