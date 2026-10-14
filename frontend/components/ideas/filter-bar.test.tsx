import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FilterBar } from "./filter-bar";
import { DEFAULT_FILTERS } from "@/lib/library-params";

const TAGS = [
  { name: "ai", count: 12 },
  { name: "saas", count: 7 },
];

describe("FilterBar", () => {
  it("reports a status selection through onChange", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <FilterBar filters={DEFAULT_FILTERS} onChange={onChange} onClearAll={vi.fn()} tags={TAGS} />,
    );

    await user.click(screen.getByRole("button", { name: /status/i }));
    await user.click(await screen.findByRole("menuitemradio", { name: "Analyzed" }));

    expect(onChange).toHaveBeenCalledWith({ status: "done" });
  });

  it("clears the archived filter from its active pill", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <FilterBar
        filters={{ ...DEFAULT_FILTERS, archived: true }}
        onChange={onChange}
        onClearAll={vi.fn()}
        tags={TAGS}
      />,
    );

    await user.click(screen.getByRole("button", { name: /remove filter: archived/i }));
    expect(onChange).toHaveBeenCalledWith({ archived: false });
  });

  it("switches the layout to board", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <FilterBar filters={DEFAULT_FILTERS} onChange={onChange} onClearAll={vi.fn()} tags={TAGS} />,
    );

    await user.click(screen.getByRole("button", { name: /board/i }));
    expect(onChange).toHaveBeenCalledWith({ view: "board" });
  });

  it("calls onClearAll from the clear-all link", async () => {
    const user = userEvent.setup();
    const onClearAll = vi.fn();
    render(
      <FilterBar
        filters={{ ...DEFAULT_FILTERS, q: "pets", status: "done" }}
        onChange={vi.fn()}
        onClearAll={onClearAll}
        tags={TAGS}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Clear all" }));
    expect(onClearAll).toHaveBeenCalled();
  });

  it("lists tags with their counts", async () => {
    const user = userEvent.setup();
    render(
      <FilterBar filters={DEFAULT_FILTERS} onChange={vi.fn()} onClearAll={vi.fn()} tags={TAGS} />,
    );

    await user.click(screen.getByRole("button", { name: /^tag/i }));
    expect(await screen.findByText("#ai")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
  });
});
