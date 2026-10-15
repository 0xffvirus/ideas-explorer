import type {
  CompareReport,
  IdeaDetail,
  IdeaSummary,
  Report,
  ReportSection,
  RunRead,
  RunStepRead,
  ScorecardEntry,
  Source,
} from "@/lib/api/types";

/** In-memory idea fixture with the extra fields the mock API needs. */
export interface MockIdea extends IdeaSummary {
  raw_input: string;
  /** Extra searchable text standing in for the refined brief. */
  brief: string;
  version_id: string;
}

export const MOCK_IDEA_IDS = {
  petTracker: "11111111-1111-4111-8111-111111111111",
  invoiceBot: "22222222-2222-4222-8222-222222222222",
  toolLibrary: "33333333-3333-4333-8333-333333333333",
  quantumBackup: "44444444-4444-4444-8444-444444444444",
  mealPlanner: "55555555-5555-4555-8555-555555555555",
  clarifyDemo: "66666666-6666-4666-8666-666666666666",
} as const;

export const MOCK_RUN_IDS = {
  petTracker: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  invoiceBot: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  toolLibrary: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
  clarifyDemo: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
} as const;

const VERSION_IDS = {
  petTracker: "1a000000-0000-4000-8000-000000000001",
  invoiceBot: "2a000000-0000-4000-8000-000000000002",
  toolLibrary: "3a000000-0000-4000-8000-000000000003",
  quantumBackup: "4a000000-0000-4000-8000-000000000004",
  mealPlanner: "5a000000-0000-4000-8000-000000000005",
  clarifyDemo: "6a000000-0000-4000-8000-000000000006",
};

export const BASE_IDEAS: MockIdea[] = [
  {
    id: MOCK_IDEA_IDS.petTracker,
    version_id: VERSION_IDS.petTracker,
    title: "Pet health tracker for busy owners",
    status: "done",
    verdict: "pursue",
    category: "Consumer",
    overall_score: 76.4,
    pinned: false,
    archived_at: null,
    created_at: "2026-10-10T09:00:00.000Z",
    updated_at: "2026-10-11T12:00:00.000Z",
    tags: ["pets", "health"],
    latest_version_number: 1,
    raw_input:
      "An app that tracks my cat's litter box habits and warns me about health issues early.",
    brief:
      "A smart litter tray sensor that watches cat weight and litter habits to catch illness early.",
  },
  {
    id: MOCK_IDEA_IDS.invoiceBot,
    version_id: VERSION_IDS.invoiceBot,
    title: "AI invoice reconciliation for freelancers",
    status: "analyzing",
    verdict: null,
    category: "Fintech",
    overall_score: null,
    pinned: false,
    archived_at: null,
    created_at: "2026-10-09T09:00:00.000Z",
    updated_at: "2026-10-09T10:00:00.000Z",
    tags: ["finance", "ai"],
    latest_version_number: 1,
    raw_input: "Reconcile my invoices against bank transactions automatically every Friday.",
    brief: "An autonomous bookkeeper that matches invoices to payments and flags mismatches.",
  },
  {
    id: MOCK_IDEA_IDS.toolLibrary,
    version_id: VERSION_IDS.toolLibrary,
    title: "Neighborhood tool library",
    status: "queued",
    verdict: null,
    category: "Marketplace",
    overall_score: null,
    pinned: false,
    archived_at: null,
    created_at: "2026-10-08T09:00:00.000Z",
    updated_at: "2026-10-08T09:05:00.000Z",
    tags: ["community"],
    latest_version_number: 1,
    raw_input: "Let neighbors lend drills and ladders to each other with a deposit system.",
    brief: "A peer-to-peer tool sharing club with deposits and pickup lockers.",
  },
  {
    id: MOCK_IDEA_IDS.quantumBackup,
    version_id: VERSION_IDS.quantumBackup,
    title: "Quantum-safe backup for small teams",
    status: "draft",
    verdict: "refine",
    category: "Security",
    overall_score: 58.0,
    pinned: true,
    archived_at: null,
    created_at: "2026-10-07T09:00:00.000Z",
    updated_at: "2026-10-07T09:30:00.000Z",
    tags: ["security", "ai"],
    latest_version_number: 1,
    raw_input: "Post-quantum encrypted backups that a five-person startup can actually set up.",
    brief: "A managed backup service using post-quantum cryptography for small companies.",
  },
  {
    id: MOCK_IDEA_IDS.mealPlanner,
    version_id: VERSION_IDS.mealPlanner,
    title: "Meal planning from fridge leftovers",
    status: "failed",
    verdict: "park",
    category: "Food",
    overall_score: 41.2,
    pinned: false,
    archived_at: null,
    created_at: "2026-10-06T09:00:00.000Z",
    updated_at: "2026-10-06T09:45:00.000Z",
    tags: ["food"],
    latest_version_number: 1,
    raw_input: "Plan dinners around whatever is left in my fridge before it goes bad.",
    brief: "A pantry-aware meal planner that reduces food waste and grocery spend.",
  },
  {
    id: MOCK_IDEA_IDS.clarifyDemo,
    version_id: VERSION_IDS.clarifyDemo,
    title: "Member-run bike repair workshop",
    status: "analyzing",
    verdict: null,
    category: "Community",
    overall_score: null,
    pinned: false,
    archived_at: null,
    created_at: "2026-10-05T09:00:00.000Z",
    updated_at: "2026-10-05T09:00:30.000Z",
    tags: ["community"],
    latest_version_number: 1,
    raw_input: "A member-run bike workshop where neighbors fix their own bikes together.",
    brief: "A cooperative repair space with shared tools, stands and booked time slots.",
  },
];

function step(
  name: string,
  status: string,
  costUsd: number,
  startedAt: string | null,
  finishedAt: string | null,
): RunStepRead {
  return {
    id: `${name}-step`,
    step: name,
    status,
    output: null,
    cost_usd: costUsd,
    model: "gpt-4o-mini",
    attempts: 1,
    error: null,
    started_at: startedAt,
    finished_at: finishedAt,
  };
}

export const BASE_RUNS: RunRead[] = [
  {
    id: MOCK_RUN_IDS.petTracker,
    idea_id: MOCK_IDEA_IDS.petTracker,
    version_id: VERSION_IDS.petTracker,
    status: "done",
    step: "critic",
    cost_usd: 0.42,
    cost_cap_usd: 0.75,
    error: null,
    questions: null,
    started_at: "2026-10-10T09:01:00.000Z",
    finished_at: "2026-10-10T09:04:30.000Z",
    steps: [
      step("classify", "done", 0.01, "2026-10-10T09:01:00.000Z", "2026-10-10T09:01:08.000Z"),
      step("refine", "done", 0.02, "2026-10-10T09:01:08.000Z", "2026-10-10T09:01:30.000Z"),
      step("market", "done", 0.08, "2026-10-10T09:01:30.000Z", "2026-10-10T09:02:10.000Z"),
      step("competitors", "done", 0.07, "2026-10-10T09:02:10.000Z", "2026-10-10T09:02:40.000Z"),
      step("customers", "done", 0.09, "2026-10-10T09:02:40.000Z", "2026-10-10T09:03:20.000Z"),
      step("feasibility", "done", 0.06, "2026-10-10T09:03:20.000Z", "2026-10-10T09:03:50.000Z"),
      step("business_model", "done", 0.06, "2026-10-10T09:03:50.000Z", "2026-10-10T09:04:15.000Z"),
      step("critic", "done", 0.03, "2026-10-10T09:04:15.000Z", "2026-10-10T09:04:30.000Z"),
    ],
  },
  {
    id: MOCK_RUN_IDS.invoiceBot,
    idea_id: MOCK_IDEA_IDS.invoiceBot,
    version_id: VERSION_IDS.invoiceBot,
    status: "running",
    step: "market",
    cost_usd: 0.05,
    cost_cap_usd: 0.75,
    error: null,
    questions: null,
    started_at: "2026-10-09T10:00:00.000Z",
    finished_at: null,
    // Steps are deliberately empty: the UI must build progress from SSE events.
    steps: [],
  },
  {
    id: MOCK_RUN_IDS.toolLibrary,
    idea_id: MOCK_IDEA_IDS.toolLibrary,
    version_id: VERSION_IDS.toolLibrary,
    status: "pending",
    step: "classify",
    cost_usd: 0,
    cost_cap_usd: 0.75,
    error: null,
    questions: null,
    started_at: "2026-10-08T09:06:00.000Z",
    finished_at: null,
    steps: [],
  },
  {
    id: MOCK_RUN_IDS.clarifyDemo,
    idea_id: MOCK_IDEA_IDS.clarifyDemo,
    version_id: VERSION_IDS.clarifyDemo,
    status: "running",
    step: "classify",
    cost_usd: 0,
    cost_cap_usd: 0.75,
    error: null,
    questions: null,
    started_at: "2026-10-05T09:01:00.000Z",
    finished_at: null,
    steps: [],
  },
];

export const CLARIFY_QUESTIONS = [
  {
    question: "Which city or neighborhood is this for?",
    why: "Local tool access and insurance rules differ by city.",
  },
  {
    question: "Will members pay a monthly fee or per visit?",
    why: "Pricing decides the whole revenue model.",
  },
];

const SCORECARD: ScorecardEntry[] = [
  {
    dimension: "problem_severity",
    label: "Problem severity",
    score: 4,
    confidence: 0.84,
    needs_review: false,
    source: "refine",
    rationale: "Owners report missing early illness signs until symptoms are advanced.",
  },
  {
    dimension: "market_evidence",
    label: "Market evidence",
    score: 4,
    confidence: 0.51,
    needs_review: true,
    source: "market",
    rationale: "Fast-growing pet tech spend, but sparse direct data on cat monitoring.",
  },
  {
    dimension: "competition",
    label: "Competition",
    score: 3,
    confidence: 0.72,
    needs_review: false,
    source: "competitors",
    rationale: "Litter-robot hardware exists; health analytics is still open.",
  },
  {
    dimension: "customer_access",
    label: "Customer access",
    score: 4,
    confidence: 0.66,
    needs_review: false,
    source: "customers",
    rationale: "Cat communities are easy to reach through breed and city groups.",
  },
  {
    dimension: "feasibility",
    label: "Feasibility",
    score: 3,
    confidence: 0.58,
    needs_review: true,
    source: "feasibility",
    rationale: "Sensor accuracy is proven; vet partnerships take longer than expected.",
  },
  {
    dimension: "business_model",
    label: "Business model",
    score: 4,
    confidence: 0.7,
    needs_review: false,
    source: "business_model",
    rationale: "A $9/month subscription clears hardware cost within eight months.",
  },
];

export const REPORT_SOURCES: Source[] = [
  { number: 1, url: "https://example.com/pet-tech-market", title: "Pet tech market report 2025" },
  { number: 2, url: "https://example.com/urban-pets", title: "Urban pet ownership study" },
];

const REPORT_SECTIONS: ReportSection[] = [
  {
    name: "market",
    title: "Market",
    status: "complete",
    json_payload: {
      market_size: "The pet tech market reached $8.2B in 2025 and grows about 12% per year.",
      demand_signal: "High — owners already pay for food subscriptions and vet telehealth.",
      trends: ["Remote monitoring adoption is rising", "Vets increasingly bundle data plans"],
    },
    markdown: "### Market\n\nPet tech reached **$8.2B** in 2025 ([source](https://example.com/pet-tech-market)).",
    claims: [
      {
        text: "Pet tech spend reached $8.2B in 2025.",
        citation_numbers: [1],
        status: "verified",
      },
      {
        text: "Urban cat ownership is growing by double digits every year.",
        citation_numbers: [],
        status: "unverified",
      },
    ],
  },
  {
    name: "competitors",
    title: "Competitors",
    status: "complete",
    json_payload: {
      competitors: [
        { name: "Whisker", positioning: "Hardware-first litter robots", funding: "$200M+" },
        { name: "Vet AI", positioning: "Telehealth triage for cats and dogs" },
      ],
      differentiation: "Health trend analytics rather than another litter box.",
    },
    markdown: "",
    claims: [
      {
        text: "Whisker has raised more than $200M.",
        citation_numbers: [2],
        status: "verified",
      },
    ],
  },
  {
    name: "customers",
    title: "Customers",
    status: "complete",
    json_payload: {
      personas: ["Cat owners aged 28-45 in cities", "Multi-cat households"],
      communities: ["r/cats", "City-specific cat Facebook groups"],
      pain_quotes: ["I only noticed something was wrong after two weeks."],
    },
    markdown: "",
    claims: [],
  },
  {
    name: "feasibility",
    title: "Feasibility",
    status: "complete",
    json_payload: {
      technical: "Weight and visit-frequency sensing is off-the-shelf.",
      operational: "Vet review workflow needed for alerts.",
      legal: "Pet health data is not PHI, but privacy policy still required.",
      cost_to_mvp: "$18k including hardware prototypes and a vet advisor.",
    },
    markdown: "",
    claims: [],
  },
  {
    name: "business_model",
    title: "Business model",
    status: "not_completed",
    json_payload: {},
    markdown: "",
    claims: [],
  },
];

/** One complete report derived from an idea fixture. */
export function reportFor(idea: MockIdea): Report {
  return {
    idea_id: idea.id,
    version_id: idea.version_id,
    run_id: MOCK_RUN_IDS.petTracker,
    header: {
      title: idea.title,
      one_liner: idea.brief,
      verdict: idea.verdict,
      verdict_confidence: 0.82,
      overall_score: idea.overall_score,
      score_basis: "all_dimensions",
      run_date: idea.updated_at,
      cost_usd: 0.42,
    },
    scorecard: SCORECARD,
    brief: {
      title: idea.title,
      one_liner: idea.brief,
      problem: "Owners cannot tell when a cat is unwell until symptoms are advanced.",
      solution: "A sensor tray plus trend analysis with vet-grade alerts.",
      target_users: "Cat owners aged 28-45 in cities.",
      value_prop: "Catch illness weeks earlier without daily checking.",
      key_assumptions: [
        "Owners will pay a subscription",
        "Litter habits correlate with illness",
      ],
      variants: ["A vet-clinic-first version with shared hardware"],
      claims: [
        {
          text: "Cat ownership is growing in urban households.",
          citation_numbers: [2],
          status: "verified",
        },
      ],
    },
    sections: REPORT_SECTIONS,
    next_steps: [
      {
        assumption: "Owners will pay $9/month",
        test: "Pre-sell to 20 owners from a landing page",
        cost_hint: "$200 in ads",
      },
      {
        assumption: "Vets will review alerts",
        test: "Interview 5 vets about a revenue-share plan",
        cost_hint: "10 hours",
      },
    ],
    sources: REPORT_SOURCES,
    generated_at: idea.updated_at,
    run_date: idea.updated_at,
    cost_usd: 0.42,
    is_partial: false,
  };
}

/** Compare payload: done ideas carry their report header plus scorecard. */
export function compareReportFor(entries: MockIdea[]): CompareReport {
  return {
    dimensions: SCORECARD.map((entry) => entry.dimension),
    entries: entries.map((idea) => ({
      idea_id: idea.id,
      title: idea.title,
      one_liner: idea.brief,
      verdict: idea.verdict,
      verdict_confidence: idea.verdict ? 0.8 : null,
      overall_score: idea.overall_score,
      category: idea.category,
      report: idea.status === "done" ? { header: reportFor(idea).header, scorecard: SCORECARD } : null,
      reason: idea.status === "done" ? null : "No completed report yet",
    })),
  };
}

export function ideaDetail(idea: MockIdea): IdeaDetail {
  return {
    id: idea.id,
    title: idea.title,
    status: idea.status,
    verdict: idea.verdict,
    category: idea.category,
    overall_score: idea.overall_score,
    pinned: idea.pinned,
    archived_at: idea.archived_at,
    created_at: idea.created_at,
    updated_at: idea.updated_at,
    latest_version: {
      id: idea.version_id,
      number: idea.latest_version_number,
      raw_input: idea.raw_input,
      context: null,
      brief: null,
      created_at: idea.created_at,
    },
    versions: [
      {
        id: idea.version_id,
        number: idea.latest_version_number,
        raw_input: idea.raw_input,
        context: null,
        brief: null,
        created_at: idea.created_at,
      },
    ],
    tags: idea.tags,
  };
}

export function ideaSummary(idea: MockIdea): IdeaSummary {
  return {
    id: idea.id,
    title: idea.title,
    status: idea.status,
    verdict: idea.verdict,
    category: idea.category,
    overall_score: idea.overall_score,
    pinned: idea.pinned,
    archived_at: idea.archived_at,
    created_at: idea.created_at,
    updated_at: idea.updated_at,
    tags: idea.tags,
    latest_version_number: idea.latest_version_number,
  };
}
