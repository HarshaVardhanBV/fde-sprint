# Week 3 · Day 15 — Eval Harness for the Regulatory RAG API

An LLM-as-judge eval harness that scores your **live** reg-rag app so you have a
number, not a vibe. This is Phase 4 (Evaluate) of the FDE Delivery Framework.

## The idea in one breath
Golden set (questions with known answers) → ask your live RAG app → a strong Claude
model **judges** each answer against a rubric → a scorecard. Today's score is your
**baseline ("before")**. Change the RAG later, re-run, compare = proof it improved.

## What's here
| File | What it is |
|---|---|
| `golden_set.json` | 8 ICH E2A questions with expected key points. 7 answerable + 1 "trap" (out-of-scope, should be refused). |
| `eval.py` | The harness: asks the live API, judges, prints + saves a scorecard. |
| `results_*.json/.csv` | Created when you run it. Keep them to compare over time. |

## How to run (5 steps)
```bash
# 1. go to this folder
cd "week3-evals"

# 2. install the two libraries it needs
pip install anthropic requests

# 3. set your Anthropic key (same one from Weeks 1-2)
export ANTHROPIC_API_KEY="sk-ant-..."

# 4. run it
python eval.py

# 5. read the SCORECARD it prints, and the saved results_*.csv
```

If your Railway app went to sleep, the first question may be slow (cold start) —
that's normal, let it finish.

## The rubric (what the judge scores, each 1–5)
- **groundedness** — is the answer supported by the retrieved sources? (anti-hallucination — the one that matters most for regulated use)
- **answer_relevance** — does it actually answer the question?
- **correctness** — does it cover the expected key points?

For the trap question, a correct *refusal* ("not in the documents") scores 5;
inventing an aspirin dose scores 1. That single test is how you prove your
"answer ONLY from context" prompt actually works.

## The gate (Day 15 done when)
You can state your reg-rag's baseline score out of 5, and you have a saved
`results_*` file to compare against next time.

## Next (Day 16)
Promote this into a reusable `Eval_Harness_Blueprint.md` in `60_Consulting_IP`,
the same way you did for the API and RAG blueprints.
