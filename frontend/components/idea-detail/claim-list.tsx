import { UnverifiedPill } from "@/components/unverified-pill";
import type { ReportClaim, Source } from "@/lib/api/types";
import { sanitizeUrl } from "@/lib/markdown";
import { cn } from "@/lib/utils";

export interface ClaimListProps {
  claims: ReportClaim[];
  sources: Source[];
}

/**
 * Claim list: verified claims link their citation numbers to the report
 * sources; unsourced claims are muted and carry the "unverified" pill.
 */
export function ClaimList({ claims, sources }: ClaimListProps) {
  const visible = claims.filter((claim) => claim.text.trim() !== "");
  if (visible.length === 0) return null;
  const byNumber = new Map(sources.map((source) => [source.number, source]));

  return (
    <ul className="flex flex-col gap-2">
      {visible.map((claim, index) => {
        const verified = claim.status === "verified";
        return (
          <li
            key={`${claim.text}-${index}`}
            className={cn(
              "flex flex-wrap items-baseline gap-1.5 text-sm leading-relaxed",
              !verified && "text-muted-foreground",
            )}
          >
            <span>{claim.text}</span>
            {(claim.citation_numbers ?? []).map((number) => {
              const source = byNumber.get(number);
              return source ? (
                <a
                  key={number}
                  href={sanitizeUrl(source.url) ?? "#"}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-sm text-xs font-medium text-foreground underline underline-offset-2 hover:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background focus-visible:outline-none"
                  aria-label={`Source ${number}: ${source.title || source.url}`}
                >
                  [{number}]
                </a>
              ) : (
                <span key={number} className="text-xs text-muted-foreground">
                  [{number}]
                </span>
              );
            })}
            {verified ? null : <UnverifiedPill />}
          </li>
        );
      })}
    </ul>
  );
}
