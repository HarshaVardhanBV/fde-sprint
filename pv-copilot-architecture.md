# Appendix — how the three point solutions interoperate

**This is an appendix, not the headline.** The portfolio is three independent point solutions (AE Triage, Regulatory Q&A, Safety Agent), each solving one bounded job on its own. This document exists only to show that, *because they share typed contracts*, they can be composed into an end-to-end path when a specific client wants one. It is not a claim to "solve PV" — that space is too big and too nuanced for any single tool. Read this only if the composition question comes up. Diagram: `pv-copilot-architecture.svg`.

## The optional chain

If a client does want an end-to-end path, a case can flow through six stages. Each stage is an existing point solution (or a thin new step), and each emits a typed object the next stage can consume.

1. **Intake** — a free-text AE report, or a batch CSV of them.
2. **Triage** (`01-ae-triage-api`, P1) — extract structured fields and an ICH-E2A seriousness label. Contract: `{seriousness, suspected_drug, event, summary, confidence}`.
3. **Serious? gate** — deterministic branch on `seriousness`. `non-serious` → log the record and close (cheap path, no further model calls). `serious` → continue to the full workup.
4. **FAERS context** (`04-safety-agent`, P4) — the tool-use loop pulls openFDA data for `suspected_drug` and computes **disproportionality signals (PRR / ROR / EBGM)**, not just a serious fraction. Contract: `Verdict` + the signal table.
5. **ICH check** (`02-reg-rag`, P2) — RAG over the ICH/FDA corpus confirms whether this event meets reporting criteria, with citations. Contract: `{answer, sources}`.
6. **Draft ICSR** — compose the case narrative from the triage fields + FAERS signals + reg citations. Contract: draft narrative + provenance.
7. **Human review** — a PV specialist approves or edits before anything is filed. This is the hard gate; the system drafts, the human commits.

Each point solution stands on its own and is presented that way. The chain here is an *optional* composition for a client who explicitly wants the end-to-end path — evidence that the pieces interoperate, not a repackaging of three tools into one "PV platform."

## Three cross-cutting layers (what makes it sellable, not just runnable)

**Traceability spine.** Every stage appends a structured record to a per-case, append-only log: the stage output, the tool-call trace (already captured in the agent), the source citations from RAG, and the case ID. In a regulated setting the audit trail is the product, not a nice-to-have.

**Visible evals** (`03-evals`). The harness already exists — surface the numbers in the UI. Current baselines: triage is typed and Pydantic-validated; RAG triad **4.79/5** (retrieval 4.57); agent **89% assessment match (8/9)** with rationale groundedness **5.0/5**. "94%-style agreement with a PV specialist, misses explained" persuades a J&J/GSK stakeholder more than any UI. The one agent miss (aspirin, expected `signal`, got `no-signal`) is exactly the kind of explained gap to show, not hide.

**Cost & resilience.** Two production-maturity signals:
- **Model router** — Haiku on the high-volume extraction/triage path, Opus reserved for the signal judgment. ~10× cheaper and faster where volume lives, and "I route by task" is itself a selling point. (Batch triage must also go concurrent — the current sequential loop over `claude-opus-4-8` per row would time out at 500 rows.)
- **Demo mode** — cache 3–5 canned outputs per page and add a live/cached toggle so every page renders a result even with no key, expired key, or zero credits. This is the single highest-leverage fix before showing anyone: a dead demo is worse than no demo when it's the sales asset.

## What's reused vs. what's new

Reused as-is: the three model calls / tool loops and the eval harness — they're the arrows in the diagram. New work: (a) the orchestrator that threads stage N's typed output into stage N+1, (b) the case-level audit log, (c) the PRR/ROR/EBGM computation inside the agent (the move from document-in/structured-out toward a genuine compute-a-decision layer, on public FAERS data), (d) demo-mode caching + toggle, (e) the model router and concurrent batch.

## Why the disproportionality upgrade matters

Triage and Reg-RAG are still document-in / structured-out. The FAERS agent is the beachhead into analytics: PRR/ROR/EBGM is the real PV signal-detection math regulators actually use, computed on public data. That's a categorically stronger claim than "another extraction demo," and it's the piece worth pushing hardest.
