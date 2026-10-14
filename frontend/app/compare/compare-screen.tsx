"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import type { Route } from "next";
import { Button } from "@/components/ui/button";
import { ScoreBadge, StatusBadge, VerdictBadge } from "@/components/ideas/badges";
import { useCompare } from "@/lib/api/hooks";
import type { CompareItem, DimensionId, Report } from "@/lib/api/types";
import { CATEGORY_LABELS } from "@/lib/labels";
import { formatCost } from "@/lib/format";
import { cn } from "cn";

type Row = {
  label: string;
  render: (item: CompareItem) => React.ReactNode;
};

function dimension(report: Report | null | undefined, id: DimensionId) {
  if (!report) return null;
  return report.scorecard.dimensions.find((entry) => entry.id === id) ?? null;
}

function firstRisk(report: Report | null | undefined): string | null {
  return report?.feasibility?.risks?.[0]?.risk ?? null;
}

const ROWS: Row[] = [
  {
    label: "Verdict",
    render: (item) => <VerdictBadge verdict={item.idea.verdict} />,
  },
  {
    label: "Overall score",
    render: (item) => (
      <span className="t-body font-bold text-ink tabular-nums">
        {item.report?.header.overall_score != null
          ? `${Math.round(item.report.header.overall_score * 10) / 10}/100`
          : "—"}
      </span>
    ),
  },
  {
    label: "Problem severity",
    render: (item) => {
      const value = dimension(item.report, "problem_severity");
      return value && !value.not_scored ? (
        <ScoreBadge score={value.score} confidence={value.confidence} />
      ) : (
        <span className="t-meta">—</span>
      );
    },
  },
  {
    label: "Market evidence",
    render: (item) => {
      const value = dimension(item.report, "market_evidence");
      return value && !value.not_scored ? (
        <ScoreBadge score={value.score} confidence={value.confidence} />
      ) : (
        <span className="t-meta">—</span>
      );
    },
  },
  {
    label: "Competition (higher is easier)",
    render: (item) => {
      const value = dimension(item.report, "competition_intensity");
      return value && !value.not_scored ? (
        <ScoreBadge score={value.score} confidence={value.confidence} />
      ) : (
        <span className="t-meta">—</span>
      );
    },
  },
  {
    label: "Customer reachability",
    render: (item) => {
      const value = dimension(item.report, "customer_reachability");
      return value && !value.not_scored ? (
        <ScoreBadge score={value.score} confidence={value.confidence} />
      ) : (
        <span className="t-meta">—</span>
      );
    },
  },
  {
    label: "Feasibility",
    render: (item) => {
      const value = dimension(item.report, "feasibility");
      return value && !value.not_scored ? (
        <ScoreBadge score={value.score} confidence={value.confidence} />
      ) : (
        <span className="t-meta">—</span>
      );
    },
  },
  {
    label: "Monetization clarity",
    render: (item) => {
      const value = dimension(item.report, "monetization_clarity");
      return value && !value.not_scored ? (
        <ScoreBadge score={value.score} confidence={value.confidence} />
      ) : (
        <span className="t-meta">—</span>
      );
    },
  },
  {
    label: "TAM",
    render: (item) => <span className="t-body">{item.report?.market?.tam?.value ?? "—"}</span>,
  },
  {
    label: "MVP cost",
    render: (item) => (
      <span className="t-body">{item.report?.feasibility?.mvp_cost_range?.text ?? "—"}</span>
    ),
  },
  {
    label: "MVP timeline",
    render: (item) => (
      <span className="t-body">{item.report?.feasibility?.mvp_timeline?.text ?? "—"}</span>
    ),
  },
  {
    label: "Biggest risk",
    render: (item) => <span className="t-body">{firstRisk(item.report) ?? "—"}</span>,
  },
  {
    label: "First pricing option",
    render: (item) => {
      const pricing = item.report?.business_model?.pricing_options?.[0];
      return <span className="t-body">{pricing ? `${pricing.name} · ${pricing.price}` : "—"}</span>;
    },
  },
  {
    label: "Run cost",
    render: (item) => (
      <span className="t-body tabular-nums">{formatCost(item.report?.cost_usd)}</span>
    ),
  },
];

export function CompareScreen() {
  const searchParams = useSearchParams();
  const ids = (searchParams.get("ids") ?? "").split(",").filter(Boolean).slice(0, 3);
  const valid = ids.length >= 2 && ids.length <= 3;
  const query = useCompare(valid ? ids : []);

  if (!valid) {
    return (
      <div className="container--reading container pt-[calc(var(--header-offset)+var(--space-8))] pb-24">
        <h1 className="t-section">Compare ideas</h1>
        <p className="t-body mt-3">
          Pick two or three ideas in the library to see their scorecards and key findings side by
          side.
        </p>
        <Button asChild className="mt-6 rounded-pill font-bold">
          <Link href="/ideas">Go to the library</Link>
        </Button>
      </div>
    );
  }

  if (query.isPending) {
    return (
      <div
        className="container pt-[calc(var(--header-offset)+var(--space-8))] pb-24"
        aria-busy="true"
      >
        <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="t-section">Compare</h1>
            <p className="t-meta mt-1">{valid ? `${ids.length} ideas side by side` : ""}</p>
          </div>
          <Button asChild variant="outline" className="rounded-pill font-bold">
            <Link href="/ideas">Back to library</Link>
          </Button>
        </div>
        <div className="grid gap-x-6 lg:grid-cols-[200px_1fr_1fr]">
          <div className="hidden lg:block" />
          {ids.slice(0, 3).map((id) => (
            <div key={id} className="h-40 animate-pulse rounded-card bg-surface-subtle" />
          ))}
          <div className="h-96 animate-pulse rounded-card bg-surface-subtle lg:col-span-3" />
        </div>
      </div>
    );
  }

  if (query.isError || !query.data) {
    return (
      <div className="container--reading container pt-[calc(var(--header-offset)+var(--space-8))] pb-24">
        <h1 className="t-section">Compare ideas</h1>
        <p className="t-body mt-3" role="alert">
          Could not load the comparison. Check the selection and try again.
        </p>
        <Button className="mt-6 rounded-pill font-bold" onClick={() => void query.refetch()}>
          Retry
        </Button>
      </div>
    );
  }

  const items = query.data.items;
  const columns =
    items.length === 2 ? "lg:grid-cols-[200px_1fr_1fr]" : "lg:grid-cols-[200px_1fr_1fr_1fr]";

  return (
    <div
      className="container pt-[calc(var(--header-offset)+var(--space-8))] pb-24"
      data-testid="compare-screen"
    >
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="t-section">Compare</h1>
          <p className="t-meta mt-1">{items.length} ideas side by side</p>
        </div>
        <Button asChild variant="outline" className="rounded-pill font-bold">
          <Link href="/ideas">Back to library</Link>
        </Button>
      </div>

      <div className="overflow-x-auto">
        <div className={cn("grid min-w-0 gap-x-6", columns)}>
          <div className="hidden lg:block" />
          {items.map((item) => (
            <div key={item.idea.id} className="rounded-card border border-line bg-surface p-5">
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge status={item.idea.status} />
                {item.idea.category && (
                  <span className="badge">
                    {CATEGORY_LABELS[item.idea.category] ?? item.idea.category}
                  </span>
                )}
              </div>
              <h2 className="t-card mt-2">
                <Link
                  href={`/ideas/${item.idea.id}` as Route}
                  className="link decoration-2 hover:decoration-4"
                >
                  {item.idea.title}
                </Link>
              </h2>
              {item.idea.one_liner && (
                <p className="t-body mt-1 line-clamp-3">{item.idea.one_liner}</p>
              )}
              {!item.report && (
                <p className="t-meta mt-2 text-ink-muted">
                  {item.error ?? "No completed report for this idea yet."}
                </p>
              )}
            </div>
          ))}

          {ROWS.map((row, index) => (
            <div
              key={row.label}
              className={cn(
                "contents",
                index % 2 === 0 ? "[&>div]:bg-canvas" : "[&>div]:bg-surface",
              )}
            >
              <div className="border-b border-line py-3 pe-4 text-sm font-bold text-ink lg:py-4">
                {row.label}
              </div>
              {items.map((item) => (
                <div
                  key={`${item.idea.id}-${row.label}`}
                  className="flex flex-col gap-1 border-b border-line py-3 lg:py-4"
                >
                  <span className="t-meta lg:hidden">{item.idea.title}</span>
                  {item.report ? row.render(item) : <span className="t-meta">—</span>}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
