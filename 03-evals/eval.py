"""
eval.py — LLM-as-judge eval harness for the Regulatory RAG API (Project 2).

WHAT THIS DOES (the whole idea in 4 lines):
  1. Take a "golden set" of questions we already know the right answers to.
  2. Ask your LIVE RAG app each question (over the internet).
  3. Have a strong Claude model act as a JUDGE and score each answer.
  4. Print a scorecard + save results, so you have a NUMBER, not a vibe.

This baseline number is your "before". Next session you tweak the RAG
(chunk size, n_results, prompt) and re-run -> that's your "after". The gap
is proof your change helped (or hurt). That is the entire point of evals.

RUN:
  pip install anthropic requests
  export ANTHROPIC_API_KEY="sk-ant-..."      # same key as Weeks 1-2
  python eval.py
"""

import os
import re
import json
import csv
import time
import requests
import anthropic

# ---- Config ---------------------------------------------------------------
# Your RAG app that is already live on Railway. The eval talks to THIS.
RAG_URL = os.environ.get("RAG_URL", "https://reg-rag-production.up.railway.app/ask")

# A STRONG model judges. Cheap models make sloppy judges (your own note).
JUDGE_MODEL = "claude-opus-4-8"

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from your environment


# ---- Helpers --------------------------------------------------------------
def extract_json(text: str) -> str:
    """Strip markdown code fences Claude sometimes wraps JSON in.
    (Same defensive-parsing pattern you used in Projects 1 and 2.)"""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text)
    return text


def ask_rag(question: str) -> dict:
    """Send one question to your live RAG API. Returns {answer, sources}."""
    r = requests.post(RAG_URL, json={"question": question}, timeout=60)
    r.raise_for_status()
    return r.json()  # your API returns {"answer": ..., "sources": [...]}


# ---- The judge ------------------------------------------------------------
# The rubric is the heart of an eval. We score 3 things, each 1-5:
#   groundedness    -> is the answer supported by the retrieved sources?
#                      (This is the anti-hallucination score. Most important
#                       for a regulated / compliance use case.)
#   answer_relevance-> does it actually answer the question asked?
#   correctness     -> does it cover the expected key points we know are true?
# For the "trap" question (type=refusal), correctly declining IS the win.

JUDGE_SYSTEM = """You are a strict evaluation judge for a regulatory Q&A system.
You will be given: the QUESTION, the SYSTEM ANSWER, the SOURCE CHUNKS the system
retrieved, and the EXPECTED KEY POINTS. Score the answer objectively.

Return ONLY valid JSON with exactly these keys:
{
  "groundedness": 1-5,        // is every claim supported by the SOURCE CHUNKS? 5 = fully grounded, 1 = hallucinated
  "answer_relevance": 1-5,    // does it address the QUESTION? 5 = directly, 1 = off-topic
  "correctness": 1-5,         // does it cover the EXPECTED KEY POINTS? 5 = all, 1 = none/wrong
  "reason": "<one sentence explaining the scores>"
}

Special rule: if the expected behaviour is to REFUSE (the answer is not in the
documents), then a correct, honest refusal scores 5 on all three, and inventing
an answer scores 1 on groundedness and correctness."""


def judge(item: dict, answer: str, sources: list) -> dict:
    is_refusal = item.get("type") == "refusal"
    user = f"""QUESTION:
{item['question']}

SYSTEM ANSWER:
{answer}

SOURCE CHUNKS THE SYSTEM RETRIEVED:
{json.dumps(sources, indent=2)}

EXPECTED KEY POINTS:
{json.dumps(item['expected_points'], indent=2)}

EXPECTED BEHAVIOUR: {"REFUSE — the answer is NOT in the documents" if is_refusal else "ANSWER using the sources"}

Score now."""

    msg = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=400,
        system=JUDGE_SYSTEM,
        messages=[{"role": "user", "content": user}],
    )
    raw = msg.content[0].text
    data = json.loads(extract_json(raw))
    # Defensive: clamp scores into 1-5 so one weird judge reply can't break the run.
    for k in ("groundedness", "answer_relevance", "correctness"):
        data[k] = max(1, min(5, int(data[k])))
    return data


# ---- The context-relevance judge (RAG triad, leg 1) -----------------------
# This judge NEVER sees the answer. It grades ONLY the retrieved chunks:
# "do these chunks actually contain what's needed to answer the question?"
# That's what separates a RETRIEVAL failure from a GENERATION failure. If
# context relevance is low, the right chunk never reached the model -- no
# prompt tweak can fix that; you fix retrieval (n_results, chunk size,
# reranking) or the corpus itself.

CONTEXT_JUDGE_SYSTEM = """You are a retrieval-quality judge for a RAG system.
You are given a QUESTION and the SOURCE CHUNKS that were retrieved for it.
You do NOT see any generated answer. Judge ONLY whether these chunks contain
the information needed to answer the question.

Return ONLY valid JSON with exactly these keys:
{
  "context_relevance": 1-5,   // 5 = chunks fully contain what's needed; 1 = chunks are irrelevant / missing the needed facts
  "reason": "<one sentence>"
}"""


def judge_context(item: dict, sources: list) -> dict:
    """Score ONLY the retrieved chunks against the question. Answer not shown."""
    user = f"""QUESTION:
{item['question']}

SOURCE CHUNKS RETRIEVED:
{json.dumps(sources, indent=2)}

Judge whether these chunks contain the information needed to answer the question."""
    msg = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=250,
        system=CONTEXT_JUDGE_SYSTEM,
        messages=[{"role": "user", "content": user}],
    )
    data = json.loads(extract_json(msg.content[0].text))
    data["context_relevance"] = max(1, min(5, int(data["context_relevance"])))
    return data


# ---- Main loop ------------------------------------------------------------
def main():
    with open("golden_set.json") as f:
        golden = json.load(f)

    print(f"\nRunning eval against: {RAG_URL}")
    print(f"Judge model: {JUDGE_MODEL}")
    print(f"Golden set: {len(golden)} questions\n")

    rows = []
    for i, item in enumerate(golden, 1):
        print(f"[{i}/{len(golden)}] {item['id']} ...", end=" ", flush=True)
        try:
            rag = ask_rag(item["question"])
            sources = rag.get("sources", [])
            # RAG-triad leg 1: grade the RETRIEVED CHUNKS alone (judge never sees the answer)
            ctx = judge_context(item, sources)
            # Answer-level scores (this judge DOES see the answer)
            scores = judge(item, rag.get("answer", ""), sources)
            rows.append({
                "id": item["id"],
                "type": item["type"],
                "context_relevance": ctx["context_relevance"],
                **{k: scores[k] for k in ("groundedness", "answer_relevance", "correctness")},
                "reason": scores["reason"],
                "ctx_reason": ctx["reason"],
            })
            print(f"ctx{ctx['context_relevance']}  G{scores['groundedness']} "
                  f"R{scores['answer_relevance']} C{scores['correctness']}")
        except Exception as e:
            print(f"ERROR: {e}")
            rows.append({"id": item["id"], "type": item["type"], "context_relevance": 0,
                         "groundedness": 0, "answer_relevance": 0, "correctness": 0,
                         "reason": f"error: {e}", "ctx_reason": ""})
        time.sleep(0.5)  # be polite to the API

    # ---- Scorecard --------------------------------------------------------
    def avg(key, types=None):
        vals = [r.get(key, 0) for r in rows
                if r.get(key, 0) > 0 and (types is None or r["type"] in types)]
        return sum(vals) / len(vals) if vals else 0

    print("\n" + "=" * 78)
    print("SCORECARD  (1-5 each; RAG triad + correctness). BASELINE / 'before'.")
    print("=" * 78)
    print(f"{'question':<26}{'ctx_rel':>9}{'ground':>8}{'relev':>8}{'correct':>9}")
    print("-" * 78)
    for r in rows:
        print(f"{r['id']:<26}{r.get('context_relevance', 0):>9}"
              f"{r['groundedness']:>8}{r['answer_relevance']:>8}{r['correctness']:>9}")
    print("-" * 78)
    # ctx_rel is averaged over GROUNDED questions only: for the trap (refusal),
    # LOW context relevance is CORRECT, so including it would be misleading.
    print(f"{'AVERAGE (grounded Qs)':<26}{avg('context_relevance', {'grounded'}):>9.2f}"
          f"{avg('groundedness'):>8.2f}{avg('answer_relevance'):>8.2f}{avg('correctness'):>9.2f}")
    print("=" * 78)

    answer_quality = (avg('groundedness') + avg('answer_relevance') + avg('correctness')) / 3
    retrieval_quality = avg('context_relevance', {'grounded'})
    print(f"ANSWER-QUALITY SCORE : {answer_quality:.2f} / 5   (comparable to your 4.83 baseline)")
    print(f"RETRIEVAL SCORE      : {retrieval_quality:.2f} / 5   (context relevance, grounded Qs)")
    print("If a question has HIGH answer scores but LOW ctx_rel, retrieval is the weak link.\n")
    overall = answer_quality

    # ---- Save results (so you can compare before/after later) -------------
    stamp = time.strftime("%Y%m%d_%H%M%S")
    with open(f"results_{stamp}.json", "w") as f:
        json.dump({"rag_url": RAG_URL, "answer_quality": answer_quality,
                   "retrieval_quality": retrieval_quality, "rows": rows}, f, indent=2)
    with open(f"results_{stamp}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "type", "context_relevance", "groundedness",
                                          "answer_relevance", "correctness", "reason", "ctx_reason"])
        w.writeheader()
        w.writerows(rows)
    print(f"Saved results_{stamp}.json and results_{stamp}.csv")
    print("Tip: keep this baseline. After you tune the RAG, re-run and compare.\n")


if __name__ == "__main__":
    main()
