import type {
  Claim,
  ClarifyingQuestion,
  CompanyLead,
  DimensionId,
  DimensionScore,
  Idea,
  IdeaBrief,
  IdeaDetail,
  IdeaList,
  MarketSection,
  BusinessModelSection,
  CompetitorSection,
  CustomerSection,
  FeasibilitySection,
  NextStep,
  Report,
  Run,
  RunEvent,
  RunStep,
  RunStepName,
  Source,
  Verdict,
} from "@/lib/api/types";

/* ------------------------------------------------------------------ *
 * Deterministic randomness — no Math.random, no Date.now at module
 * scope, so the same dataset appears in every session and snapshot.
 * ------------------------------------------------------------------ */

export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function pick<T>(rand: () => number, items: readonly T[]): T {
  return items[Math.floor(rand() * items.length) % items.length];
}

export const BASE_TIME = Date.parse("2026-10-01T09:00:00.000Z");

export function minutesAfter(base: number, minutes: number): string {
  return new Date(base + minutes * 60_000).toISOString();
}

export function uuidFor(index: number): string {
  const head = (0x10000000 + index).toString(16).padStart(8, "0");
  return `${head}-0000-4000-8000-000000000000`;
}

export const FIXED_IDS = {
  dogWalking: "00000000-0000-4000-8000-000000000001",
  invoiceAi: "00000000-0000-4000-8000-000000000002",
  awaitingInput: "00000000-0000-4000-8000-000000000003",
  partialRun: "00000000-0000-4000-8000-000000000004",
} as const;

/* ------------------------------------------------------------------ *
 * Vocabulary pools
 * ------------------------------------------------------------------ */

export const CATEGORIES = [
  "b2b_saas",
  "b2c_app",
  "marketplace",
  "hardware",
  "service",
  "content",
  "fintech",
  "health",
  "other",
] as const;

export const TAG_POOL = [
  "ai",
  "saas",
  "marketplace",
  "healthcare",
  "fintech",
  "productivity",
  "sustainability",
  "education",
  "logistics",
  "community",
  "mobile",
  "b2b",
] as const;

const SUBJECTS = [
  "Dog walking",
  "Invoice reconciliation",
  "Meal planning",
  "Fleet maintenance",
  "Therapy scheduling",
  "Budget tracking",
  "Grocery delivery",
  "Code review",
  "Language tutoring",
  "Plant care",
  "Coworking booking",
  "Payroll",
  "Interview prep",
  "Prescription delivery",
  "Home cleaning",
  "Car repair",
  "Event planning",
  "Gift curation",
  "Sleep tracking",
  "Personal training",
  "Legal documents",
  "Tax filing",
  "Recruiting",
  "Customer support",
  "Expense reports",
  "Warehouse picking",
  "Farm supply",
  "Church management",
  "Yoga studios",
  "Music lessons",
  "Photography booking",
  "Freelance invoicing",
  "Construction bidding",
  "Restaurant inventory",
  "Truck routing",
  "Elder care",
  "Childcare",
  "Pet insurance",
  "Travel planning",
  "Local news",
] as const;

const AUDIENCES = [
  "for freelancers",
  "for small clinics",
  "for busy parents",
  "for trucking companies",
  "for independent shops",
  "for nonprofits",
  "for landlords",
  "for restaurants",
  "for developers",
  "for students",
  "for elderly care homes",
  "for gyms",
  "for law firms",
  "for farmers",
  "for remote teams",
  "for pet owners",
  "for local governments",
  "for hotels",
  "for pharmacies",
  "for construction crews",
  "for tutors",
  "for accountants",
  "for event planners",
  "for coffee shops",
  "for warehouses",
] as const;

const PROBLEMS = [
  "Most teams still run this on spreadsheets and group chats, so work slips through the cracks and nobody can see the full picture.",
  "The pain is real and recurring: it costs people hours every week and they complain about it in public forums constantly.",
  "Current tools are either enterprise-priced or too generic to fit the workflow, forcing people into manual workarounds.",
  "Demand is growing faster than the services can absorb, and the existing options are fragmented across channels.",
] as const;

const SOLUTIONS = [
  "A focused workflow tool that replaces the spreadsheets, automates the repetitive parts, and keeps everyone on one shared timeline.",
  "A lightweight marketplace that matches supply and demand in real time with transparent pricing and trust signals.",
  "An AI-assisted assistant that handles the busywork end to end and escalates only the exceptions to a human.",
  "A vertical SaaS built around the real workflow, with sensible defaults and integrations with the tools people already use.",
] as const;

const VALUE_PROPS = [
  "Cut weekly admin time by half in the first month.",
  "Fewer no-shows, fewer missed handoffs, and a single source of truth.",
  "Launch in days, not months, with no consultants required.",
  "Pay only when the work gets done.",
] as const;

const ASSUMPTIONS = [
  "Users will adopt a new tool if setup takes less than ten minutes.",
  "The willingness to pay is at least $29 per seat per month.",
  "Supply-side acquisition can be done through existing communities rather than paid ads.",
  "An AI-first workflow can replace two hours of manual coordination per day.",
  "Buyers care more about scheduling reliability than about the lowest price.",
] as const;

const SOURCE_SITES = [
  {
    url: "https://www.statista.com/outlook/digital-markets",
    title: "Statista — Digital market outlook",
  },
  {
    url: "https://www.grandviewresearch.com/industry-analysis",
    title: "Grand View Research — Industry analysis",
  },
  {
    url: "https://news.ycombinator.com/item?id=39000001",
    title: "Hacker News — Ask HN discussion",
  },
  {
    url: "https://www.reddit.com/r/smallbusiness/comments/pain-points/",
    title: "r/smallbusiness — recurring pain points",
  },
  {
    url: "https://www.reddit.com/r/Entrepreneur/comments/validation/",
    title: "r/Entrepreneur — validating a niche tool",
  },
  { url: "https://www.gartner.com/en/newsroom", title: "Gartner — market press release" },
  { url: "https://www.crunchbase.com/hub", title: "Crunchbase — funding activity" },
  { url: "https://www.nber.org/papers", title: "NBER — working paper" },
  { url: "https://www.mckinsey.com/featured-insights", title: "McKinsey — featured insights" },
  { url: "https://stackoverflow.blog/", title: "Stack Overflow — developer survey notes" },
] as const;

export function makeSource(rand: () => number): Source & { claimText: string } {
  const site = pick(rand, SOURCE_SITES);
  return { number: 0, url: site.url, title: site.title, claimText: site.title };
}

function claim(rand: () => number, text: string, urlCount = 1): Claim {
  const urls: string[] = [];
  const used = new Set<number>();
  for (let i = 0; i < urlCount; i += 1) {
    let idx = Math.floor(rand() * SOURCE_SITES.length);
    while (used.has(idx)) idx = (idx + 1) % SOURCE_SITES.length;
    used.add(idx);
    urls.push(SOURCE_SITES[idx].url);
  }
  const confidence = 0.45 + rand() * 0.5;
  return {
    text,
    source_urls: urls,
    verified: rand() > 0.18,
    confidence: Math.round(confidence * 100) / 100,
  };
}

/* ------------------------------------------------------------------ *
 * Idea + brief builders
 * ------------------------------------------------------------------ */

export function buildBrief(rand: () => number, title: string): IdeaBrief {
  return {
    title,
    one_liner: `${title} — ${pick(rand, VALUE_PROPS).toLowerCase()}`,
    problem: pick(rand, PROBLEMS),
    solution: pick(rand, SOLUTIONS),
    target_users: `Operators and owners who feel ${title.toLowerCase()} pain weekly and currently juggle two or three disconnected tools.`,
    value_prop: pick(rand, VALUE_PROPS),
    key_assumptions: [...ASSUMPTIONS].sort(() => rand() - 0.5).slice(0, 4),
    variants: [
      {
        title: "Narrow wedge: one workflow, done perfectly",
        description: `Start with the single highest-frequency ${pick(rand, ["scheduling", "tracking", "matching", "reporting"])} task and expand once retention holds.`,
      },
      {
        title: "Services-first, software later",
        description:
          "Run the operation manually for ten customers to learn the job to be done, then automate the repeatable parts.",
      },
    ],
  };
}

export function titleFor(index: number): string {
  const subject = SUBJECTS[index % SUBJECTS.length];
  const audience = AUDIENCES[Math.floor(index / SUBJECTS.length) % AUDIENCES.length];
  return `${subject} ${audience}`;
}

export function rawInputFor(title: string, index: number): string {
  return `I keep noticing that ${title.toLowerCase()} is stuck in the dark ages — people coordinate over text messages and paper, and things fall through the cracks. I want to build a simple tool that fixes the scheduling and the follow-ups, charges a monthly subscription, and starts with one city. (mock idea #${index + 1})`;
}

/* ------------------------------------------------------------------ *
 * Report builders
 * ------------------------------------------------------------------ */

const DIMENSIONS: { id: DimensionId; label: string }[] = [
  { id: "problem_severity", label: "Problem severity" },
  { id: "market_evidence", label: "Market evidence" },
  { id: "competition_intensity", label: "Competition intensity" },
  { id: "customer_reachability", label: "Customer reachability" },
  { id: "feasibility", label: "Feasibility" },
  { id: "monetization_clarity", label: "Monetization clarity" },
];

export function buildScorecard(rand: () => number, opts?: { exclude?: DimensionId[] }) {
  const exclude = new Set(opts?.exclude ?? []);
  const dimensions: DimensionScore[] = DIMENSIONS.map((dim) => {
    if (exclude.has(dim.id)) {
      return {
        ...dim,
        score: null,
        confidence: null,
        needs_review: false,
        not_scored: true,
        rationale: null,
      };
    }
    const score = 2 + Math.floor(rand() * 4);
    const confidence = Math.round((0.5 + rand() * 0.48) * 100) / 100;
    return {
      ...dim,
      score,
      confidence,
      needs_review: confidence < 0.6,
      not_scored: false,
      rationale: `${dim.label} scored ${score}/5 — ${pick(rand, [
        "evidence is consistent across three independent sources",
        "the signal comes mostly from community posts and needs more validation",
        "competitors validate the demand but pricing pressure is real",
        "a clear wedge exists if the first segment is chosen carefully",
      ])}.`,
    };
  });
  const scored = dimensions.filter((d) => !d.not_scored && d.score != null);
  const weights: Record<DimensionId, number> = {
    problem_severity: 0.22,
    market_evidence: 0.2,
    competition_intensity: 0.14,
    customer_reachability: 0.16,
    feasibility: 0.16,
    monetization_clarity: 0.12,
  };
  let weightSum = 0;
  let total = 0;
  for (const d of scored) {
    const value = d.id === "competition_intensity" ? 6 - (d.score ?? 3) : (d.score ?? 3);
    const w = weights[d.id];
    weightSum += w;
    total += value * w;
  }
  const overall = weightSum > 0 ? Math.round(((total / weightSum - 1) / 4) * 1000) / 10 : null;
  return { dimensions, overall, excluded: [...exclude] };
}

export function verdictFor(overall: number | null): Verdict {
  if (overall == null) return "refine";
  if (overall >= 68) return "pursue";
  if (overall >= 48) return "refine";
  return "park";
}

export function buildMarket(rand: () => number, title: string): MarketSection {
  const billion = Math.round((0.4 + rand() * 7) * 10) / 10;
  const sam = Math.round((80 + rand() * 900) * 10) / 10;
  const som = Math.round((4 + rand() * 40) * 10) / 10;
  return {
    tam: {
      value: `$${billion}B`,
      method: pick(rand, [
        "top-down from industry reports",
        "bottom-up from buyer counts × annual spend",
      ]),
      source_urls: [SOURCE_SITES[0].url, SOURCE_SITES[1].url],
      verified: true,
    },
    sam: {
      value: `$${sam}M`,
      method: "filtered to the beachhead segment described in the brief",
      source_urls: [SOURCE_SITES[1].url],
      verified: true,
    },
    som: {
      value: `$${som}M`,
      method: "3-year obtainable share at 2-4% of the serviceable segment",
      source_urls: [SOURCE_SITES[2].url],
      verified: rand() > 0.3,
    },
    trends: [
      claim(rand, `${title} demand is shifting from phone and paper to mobile-first booking.`, 2),
      claim(rand, "Incumbents are consolidating, leaving a gap for focused vertical tools.", 1),
    ],
    timing_why_now: claim(
      rand,
      "AI drops the cost of the coordination layer by an order of magnitude, which makes this niche profitable now.",
      2,
    ),
  };
}

export function buildCompetitors(rand: () => number, title: string): CompetitorSection {
  const names = [
    "GorillaDesk",
    "Jobber",
    "Housecall Pro",
    "Calendly",
    "ServiceTitan",
    "Acuity",
    "Workiz",
  ];
  const count = 3 + Math.floor(rand() * 3);
  const competitors = names.slice(0, count).map((name) => ({
    name,
    url: `https://www.${name.toLowerCase().replace(/\s+/g, "")}.com`,
    positioning: pick(rand, [
      "Broad horizontal suite; not tuned for this niche",
      "Strong brand in services, weak on automation",
      "Cheap and simple, but no follow-up workflow",
      "Enterprise pricing excludes small operators",
    ]),
    pricing: pick(rand, [
      "$49-$199 / month",
      "$29 / seat / month",
      "Free + 2.9% transaction fee",
      "Custom pricing",
    ]),
    gap: pick(rand, [
      "No AI-assisted scheduling",
      `Does not serve ${title.toLowerCase()} workflows`,
      "Onboarding takes weeks",
      "No community or trust layer",
    ]),
    source_urls: [SOURCE_SITES[3].url],
    verified: rand() > 0.25,
  }));
  return {
    competitors,
    differentiation: claim(
      rand,
      "Wedge: own the follow-up loop nobody automates, then expand into scheduling and payments.",
      2,
    ),
  };
}

export function buildCustomers(rand: () => number, title: string): CustomerSection {
  const communities = [
    {
      name: "r/smallbusiness",
      url: "https://www.reddit.com/r/smallbusiness/",
      description: "Owners comparing tools",
    },
    {
      name: "r/Entrepreneur",
      url: "https://www.reddit.com/r/Entrepreneur/",
      description: "Validation and GTM threads",
    },
    {
      name: "Indie Hackers",
      url: "https://www.indiehackers.com/",
      description: "Builders sharing revenue numbers",
    },
    {
      name: "Hacker News",
      url: "https://news.ycombinator.com/",
      description: "Tooling discussions",
    },
  ];
  const leads: CompanyLead[] = [
    {
      name: "Bright Path Services",
      domain: "brightpathservices.com",
      industry: "Home services",
      size_band: "11-50",
      country: "United States",
      why_fit: `Public job postings show a coordinator role dedicated to ${title.toLowerCase()} admin.`,
      url: "https://brightpathservices.com",
    },
    {
      name: "Northline Collective",
      domain: "northline.co",
      industry: "Local marketplace",
      size_band: "1-10",
      country: "United Kingdom",
      why_fit: "Reviews mention slow follow-ups; the team is small and tool-friendly.",
      url: "https://northline.co",
    },
  ];
  return {
    personas: [
      {
        name: "Maya, the operator",
        description:
          "Runs day-to-day ops for a 15-person team; spends 2+ hours a day on scheduling and follow-ups.",
        source_urls: [SOURCE_SITES[3].url],
        verified: true,
      },
      {
        name: "Sam, the owner",
        description:
          "Cares about margin and reliability; will pay for anything that removes churn.",
        source_urls: [SOURCE_SITES[4].url],
        verified: rand() > 0.4,
      },
    ],
    communities,
    pain_quotes: [
      {
        text: "We still coordinate everything over WhatsApp and it is chaos. Somebody always drops the ball.",
        url: "https://www.reddit.com/r/smallbusiness/comments/pain-points/",
      },
      {
        text: "I would pay $50/month tomorrow if it just handled reminders and confirmations.",
        url: "https://www.reddit.com/r/Entrepreneur/comments/validation/",
      },
      {
        text: "The tools we tried were built for giant companies. We need something that fits how we actually work.",
        url: "https://news.ycombinator.com/item?id=39000001",
      },
    ],
    early_adopter_profile: claim(
      rand,
      `Small operators (under 20 staff) already paying for one vertical tool and unhappy with the follow-up workflow.`,
      1,
    ),
    leads,
  };
}

export function buildFeasibility(rand: () => number): FeasibilitySection {
  return {
    technical: claim(
      rand,
      "MVP is a web app plus notifications; no novel tech required. AI-assisted scheduling is off-the-shelf.",
      1,
    ),
    operational: claim(
      rand,
      "Support load is manageable if onboarding is self-serve; manual concierge for the first 20 customers.",
      1,
    ),
    legal_regulatory: claim(
      rand,
      "Standard privacy and payments compliance; check local licensing requirements for services in target regions.",
      1,
    ),
    mvp_cost_range: claim(rand, "$18k-$35k to build with a small team over 8-10 weeks.", 1),
    mvp_timeline: claim(rand, "8-10 weeks part-time, 4-6 weeks full-time.", 1),
    risks: [
      {
        risk: "Supply-side liquidity takes longer than expected in the first city",
        likelihood: "high",
        impact: "high",
        mitigation: "Launch with a concierge beta and hand-recruit the first 30 providers.",
      },
      {
        risk: "Incumbents copy the follow-up workflow",
        likelihood: "medium",
        impact: "medium",
        mitigation: "Build community and integration depth that is slow to copy.",
      },
      {
        risk: "Payment disputes and no-show costs",
        likelihood: "medium",
        impact: "low",
        mitigation: "Deposits, cancellation windows, and clear terms.",
      },
    ],
  };
}

export function buildBusinessModel(rand: () => number): BusinessModelSection {
  return {
    lean_canvas: {
      problem: "Coordination is manual, follow-ups get dropped, and tools are wrong-sized.",
      solution: "A focused workflow app with automated follow-ups and mobile-first booking.",
      key_metrics: "Activation (first job booked), weekly active operators, net revenue retention.",
      unique_value: "Fewer dropped jobs and hours saved weekly, with setup in under an hour.",
      unfair_advantage:
        "Founder is embedded in the niche community; early data flywheel on pricing and demand.",
      channels:
        "Niche communities, referral loops between providers and customers, local partnerships.",
      customer_segments: "Small operators (2-20 staff) and their repeat customers.",
      cost_structure: "Hosting, LLM usage, support, and community marketing.",
      revenue_streams: "Monthly subscription + optional payments take rate.",
    },
    revenue_streams: [
      claim(rand, "Subscription: $39/seat/month for operators; $19/month for solo providers.", 1),
      claim(rand, "Payments: 1.5% take rate on bookings processed in-app.", 1),
    ],
    pricing_options: [
      { name: "Solo", price: "$19 / month", notes: "One provider, unlimited bookings" },
      { name: "Team", price: "$39 / seat / month", notes: "Shared inbox, roles, reporting" },
      { name: "Pro", price: "$79 / seat / month", notes: "Automations, priority support, API" },
    ],
    unit_economics: {
      cac: claim(rand, "$120 blended CAC through community-led acquisition.", 1),
      ltv: claim(rand, "$1,050 gross LTV at 24-month average lifetime and $44 ARPA.", 1),
      assumptions: [
        "Monthly churn of 3-4% after the first 90 days",
        "Organic and community channels supply 60% of new customers",
        "Expansion revenue about 15% of MRR",
      ],
    },
    go_to_market: [
      claim(rand, "Concierge onboarding for the first 30 operators in one city.", 1),
      claim(rand, "Publish benchmark data for the niche to earn trust and backlinks.", 1),
      claim(rand, "Referral loop: operators invite their repeat customers to book in-app.", 1),
    ],
  };
}

export function collectSources(report: Omit<Report, "sources">): Source[] {
  const urls = new Set<string>();
  const add = (claimLike?: { source_urls?: string[] } | null) => {
    for (const url of claimLike?.source_urls ?? []) urls.add(url);
  };
  const market = report.market;
  if (market) {
    add(market.tam);
    add(market.sam);
    add(market.som);
    market.trends?.forEach(add);
    add(market.timing_why_now);
  }
  report.competitors?.competitors?.forEach((c) => {
    if (c.url) urls.add(c.url);
    add(c);
  });
  add(report.competitors?.differentiation);
  report.customers?.personas?.forEach(add);
  add(report.customers?.early_adopter_profile);
  const feasibility = report.feasibility;
  if (feasibility) {
    [
      feasibility.technical,
      feasibility.operational,
      feasibility.legal_regulatory,
      feasibility.mvp_cost_range,
      feasibility.mvp_timeline,
    ].forEach(add);
  }
  const bm = report.business_model;
  if (bm) {
    bm.revenue_streams?.forEach(add);
    add(bm.unit_economics?.cac);
    add(bm.unit_economics?.ltv);
    bm.go_to_market?.forEach(add);
  }
  urls.delete("");
  return [...urls].map((url, index) => ({
    number: index + 1,
    url,
    title: SOURCE_SITES.find((s) => s.url === url)?.title ?? new URL(url).hostname,
  }));
}

export function buildReport(
  rand: () => number,
  idea: IdeaDetail,
  run: Run,
  opts?: { exclude?: DimensionId[] },
): Report {
  const title = idea.latest_version?.brief?.title ?? idea.title;
  const scorecard = buildScorecard(rand, opts);
  const verdict = verdictFor(scorecard.overall);
  const nextSteps: NextStep[] = [
    {
      assumption: "Operators will pay $39/seat without a long trial",
      test: "Pre-sell to 15 operators from two communities with a refundable deposit.",
      risk: "high",
    },
    {
      assumption: "Follow-ups can be automated without hurting the human touch",
      test: "Run a concierge A/B over four weeks and measure no-show rates.",
      risk: "medium",
    },
    {
      assumption: "One city has enough supply density to seed the marketplace",
      test: "Map 100 providers; interview 20; measure response and referral willingness.",
      risk: "medium",
    },
  ];
  const partial = run.status === "partial";
  const reportWithoutSources: Omit<Report, "sources"> = {
    idea_id: idea.id,
    run_id: run.id,
    version: idea.latest_version?.number ?? 1,
    generated_at: run.finished_at ?? minutesAfter(BASE_TIME, 30),
    cost_usd: run.cost_usd,
    header: {
      title,
      one_liner: idea.one_liner,
      verdict,
      verdict_confidence: Math.round((0.55 + rand() * 0.4) * 100) / 100,
      overall_score: scorecard.overall,
      excluded_dimensions: scorecard.excluded,
      run_date: run.finished_at ?? null,
      cost_usd: run.cost_usd,
      partial,
    },
    scorecard: {
      dimensions: scorecard.dimensions,
      overall_score: scorecard.overall,
      excluded: scorecard.excluded,
    },
    brief: idea.latest_version?.brief ?? null,
    market: partial ? null : buildMarket(rand, title),
    competitors: partial ? null : buildCompetitors(rand, title),
    customers: partial ? null : buildCustomers(rand, title),
    feasibility: buildFeasibility(rand),
    business_model: partial ? null : buildBusinessModel(rand),
    next_steps: nextSteps,
    sections_status: partial
      ? {
          market: "not_completed",
          competitors: "not_completed",
          customers: "not_completed",
          feasibility: "done",
          business_model: "not_completed",
        }
      : {
          market: "done",
          competitors: "done",
          customers: "done",
          feasibility: "done",
          business_model: "done",
        },
  };
  return { ...reportWithoutSources, sources: collectSources(reportWithoutSources) };
}

export const ALL_STEPS: RunStepName[] = [
  "refine",
  "market",
  "competitors",
  "customers",
  "feasibility",
  "business_model",
  "critic",
];

export function completedRun(idea: IdeaDetail, index: number, opts?: { partial?: boolean }): Run {
  const started = BASE_TIME + index * 3_600_000;
  const finished = started + 4.5 * 60_000;
  const steps: RunStep[] = ALL_STEPS.map((step, stepIndex) => ({
    step,
    status:
      opts?.partial && ["market", "competitors", "customers", "business_model"].includes(step)
        ? "skipped"
        : "done",
    cost_usd: Math.round((0.03 + (stepIndex % 4) * 0.02) * 100) / 100,
    model: stepIndex < 2 ? "gpt-4.1-mini" : "gpt-4.1",
    attempts: 1,
    error: null,
    started_at: new Date(started + stepIndex * 30_000).toISOString(),
    finished_at: new Date(started + (stepIndex + 1) * 30_000).toISOString(),
  }));
  const cost = Math.round(steps.reduce((sum, s) => sum + s.cost_usd, 0) * 100) / 100;
  return {
    id: uuidFor(90_000 + index),
    idea_id: idea.id,
    idea_version_id: idea.latest_version?.id ?? uuidFor(index),
    status: opts?.partial ? "partial" : "done",
    step: null,
    cost_usd: cost,
    cost_cap_usd: 0.75,
    error: null,
    steps,
    questions: [],
    created_at: new Date(started).toISOString(),
    started_at: new Date(started).toISOString(),
    finished_at: new Date(finished).toISOString(),
  };
}

export function makeRunEvent(
  runId: string,
  id: string,
  event: Partial<RunEvent> & Pick<RunEvent, "type">,
): RunEvent {
  return {
    id,
    run_id: runId,
    at: new Date(BASE_TIME + Number(id) * 1000).toISOString(),
    step: null,
    status: null,
    error: null,
    cost_usd: null,
    cost_cap_usd: 0.75,
    questions: [],
    ...event,
  } as RunEvent;
}

export function emptyList(): IdeaList {
  return { items: [], next_cursor: null, mode: null };
}

export const QUESTIONS: ClarifyingQuestion[] = [
  {
    id: "q1",
    question: "Who is the first customer you want to serve?",
    help: "For example: solo operators in one city, or a specific team size.",
  },
  {
    id: "q2",
    question: "What region should the analysis assume?",
    help: "Regulatory and pricing evidence changes a lot by region.",
  },
];

export function ideaSummaryFrom(detail: IdeaDetail): Idea {
  const {
    versions: _versions,
    latest_version: _latestVersion,
    latest_run: _latestRun,
    ...summary
  } = detail;
  return summary;
}
