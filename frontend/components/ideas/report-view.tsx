"use client";

import { ExternalLink, RefreshCw } from "lucide-react";
import { cn } from "cn";
import { Button } from "@/components/ui/button";
import type { Metric, Report, RunStepName } from "@/lib/api/types";
import { formatDateTime, hostname, safeExternalUrl } from "@/lib/format";
import {
  ClaimBlock,
  ClaimList,
  CitationRef,
  ReportSourcesProvider,
  SectionPlaceholder,
} from "./claims";
import { Scorecard } from "./scorecard";

export type ReportTab =
  | "overview"
  | "market"
  | "competitors"
  | "customers"
  | "feasibility"
  | "business_model"
  | "sources";

export const REPORT_TABS: { id: ReportTab; label: string; step?: RunStepName }[] = [
  { id: "overview", label: "Overview" },
  { id: "market", label: "Market", step: "market" },
  { id: "competitors", label: "Competitors", step: "competitors" },
  { id: "customers", label: "Customers", step: "customers" },
  { id: "feasibility", label: "Feasibility", step: "feasibility" },
  { id: "business_model", label: "Business model", step: "business_model" },
  { id: "sources", label: "Sources" },
];

function MetricCard({ label, metric }: { label: string; metric: Metric | null | undefined }) {
  if (!metric) return null;
  return (
    <div className="rounded-card border border-line bg-surface p-4">
      <p className="t-meta">{label}</p>
      <p className="t-card mt-1 tabular-nums">
        {metric.value}
        <CitationRef urls={metric.source_urls ?? []} />
      </p>
      <p className="t-meta mt-1">Method: {metric.method}</p>
    </div>
  );
}

function SectionHeader({
  title,
  step,
  onRerun,
  rerunningStep,
}: {
  title: string;
  step?: RunStepName;
  onRerun?: (step: RunStepName) => void;
  rerunningStep?: RunStepName | null;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
      <h2 className="t-subsection">{title}</h2>
      {step && onRerun && (
        <Button
          variant="outline"
          size="sm"
          className="rounded-pill font-bold"
          onClick={() => onRerun(step)}
          disabled={rerunningStep != null}
          data-testid={`rerun-${step}`}
        >
          <RefreshCw
            size={14}
            className={cn(rerunningStep === step && "animate-spin")}
            aria-hidden="true"
          />
          {rerunningStep === step ? "Re-running…" : "Re-run section"}
        </Button>
      )}
    </div>
  );
}

export function ReportView({
  report,
  tab,
  onRerun,
  rerunningStep,
}: {
  report: Report;
  tab: ReportTab;
  onRerun?: (step: RunStepName) => void;
  rerunningStep?: RunStepName | null;
}) {
  const header = report.header;

  return (
    <ReportSourcesProvider sources={report.sources}>
      {tab === "overview" && (
        <div className="grid gap-8">
          <section aria-label="Verdict">
            <div className="flex flex-wrap items-center gap-4">
              <div className="rounded-card border border-line bg-surface px-6 py-4">
                <p className="t-meta">Verdict</p>
                <p className="t-subsection capitalize" data-testid="verdict">
                  {header.verdict ?? "Not scored"}
                </p>
                {header.verdict_confidence != null && (
                  <p className="t-meta">
                    Jev confidence {(header.verdict_confidence * 100).toFixed(0)}%
                  </p>
                )}
              </div>
              <div className="rounded-card border border-line bg-surface px-6 py-4">
                <p className="t-meta">Overall score</p>
                <p className="t-subsection tabular-nums" data-testid="overall-score">
                  {header.overall_score != null ? Math.round(header.overall_score * 10) / 10 : "—"}
                  <span className="t-meta"> /100</span>
                </p>
                {header.excluded_dimensions.length > 0 && (
                  <p className="t-meta">
                    {header.excluded_dimensions.length} dimension
                    {header.excluded_dimensions.length === 1 ? "" : "s"} excluded
                  </p>
                )}
              </div>
              <div className="rounded-card border border-line bg-surface px-6 py-4">
                <p className="t-meta">Run</p>
                <p className="t-body text-ink">
                  {formatDateTime(header.run_date ?? report.generated_at)}
                </p>
                <p className="t-meta">
                  Cost ${(header.cost_usd ?? 0).toFixed(2)}
                  {header.partial && " · partial"}
                </p>
              </div>
            </div>
          </section>

          <section aria-label="Scorecard">
            <h2 className="t-subsection mb-4">Scorecard</h2>
            <Scorecard dimensions={report.scorecard.dimensions} />
          </section>

          {report.brief && (
            <section aria-label="Polished brief">
              <h2 className="t-subsection mb-4">Polished idea</h2>
              <div className="grid gap-4 lg:grid-cols-2">
                <div className="rounded-card border border-line bg-surface p-5">
                  <h3 className="field__label">Problem</h3>
                  <p className="t-body mt-1">{report.brief.problem}</p>
                  <h3 className="field__label mt-4">Solution</h3>
                  <p className="t-body mt-1">{report.brief.solution}</p>
                  <h3 className="field__label mt-4">Target users</h3>
                  <p className="t-body mt-1">{report.brief.target_users}</p>
                  <h3 className="field__label mt-4">Value proposition</h3>
                  <p className="t-body mt-1">{report.brief.value_prop}</p>
                </div>
                <div className="rounded-card border border-line bg-surface p-5">
                  <h3 className="field__label">Key assumptions</h3>
                  <ul className="mt-2 list-disc space-y-2 ps-5">
                    {report.brief.key_assumptions.map((assumption) => (
                      <li key={assumption} className="t-body">
                        {assumption}
                      </li>
                    ))}
                  </ul>
                  {(report.brief.variants?.length ?? 0) > 0 && (
                    <>
                      <h3 className="field__label mt-5">Variants</h3>
                      <ul className="mt-2 grid gap-3">
                        {report.brief.variants?.map((variant) => (
                          <li key={variant.title} className="rounded-field border border-line p-3">
                            <p className="t-body font-bold text-ink">{variant.title}</p>
                            <p className="t-body">{variant.description}</p>
                          </li>
                        ))}
                      </ul>
                    </>
                  )}
                </div>
              </div>
            </section>
          )}

          {report.next_steps.length > 0 && (
            <section aria-label="Next steps">
              <h2 className="t-subsection mb-4">Next steps — cheapest tests first</h2>
              <ol className="grid gap-3 lg:grid-cols-3" data-testid="next-steps">
                {report.next_steps.map((step, index) => (
                  <li key={index} className="rounded-card border border-line bg-surface p-5">
                    <p className="t-meta">Assumption</p>
                    <p className="t-body font-bold text-ink">{step.assumption}</p>
                    <p className="t-meta mt-3">Cheap test</p>
                    <p className="t-body">{step.test}</p>
                    {step.risk && <span className="badge mt-3 inline-flex">risk: {step.risk}</span>}
                  </li>
                ))}
              </ol>
            </section>
          )}
        </div>
      )}

      {tab === "market" && (
        <section aria-label="Market">
          <SectionHeader
            title="Market"
            step="market"
            onRerun={onRerun}
            rerunningStep={rerunningStep}
          />
          {report.market ? (
            <div className="grid gap-6">
              <div className="grid gap-4 sm:grid-cols-3">
                <MetricCard label="TAM" metric={report.market.tam} />
                <MetricCard label="SAM" metric={report.market.sam} />
                <MetricCard label="SOM" metric={report.market.som} />
              </div>
              {report.market.trends.length > 0 && (
                <div>
                  <h3 className="field__label mb-2">Trends</h3>
                  <ClaimList claims={report.market.trends} />
                </div>
              )}
              {report.market.timing_why_now && (
                <div>
                  <h3 className="field__label mb-2">Why now</h3>
                  <ClaimBlock claim={report.market.timing_why_now} />
                </div>
              )}
            </div>
          ) : (
            <SectionPlaceholder label="market" />
          )}
        </section>
      )}

      {tab === "competitors" && (
        <section aria-label="Competitors">
          <SectionHeader
            title="Competitors"
            step="competitors"
            onRerun={onRerun}
            rerunningStep={rerunningStep}
          />
          {report.competitors ? (
            <div className="grid gap-6">
              <ul className="grid gap-3" data-testid="competitor-list">
                {report.competitors.competitors.map((competitor) => {
                  const competitorUrl = safeExternalUrl(competitor.url);
                  return (
                    <li
                      key={competitor.name}
                      className="rounded-card border border-line bg-surface p-5"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="t-card">{competitor.name}</h3>
                        {competitorUrl && (
                          <a
                            href={competitorUrl}
                            target="_blank"
                            rel="noreferrer noopener"
                            className="link t-meta inline-flex items-center gap-1"
                          >
                            {hostname(competitorUrl)}
                            <ExternalLink size={12} aria-hidden="true" />
                          </a>
                        )}
                        {competitor.verified === false && (
                          <span className="badge border-dashed text-ink-muted">unverified</span>
                        )}
                      </div>
                      <div className="mt-2 grid gap-2 sm:grid-cols-3">
                        <div>
                          <p className="t-meta">Positioning</p>
                          <p className="t-body">{competitor.positioning}</p>
                        </div>
                        <div>
                          <p className="t-meta">Pricing</p>
                          <p className="t-body">{competitor.pricing ?? "—"}</p>
                        </div>
                        <div>
                          <p className="t-meta">Gap</p>
                          <p className="t-body">{competitor.gap ?? "—"}</p>
                        </div>
                      </div>
                      {competitor.source_urls && competitor.source_urls.length > 0 && (
                        <p className="t-meta mt-2">
                          Sources <CitationRef urls={competitor.source_urls} />
                        </p>
                      )}
                    </li>
                  );
                })}
              </ul>
              {report.competitors.differentiation && (
                <div>
                  <h3 className="field__label mb-2">Differentiation</h3>
                  <ClaimBlock claim={report.competitors.differentiation} />
                </div>
              )}
            </div>
          ) : (
            <SectionPlaceholder label="competitors" />
          )}
        </section>
      )}

      {tab === "customers" && (
        <section aria-label="Customers">
          <SectionHeader
            title="Customers"
            step="customers"
            onRerun={onRerun}
            rerunningStep={rerunningStep}
          />
          {report.customers ? (
            <div className="grid gap-8">
              <div className="grid gap-4 lg:grid-cols-2">
                <div>
                  <h3 className="field__label mb-2">Personas</h3>
                  <ul className="grid gap-3" data-testid="persona-list">
                    {report.customers.personas.map((persona) => (
                      <li
                        key={persona.name}
                        className="rounded-card border border-line bg-surface p-4"
                      >
                        <p className="t-body font-bold text-ink">{persona.name}</p>
                        <p className="t-body">
                          {persona.description}
                          <CitationRef urls={persona.source_urls ?? []} />
                        </p>
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h3 className="field__label mb-2">Where they gather</h3>
                  <ul className="grid gap-3">
                    {report.customers.communities.map((community) => (
                      <li
                        key={community.name}
                        className="rounded-card border border-line bg-surface p-4"
                      >
                        <a
                          href={safeExternalUrl(community.url) ?? "#"}
                          target="_blank"
                          rel="noreferrer noopener"
                          className="link t-body font-bold text-ink"
                        >
                          {community.name}
                        </a>
                        {community.description && <p className="t-meta">{community.description}</p>}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {report.customers.pain_quotes.length > 0 && (
                <div>
                  <h3 className="field__label mb-2">Pain in their own words</h3>
                  <ul className="grid gap-3 lg:grid-cols-3" data-testid="pain-quotes">
                    {report.customers.pain_quotes.map((quote, index) => (
                      <li
                        key={index}
                        className="rounded-card border border-line bg-surface-subtle p-4"
                      >
                        <blockquote className="t-body text-ink">“{quote.text}”</blockquote>
                        {safeExternalUrl(quote.url) && (
                          <a
                            href={safeExternalUrl(quote.url)}
                            target="_blank"
                            rel="noreferrer noopener"
                            className="link t-meta mt-2 inline-block"
                          >
                            original post
                          </a>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {report.customers.early_adopter_profile && (
                <div>
                  <h3 className="field__label mb-2">Early adopter profile</h3>
                  <ClaimBlock claim={report.customers.early_adopter_profile} />
                </div>
              )}

              {(report.customers.leads?.length ?? 0) > 0 && (
                <div>
                  <h3 className="field__label mb-2">Target companies</h3>
                  <p className="t-meta mb-2">
                    Company-level only — no personal contact data is stored.
                  </p>
                  <ul className="grid gap-3 sm:grid-cols-2">
                    {report.customers.leads?.map((lead) => (
                      <li
                        key={lead.domain}
                        className="rounded-card border border-line bg-surface p-4"
                      >
                        <p className="t-body font-bold text-ink">{lead.name}</p>
                        <p className="t-meta">
                          {[lead.industry, lead.size_band, lead.country]
                            .filter(Boolean)
                            .join(" · ")}
                        </p>
                        <p className="t-body mt-1">{lead.why_fit}</p>
                        {safeExternalUrl(lead.url) && (
                          <a
                            href={safeExternalUrl(lead.url)}
                            target="_blank"
                            rel="noreferrer noopener"
                            className="link t-meta mt-1 inline-block"
                          >
                            {lead.domain}
                          </a>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : (
            <SectionPlaceholder label="customers" />
          )}
        </section>
      )}

      {tab === "feasibility" && (
        <section aria-label="Feasibility">
          <SectionHeader
            title="Feasibility"
            step="feasibility"
            onRerun={onRerun}
            rerunningStep={rerunningStep}
          />
          {report.feasibility ? (
            <div className="grid gap-6">
              <div className="grid gap-4 lg:grid-cols-2">
                {(
                  [
                    ["Technical", report.feasibility.technical],
                    ["Operational", report.feasibility.operational],
                    ["Legal & regulatory", report.feasibility.legal_regulatory],
                    ["MVP cost range", report.feasibility.mvp_cost_range],
                    ["MVP timeline", report.feasibility.mvp_timeline],
                  ] as const
                ).map(([label, claim]) =>
                  claim ? (
                    <div key={label} className="rounded-card border border-line bg-surface p-4">
                      <p className="t-meta">{label}</p>
                      <ClaimBlock claim={claim} className="mt-1" />
                    </div>
                  ) : null,
                )}
              </div>
              {report.feasibility.risks.length > 0 && (
                <div>
                  <h3 className="field__label mb-2">Risks</h3>
                  <div className="overflow-x-auto rounded-card border border-line">
                    <table className="w-full border-collapse text-left" data-testid="risk-table">
                      <thead>
                        <tr className="border-b border-line bg-surface-subtle">
                          <th scope="col" className="p-3 text-sm font-bold">
                            Risk
                          </th>
                          <th scope="col" className="p-3 text-sm font-bold">
                            Likelihood
                          </th>
                          <th scope="col" className="p-3 text-sm font-bold">
                            Impact
                          </th>
                          <th scope="col" className="p-3 text-sm font-bold">
                            Mitigation
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {report.feasibility.risks.map((risk) => (
                          <tr key={risk.risk} className="border-b border-line last:border-b-0">
                            <td className="p-3 text-sm text-ink-secondary">{risk.risk}</td>
                            <td className="p-3 text-sm capitalize">{risk.likelihood}</td>
                            <td className="p-3 text-sm capitalize">{risk.impact}</td>
                            <td className="p-3 text-sm text-ink-secondary">{risk.mitigation}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <SectionPlaceholder label="feasibility" />
          )}
        </section>
      )}

      {tab === "business_model" && (
        <section aria-label="Business model">
          <SectionHeader
            title="Business model"
            step="business_model"
            onRerun={onRerun}
            rerunningStep={rerunningStep}
          />
          {report.business_model ? (
            <div className="grid gap-6">
              {report.business_model.lean_canvas && (
                <div>
                  <h3 className="field__label mb-2">Lean canvas</h3>
                  <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {Object.entries(report.business_model.lean_canvas)
                      .filter(([, value]) => Boolean(value))
                      .map(([key, value]) => (
                        <div key={key} className="rounded-card border border-line bg-surface p-4">
                          <dt className="t-meta capitalize">{key.replaceAll("_", " ")}</dt>
                          <dd className="t-body mt-1">{value}</dd>
                        </div>
                      ))}
                  </dl>
                </div>
              )}
              {report.business_model.revenue_streams.length > 0 && (
                <div>
                  <h3 className="field__label mb-2">Revenue streams</h3>
                  <ClaimList claims={report.business_model.revenue_streams} />
                </div>
              )}
              {report.business_model.pricing_options.length > 0 && (
                <div>
                  <h3 className="field__label mb-2">Pricing</h3>
                  <ul className="grid gap-3 sm:grid-cols-3">
                    {report.business_model.pricing_options.map((option) => (
                      <li
                        key={option.name}
                        className="rounded-card border border-line bg-surface p-4"
                      >
                        <p className="t-body font-bold text-ink">{option.name}</p>
                        <p className="t-card tabular-nums">{option.price}</p>
                        {option.notes && <p className="t-meta">{option.notes}</p>}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {report.business_model.unit_economics && (
                <div>
                  <h3 className="field__label mb-2">Unit economics (estimates)</h3>
                  <div className="grid gap-4 sm:grid-cols-2">
                    {report.business_model.unit_economics.cac && (
                      <div className="rounded-card border border-line bg-surface p-4">
                        <p className="t-meta">CAC</p>
                        <ClaimBlock
                          claim={report.business_model.unit_economics.cac}
                          className="mt-1"
                        />
                      </div>
                    )}
                    {report.business_model.unit_economics.ltv && (
                      <div className="rounded-card border border-line bg-surface p-4">
                        <p className="t-meta">LTV</p>
                        <ClaimBlock
                          claim={report.business_model.unit_economics.ltv}
                          className="mt-1"
                        />
                      </div>
                    )}
                  </div>
                  <ul className="mt-3 list-disc space-y-1 ps-5">
                    {report.business_model.unit_economics.assumptions.map((assumption) => (
                      <li key={assumption} className="t-meta">
                        {assumption}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {report.business_model.go_to_market.length > 0 && (
                <div>
                  <h3 className="field__label mb-2">Go to market</h3>
                  <ClaimList claims={report.business_model.go_to_market} />
                </div>
              )}
            </div>
          ) : (
            <SectionPlaceholder label="business model" />
          )}
        </section>
      )}

      {tab === "sources" && (
        <section aria-label="Sources">
          <h2 className="t-subsection mb-4">Sources</h2>
          {report.sources.length === 0 ? (
            <p className="t-body">No sources were collected for this run.</p>
          ) : (
            <ol className="grid gap-2" data-testid="sources-list">
              {report.sources.map((source) => (
                <li
                  key={source.number}
                  className="flex gap-3 border-b border-line py-3 last:border-b-0"
                >
                  <span className="t-meta tabular-nums">[{source.number}]</span>
                  {safeExternalUrl(source.url) ? (
                    <a
                      href={safeExternalUrl(source.url)}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="link t-body"
                    >
                      {source.title}
                    </a>
                  ) : (
                    <span className="t-body">{source.title}</span>
                  )}
                </li>
              ))}
            </ol>
          )}
        </section>
      )}
    </ReportSourcesProvider>
  );
}
