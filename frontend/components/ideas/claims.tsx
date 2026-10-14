"use client";

import { createContext, useContext, useMemo } from "react";
import { cn } from "cn";
import type { Claim, Source } from "@/lib/api/types";
import { hostname, safeExternalUrl } from "@/lib/format";

const SourceNumbersContext = createContext<Map<string, number>>(new Map());

export function ReportSourcesProvider({
  sources,
  children,
}: {
  sources: Source[];
  children: React.ReactNode;
}) {
  const map = useMemo(() => new Map(sources.map((s) => [s.url, s.number])), [sources]);
  return <SourceNumbersContext.Provider value={map}>{children}</SourceNumbersContext.Provider>;
}

export function CitationRef({ urls }: { urls: string[] }) {
  const numbers = useContext(SourceNumbersContext);
  if (urls.length === 0) return null;
  return (
    <sup className="ms-1 whitespace-nowrap">
      {urls.map((url, index) => {
        const number = numbers.get(url);
        const safe = safeExternalUrl(url);
        return safe ? (
          <a
            key={`${url}-${index}`}
            href={safe}
            target="_blank"
            rel="noreferrer noopener"
            className="link ms-0.5 text-xs font-medium"
            title={safe}
            data-testid="citation"
          >
            [{number ?? hostname(url)}]
          </a>
        ) : (
          <span key={`${url}-${index}`} className="ms-0.5 text-xs" title={url}>
            [{number ?? "source"}]
          </span>
        );
      })}
    </sup>
  );
}

export function UnverifiedPill({ verified }: { verified: boolean | null | undefined }) {
  if (verified !== false) return null;
  return (
    <span
      className="badge border-dashed text-ink-muted"
      title="Jev could not verify this claim against its sources"
      data-testid="unverified-pill"
    >
      unverified
    </span>
  );
}

export function ClaimBlock({
  claim,
  className,
  as: Tag = "p",
}: {
  claim: Claim;
  className?: string;
  as?: "p" | "li" | "span";
}) {
  const unverified = claim.verified === false;
  return (
    <Tag className={cn("t-body", unverified && "text-ink-muted", className)}>
      {claim.text}
      <CitationRef urls={claim.source_urls ?? []} />
      {unverified && <UnverifiedPill verified={claim.verified} />}
    </Tag>
  );
}

export function ClaimList({ claims, className }: { claims: Claim[]; className?: string }) {
  if (claims.length === 0) return null;
  return (
    <ul className={cn("list-disc space-y-2 ps-5", className)}>
      {claims.map((claim, index) => (
        <ClaimBlock key={index} claim={claim} as="li" />
      ))}
    </ul>
  );
}

export function SectionPlaceholder({ label }: { label: string }) {
  return (
    <div className="rounded-card border border-dashed border-line-control bg-surface p-8 text-center">
      <p className="t-body">The {label} section was not completed in this run.</p>
      <p className="t-meta mt-1">Re-run it, or wait for the analysis to finish.</p>
    </div>
  );
}
