# AE Triage API — Design Write-up

**Author:** Harsha Vardhan  
**Built:** June 28 – July 4, 2026  
**Live:** https://fde-sprint-production.up.railway.app

---

## Problem

Pharmacovigilance teams at pharma companies receive thousands of free-text adverse event 
reports daily. Manual triage — reading each report, extracting the suspected drug, 
classifying seriousness per ICH E2A criteria, writing a summary — is slow, inconsistent, 
and a bottleneck for regulatory timelines.

The question: can a Claude-powered API do this extraction reliably enough to augment 
(not replace) a PV analyst's workflow?

---

## Approach

A FastAPI service wraps a Claude API call with a pharmacovigilance-grounded system prompt. 
The prompt encodes ICH E2A seriousness criteria (death, life-threatening, hospitalisation, 
disability, congenital anomaly, medically important event) as classification rules. 
Claude extracts five structured fields and returns them as validated JSON.

Two endpoints:
- `POST /triage` — single report, synchronous, <2 seconds
- `POST /triage/batch` — CSV upload, processes all rows, skips failures gracefully

---

## Key Decisions

**1. System prompt JSON over tool use**  
Chose structured output via system prompt (`"Return ONLY valid JSON with these exact keys"`) 
rather than Claude's tool use API. Simpler to implement and debug at this stage; 
tool use adds value when the model needs to decide *whether* to call a function, 
not when the output schema is always the same.

**2. Pydantic validation on both sides**  
Input validated on ingress (empty report → 400), output validated on egress 
(Claude response parsed and cast to `TriageResponse`). If Claude returns an unexpected 
structure, the API returns a 500 with the raw Claude output — making prompt debugging 
straightforward.

**3. `extract_json()` helper**  
Claude occasionally wraps JSON in markdown code fences. A regex helper strips these 
before `json.loads()`. Discovered in testing — added defensively.

**4. Per-row exception handling in batch**  
One malformed report skips rather than crashing the entire batch. 
PV teams upload real-world data — dirty rows are expected, not exceptional.

**5. `confidence` field**  
Added as a signal for downstream human review. High-confidence serious events can 
be fast-tracked; low-confidence outputs get manual review. 
Keeps humans in the loop for safety-critical decisions.

---

## Trade-offs

| Decision | What I gained | What I gave up |
|---|---|---|
| System prompt JSON | Simplicity, fast iteration | Less robust than tool use if Claude adds prose |
| claude-opus-4-8 | High accuracy on clinical text | Cost — Haiku would be 20x cheaper |
| Synchronous batch | Simple implementation | Slow for large CSVs (>100 rows) — async queue needed at scale |
| Railway deploy | Live in 2 min, zero config | Less control than GCP Cloud Run |

---

## Risks

**Hallucinated drug names** — Claude may confidently name the wrong drug if the report 
is ambiguous. Mitigation: `confidence` field flags uncertain extractions for human review.

**Prompt brittleness** — changing the model version or prompt wording can shift 
classification behaviour. Mitigation: pytest suite with ICH E2A seriousness cases 
acts as a regression harness.

**No authentication** — the live API is open. For production: add API key auth 
via FastAPI's `HTTPBearer` dependency.

---

## What I'd Do With More Time

1. **Async batch processing** — queue large CSVs, return a job ID, poll for results
2. **Confidence calibration** — compare Claude's confidence ratings against 
   expert-labelled cases to validate they're meaningful
3. **MedDRA term mapping** — normalise extracted events to MedDRA preferred terms 
   for regulatory submission compatibility
4. **Authentication + rate limiting** — production-ready security layer
5. **Observability** — log every Claude call with latency, token usage, 
   and output for drift detection

---

## Results

Tested against 5 representative AE reports spanning the ICH E2A seriousness spectrum:

| Case | Drug | Expected | Result |
|---|---|---|---|
| Chest pain + hospitalisation | Aspirin | serious | ✅ serious |
| Mild headache, resolved | Paracetamol | non-serious | ✅ non-serious |
| Anaphylactic shock | Amoxicillin | serious | ✅ serious |
| Non-itchy rash, resolved | Metformin | non-serious | ✅ non-serious |
| Fatal haemorrhage | Warfarin | serious | ✅ serious |

5/5 correct. Confidence: high on all cases.