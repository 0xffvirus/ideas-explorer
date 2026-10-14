# Spec: jev-gate

> Module of [SPEC.md](SPEC.md). Code lives in `backend/app/jev/`. Depends on nothing.

## Objective

Wrap **Jev** (TypeSafe AI's System One model) in a typed client and a catalog of
questions, so the pipeline can make **decisions with calibrated confidence**:
classify, score, gate evidence, and route. Low confidence is data, not an error.

Jev facts this module relies on (docs.typesafe.ai):
- `POST /v1/systemone`, Bearer `TYPESAFE_API_KEY`, `model: "jev-latest"`, Python SDK `typesafe-sdk`.
- A request contains one `state` (text) and many named `questions`, each one `choice`
  (labels→descriptions), `score` (criteria list), or `noul` (yes/no style, returns 0–1).
- Questions are evaluated in parallel and in isolation. Adding more barely changes latency, so we
  **fan out** many questions per call.
- Choice and Score return `confidence` and `probabilities`. Noul returns a single value.

## Question Catalog (`app/jev/catalog.py`)

| Key | Type | Used for |
|---|---|---|
| `category` | choice | b2b_saas, b2c_app, marketplace, hardware, service, content, fintech, health, other |
| `business_type` | choice | b2b, b2c, b2b2c, b2g |
| `brief_is_specific` | noul | Is the raw input concrete enough to analyze without clarifying questions? |
| `problem_severity` | score 1-5 | scorecard |
| `market_evidence` | score 1-5 | scorecard (state = market section + sources) |
| `competition_intensity` | score 1-5 | scorecard (inverted in the overall score) |
| `customer_reachability` | score 1-5 | scorecard |
| `feasibility` | score 1-5 | scorecard |
| `monetization_clarity` | score 1-5 | scorecard |
| `claim_supported` | noul | per claim: "Does this source snippet support this claim?" |
| `is_relevant_evidence` | noul | filter research results before agents read them |
| `verdict` | choice | pursue, refine, park (state = full report summary) |

Each entry is a versioned Pydantic object (`instructions`, `criteria`), so prompt changes are tracked.

## Public Interface

```python
class JevClient:                       # thin, typed wrapper; one HTTP call per method
    async def ask(self, state: str, questions: dict[str, Question]) -> dict[str, Answer]: ...

class Gate:                            # domain helpers built on ask()
    async def classify(brief) -> Classification
    async def scorecard(sections) -> Scorecard            # 6 DimensionScores, each with confidence
    async def verify_claims(claims: list[Claim]) -> list[VerifiedClaim]  # batched fan-out
    async def filter_evidence(query, items: list[Evidence]) -> list[Evidence]
    async def verdict(summary) -> Verdict
```

**Confidence routing.** `CONFIDENCE_FLOOR` defaults to 0.6 (Ask first before changing it).
Below the floor → `needs_review=True`. For scorecard dimensions, the pipeline may do **one**
re-research pass before accepting a flagged result. A claim is accepted if `noul ≥ 0.7`, and below that it is labeled "unverified".

## Acceptance Criteria

- [ ] Responses map into typed `Answer` models. An unknown question type or a missing answer → `JevProtocolError`.
- [ ] One `ask()` call carries up to N questions (default 20). Larger batches are chunked and run concurrently.
- [ ] `verify_claims` for 40 claims makes ≤ 2 HTTP calls.
- [ ] The scorecard always returns 6 dimensions, and those with confidence < floor are flagged.
- [ ] Jev outage → the gate returns results marked `source="unavailable"` and the pipeline continues
      (the report shows "not scored"). It never fabricates a score from the LLM.
- [ ] Usage (`input_tokens`, `output_tokens`) is recorded per call.

## Testing

A `FakeJevClient` with scripted answers is used for unit and pipeline tests. Contract tests use recorded JSON
in `tests/fixtures/jev/`. `-m eval` runs the catalog against 10 golden ideas and checks
for stable categories and sane score spread.

## Open Questions

- Does the Python SDK expose async? If not, wrap it with `httpx` directly against the REST endpoint (preferred anyway).
- Quotas and pricing are unknown. They decide the max questions per run.
