"use client";

import { OverviewTab } from "@/components/idea-detail/overview-tab";
import { SectionPanel } from "@/components/idea-detail/section-panel";
import { SourcesTab } from "@/components/idea-detail/sources-tab";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useRerunStep } from "@/lib/api/queries";
import type { Report, ReportSection, RunRead } from "@/lib/api/types";
import type { PipelineStep } from "@/lib/progress";

export const REPORT_TABS = [
  { value: "overview", label: "Overview" },
  { value: "market", label: "Market" },
  { value: "competitors", label: "Competitors" },
  { value: "customers", label: "Customers" },
  { value: "feasibility", label: "Feasibility" },
  { value: "business_model", label: "Business model" },
  { value: "sources", label: "Sources" },
] as const;

const SECTION_TABS: ReportSection["name"][] = [
  "market",
  "competitors",
  "customers",
  "feasibility",
  "business_model",
];

export interface ReportTabsProps {
  report: Report;
  /** Latest run, used for the per-section Re-run action. */
  run: RunRead | null;
}

/** Report tabs: Overview · sections · Sources, with per-section re-runs. */
export function ReportTabs({ report, run }: ReportTabsProps) {
  const rerun = useRerunStep(run?.id ?? "");
  const canRerun = run !== null && (run.status === "done" || run.status === "partial");
  const sectionByName = new Map((report.sections ?? []).map((section) => [section.name, section]));

  function handleRerun(step: PipelineStep) {
    if (!run) return;
    rerun.mutate(step);
  }

  return (
    <Tabs defaultValue="overview" className="w-full">
      <div className="-mx-1 overflow-x-auto px-1 pb-1">
        <TabsList className="w-max justify-start">
          {REPORT_TABS.map((tab) => (
            <TabsTrigger key={tab.value} value={tab.value}>
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </div>
      <TabsContent value="overview">
        <OverviewTab report={report} />
      </TabsContent>
      {SECTION_TABS.map((name) => (
        <TabsContent key={name} value={name}>
          <SectionPanel
            section={sectionByName.get(name) ?? null}
            sectionName={name}
            sources={report.sources ?? []}
            canRerun={canRerun}
            rerunPending={rerun.isPending}
            onRerun={handleRerun}
          />
        </TabsContent>
      ))}
      <TabsContent value="sources">
        <SourcesTab sources={report.sources ?? []} />
      </TabsContent>
    </Tabs>
  );
}
