import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SafeMarkdown } from "@/components/idea-detail/safe-markdown";
import { parseMarkdown } from "@/lib/markdown";

describe("SafeMarkdown", () => {
  it("renders headings, bold, inline code, links and lists", () => {
    render(
      <SafeMarkdown
        markdown={[
          "## Market size",
          "",
          "The market is **$8.2B** and `growing` fast.",
          "",
          "- first point",
          "- second [source](https://example.com/report)",
        ].join("\n")}
      />,
    );

    expect(screen.getByRole("heading", { level: 4, name: "Market size" })).toBeInTheDocument();
    expect(screen.getByText("$8.2B").tagName).toBe("STRONG");
    expect(screen.getByText("growing").tagName).toBe("CODE");
    const link = screen.getByRole("link", { name: "source" });
    expect(link).toHaveAttribute("href", "https://example.com/report");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("renders ordered lists", () => {
    render(<SafeMarkdown markdown={"1. one\n2. two"} />);
    const list = screen.getByRole("list");
    expect(list.tagName).toBe("OL");
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("strips javascript: links instead of rendering them", () => {
    render(<SafeMarkdown markdown={"[click me](javascript:alert(1))"} />);

    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getByText("click me")).toBeInTheDocument();
  });

  it("strips data: links", () => {
    render(
      <SafeMarkdown
        markdown={"[bad](data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==)"}
      />,
    );

    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getByText("bad")).toBeInTheDocument();
  });

  it("never executes raw HTML", () => {
    const { container } = render(
      <SafeMarkdown markdown={'before <img src="x" onerror="window.__pwned = true"> after'} />,
    );

    expect(container.querySelector("img")).toBeNull();
    expect((window as unknown as Record<string, unknown>).__pwned).toBeUndefined();
    expect(screen.getByText(/before <img/)).toBeInTheDocument();
  });
});

describe("parseMarkdown", () => {
  it("keeps unknown markup as paragraph text", () => {
    const blocks = parseMarkdown("<div>not html</div>");
    expect(blocks).toHaveLength(1);
    expect(blocks[0]).toMatchObject({ type: "paragraph" });
  });

  it("parses fenced code blocks", () => {
    const blocks = parseMarkdown("```\nconst x = 1;\n```");
    expect(blocks).toEqual([{ type: "code", value: "const x = 1;" }]);
  });
});
