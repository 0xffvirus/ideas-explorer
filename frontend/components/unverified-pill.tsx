import { cn } from "@/lib/utils";

/**
 * Marks a factual claim that has no supporting source. Per the spec,
 * unverified claims keep muted text and carry this pill.
 */
export function UnverifiedPill({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border border-dashed border-border px-2 py-0.5 text-xs font-medium text-muted-foreground",
        className,
      )}
    >
      unverified
    </span>
  );
}
