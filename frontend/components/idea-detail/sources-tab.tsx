import { ExternalLink } from "lucide-react";

import type { Source } from "@/lib/api/types";
import { sanitizeUrl } from "@/lib/markdown";

export interface SourcesTabProps {
  sources: Source[];
}

const sourceHost = (url: string): string => {
  try {
    return new URL(url).host;
  } catch {
    return url;
  }
};

/** Numbered source list; every entry links out in a new tab. */
export function SourcesTab({ sources }: SourcesTabProps) {
  if (sources.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No sources were attached to this report. Unverified claims are marked in their sections.
      </p>
    );
  }

  return (
    <ol className="flex flex-col gap-2">
      {sources.map((source) => (
        <li
          key={source.number}
          id={`source-${source.number}`}
          className="flex items-start gap-3 rounded-lg border border-border bg-card p-3"
        >
          <span
            className="mt-0.5 inline-flex size-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium tabular-nums"
            aria-hidden="true"
          >
            {source.number}
          </span>
          <div className="flex min-w-0 flex-col gap-0.5">
            <a
              href={sanitizeUrl(source.url) ?? "#"}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-sm text-sm font-medium text-foreground underline underline-offset-4 hover:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background focus-visible:outline-none"
            >
              {source.title || source.url}
              <ExternalLink className="size-3.5 shrink-0" aria-hidden="true" />
            </a>
            <span className="truncate text-xs text-muted-foreground">{sourceHost(source.url)}</span>
          </div>
        </li>
      ))}
    </ol>
  );
}
