"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { OPEN_PALETTE_EVENT } from "@/lib/events";

// cmdk + dialog code loads on first open instead of on every route's first load.
const CommandPalette = dynamic(
  () => import("./command-palette").then((mod) => mod.CommandPalette),
  {
    ssr: false,
  },
);

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target.isContentEditable;
}

export function PaletteHost() {
  const router = useRouter();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    function openPalette() {
      setOpen(true);
    }
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        openPalette();
        return;
      }
      if (
        event.key === "n" &&
        !event.metaKey &&
        !event.ctrlKey &&
        !event.altKey &&
        !event.shiftKey
      ) {
        if (isTypingTarget(event.target)) return;
        event.preventDefault();
        router.push("/");
      }
    }
    window.addEventListener(OPEN_PALETTE_EVENT, openPalette);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener(OPEN_PALETTE_EVENT, openPalette);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [router]);

  return open ? <CommandPalette open={open} onOpenChange={setOpen} /> : null;
}
