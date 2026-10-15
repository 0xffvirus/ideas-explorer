import { ScoreBadge } from "@/components/score-badge";
import { VerdictBadge } from "@/components/verdict-badge";
import { ClaimList } from "@/components/idea-detail/claim-list";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import type { IdeaVerdict, Report, ScorecardEntry } from "@/lib/api/types";
import { formatDate } from "@/lib/utils";

function toVerdict(value: string | null | undefined): IdeaVerdict | null {
  return value === "pursue" || value === "refine" || value === "park" ? value : null;
}

const SCORE_BASIS_LABEL: Record<Report["header"]["score_basis"], string | null> = {
  all_dimensions: null,
  partial: "Partial evidence",
  not_scored: "Not scored",
};

function ScorecardGrid({ entries }: { entries: ScorecardEntry[] }) {
  return (
    <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {entries.map((entry) => (
        <li key={entry.dimension}>
          <Card
            className={entry.needs_review ? "h-full border-dashed" : "h-full"}
            data-needs-review={entry.needs_review || undefined}
          >
            <CardContent className="flex h-full flex-col gap-3 p-4">
              <div className="flex items-start justify-between gap-2">
                <h3 className="text-sm font-medium text-foreground">
                  {entry.label}
                  {entry.needs_review ? (
                    <span
                      className="ml-1 text-muted-foreground"
                      aria-label="Needs review"
                      title="Needs review"
                    >
                      ?
                    </span>
                  ) : null}
                </h3>
                <ScoreBadge score={entry.score} confidence={entry.confidence} />
              </div>
              {entry.confidence !== null && entry.confidence !== undefined ? (
                <Progress
                  value={Math.round(entry.confidence * 100)}
                  label={`${entry.label} confidence`}
                  className="h-1.5"
                />
              ) : null}
              {entry.rationale.trim() !== "" ? (
                <p className="text-sm leading-relaxed text-muted-foreground">{entry.rationale}</p>
              ) : null}
              <p className="mt-auto text-xs text-muted-foreground">Source: {entry.source}</p>
            </CardContent>
          </Card>
        </li>
      ))}
    </ul>
  );
}

function BriefField({ label, value }: { label: string; value: string }) {
  if (value.trim() === "") return null;
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
        {label}
      </dt>
      <dd className="text-sm leading-relaxed whitespace-pre-wrap text-foreground">{value}</dd>
    </div>
  );
}

export interface OverviewTabProps {
  report: Report;
}

/** Overview tab: header summary, scorecard, polished brief, next steps, claims. */
export function OverviewTab({ report }: OverviewTabProps) {
  const { header, brief } = report;
  const scorecard = report.scorecard ?? [];
  const nextSteps = report.next_steps ?? [];
  const basisLabel = SCORE_BASIS_LABEL[header.score_basis];
  const confidence =
    header.verdict_confidence !== null && header.verdict_confidence !== undefined
      ? `${Math.round(header.verdict_confidence * 100)}% verdict confidence`
      : null;

  return (
    <div className="flex flex-col gap-8">
      <section aria-labelledby="overview-summary-heading" className="flex flex-col gap-3">
        <h2 id="overview-summary-heading" className="sr-only">
          Summary
        </h2>
        <div className="flex flex-wrap items-center gap-3">
          <VerdictBadge verdict={toVerdict(header.verdict)} />
          <ScoreBadge score={header.overall_score} scale={100} />
          {confidence ? (
            <span className="text-sm text-muted-foreground">{confidence}</span>
          ) : null}
          {basisLabel ? <Badge variant="warning">{basisLabel}</Badge> : null}
        </div>
        <p className="max-w-3xl text-base leading-relaxed text-foreground">{header.one_liner}</p>
        <p className="text-xs text-muted-foreground">
          Run {formatDate(header.run_date)} · ${header.cost_usd.toFixed(2)} analysis cost
        </p>
      </section>

      <section aria-labelledby="overview-scorecard-heading" className="flex flex-col gap-3">
        <h2 id="overview-scorecard-heading" className="text-lg font-semibold tracking-tight">
          Scorecard
        </h2>
        {scorecard.length > 0 ? (
          <ScorecardGrid entries={scorecard} />
        ) : (
          <p className="text-sm text-muted-foreground">
            No dimension scores were produced for this run.
          </p>
        )}
      </section>

      <section aria-labelledby="overview-brief-heading" className="flex flex-col gap-3">
        <h2 id="overview-brief-heading" className="text-lg font-semibold tracking-tight">
          Polished brief
        </h2>
        <Card>
          <CardContent className="flex flex-col gap-4 p-5">
            <dl className="grid gap-4 sm:grid-cols-2">
              <BriefField label="One-liner" value={brief.one_liner} />
              <BriefField label="Target users" value={brief.target_users} />
              <BriefField label="Problem" value={brief.problem} />
              <BriefField label="Solution" value={brief.solution} />
              <BriefField label="Value proposition" value={brief.value_prop} />
            </dl>
            {(brief.key_assumptions?.length ?? 0) > 0 ? (
              <div className="flex flex-col gap-1.5">
                <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                  Key assumptions
                </h3>
                <ul className="flex list-disc flex-col gap-1 pl-5 text-sm leading-relaxed marker:text-muted-foreground">
                  {brief.key_assumptions?.map((assumption) => (
                    <li key={assumption}>{assumption}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {(brief.variants?.length ?? 0) > 0 ? (
              <div className="flex flex-col gap-1.5">
                <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                  Variants
                </h3>
                <ul className="flex list-disc flex-col gap-1 pl-5 text-sm leading-relaxed marker:text-muted-foreground">
                  {brief.variants?.map((variant) => (
                    <li key={variant}>{variant}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {(brief.claims?.length ?? 0) > 0 ? (
              <div className="border-t border-border pt-4">
                <h3 className="mb-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                  Brief claims
                </h3>
                <ClaimList claims={brief.claims ?? []} sources={report.sources ?? []} />
              </div>
            ) : null}
          </CardContent>
        </Card>
      </section>

      <section aria-labelledby="overview-next-steps-heading" className="flex flex-col gap-3">
        <h2 id="overview-next-steps-heading" className="text-lg font-semibold tracking-tight">
          Next steps
        </h2>
        {nextSteps.length > 0 ? (
          <ul className="grid gap-3 sm:grid-cols-2">
            {nextSteps.map((step, index) => (
              <li key={`${step.assumption}-${index}`}>
                <Card className="h-full">
                  <CardHeader className="p-4 pb-2">
                    <CardTitle asChild>
                      <h3 className="text-sm">{step.assumption}</h3>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-1 p-4 pt-1">
                    <p className="text-sm text-muted-foreground">{step.test}</p>
                    {step.cost_hint ? (
                      <p className="text-xs text-muted-foreground">{step.cost_hint}</p>
                    ) : null}
                  </CardContent>
                </Card>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">No next steps were suggested.</p>
        )}
      </section>
    </div>
  );
}
