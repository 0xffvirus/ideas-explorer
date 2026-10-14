"use client";

import { Search } from "lucide-react";
import { OPEN_PALETTE_EVENT } from "@/lib/events";

export function PaletteTrigger() {
  return (
    <button
      type="button"
      onClick={() => window.dispatchEvent(new CustomEvent(OPEN_PALETTE_EVENT))}
      className="icon-btn"
      aria-label="Open command palette (Command or Control + K)"
      data-testid="palette-trigger"
    >
      <Search size={18} aria-hidden="true" />
    </button>
  );
}
