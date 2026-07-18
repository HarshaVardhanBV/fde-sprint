"""
eval_agent.py — evaluate the safety-signal agent against a golden set of drugs.

This is 03-evals discipline pointed at the agent. Three-level scoring:
  1. assessment label  -> DETERMINISTIC: does the agent's verdict match the
                          known-correct label? (exact match, no LLM needed)
  2. signal detector   -> DETERMINISTIC: score the DISPROPORTIONALITY MATH on its
                          own. Collapse the agent's computed PRR/ROR/IC rows into a
                          label (signal if any reaction flags) and report precision,
                          recall and F1 against the gold set — plus whether the LLM's
                          narrative agrees with its own numbers. This is the new
                          "signal precision" leg.
  3. rationale quality -> LLM-JUDGE: is the rationale grounded, and did it AVOID
                          the serious-fraction trap? (a strong Claude grades it)

We import and run the REAL agent (agent.run_agent) — we evaluate the deployed
behaviour, not a copy.

RUN:
  python eval_agent.py
"""

import re
import json
import time
import anthropic
from dotenv import load_dotenv

from agent import run_agent            # the real agent (returns a validated Verdict)

load_dotenv(override=True)
client = anthropic.Anthropic()
JUDGE_MODEL = "claude-opus-4-8"


def extract_json(text: str) -> str:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    return re.sub(r"\s*```$", "", text)


# ---- Level 2: the rationale judge ----------------------------------------
JUDGE_SYSTEM = """You grade a pharmacovigilance agent's RATIONALE for a safety verdict.
Given the DRUG and the agent's VERDICT (JSON), score only the rationale. Return ONLY JSON:
{
  "grounded": 1-5,            // is the rationale consistent with the reactions/data it cites? 5 = fully, 1 = unsupported
  "avoids_serious_trap": 1-5, // 5 = correctly does NOT use a high serious_fraction as the signal justification; 1 = leans on serious_fraction as the main reason
  "reason": "<one sentence>"
}"""


def judge_rationale(drug: str, verdict: dict) -> dict:
    user = f"DRUG: {drug}\nVERDICT:\n{json.dumps(verdict, indent=2)}\n\nGrade the rationale."
    msg = client.messages.create(
        model=JUDGE_MODEL, max_tokens=300, system=JUDGE_SYSTEM,
        messages=[{"role": "user", "content": user}],
    )
    data = json.loads(extract_json(msg.content[0].text))
    for k in ("grounded", "avoids_serious_trap"):
        data[k] = max(1, min(5, int(data[k])))
    return data


# ---- Level 2: the signal detector (deterministic, from the math) ----------
def math_signal_label(signals):
    """Collapse the agent's computed disproportionality rows into ONE label,
    using the math alone (no LLM):
      - 'insufficient-data' if no signal rows were computed,
      - 'signal'            if any reaction flags (its PRR/ROR/IC criteria are met),
      - 'no-signal'         if rows were computed but none flag.
    Scoring this separately tells us whether the DETECTOR is right, independent of
    how the model narrated it."""
    if not signals:
        return "insufficient-data"
    return "signal" if any(s.get("signal") for s in signals) else "no-signal"


def _fnum(x):
    """Return x if it's a real number, else None (signal rows may carry a 'note')."""
    return x if isinstance(x, (int, float)) else None


# ---- Main ----------------------------------------------------------------
def main():
    with open("golden_drugs.json") as f:
        golden = json.load(f)

    rows = []
    for case in golden:
        drug, expected = case["drug"], case["expected_assessment"]
        difficulty = case.get("difficulty", "easy")
        print(f"\n########## {drug}  (expect: {expected}, {difficulty}) ##########")
        verdict = run_agent(f"Assess the safety signals for {drug} using the tools.")

        if verdict is None:                      # the agent's JSON failed to parse
            rows.append({"drug": drug, "expected": expected, "difficulty": difficulty,
                         "got": "PARSE_FAIL", "match": False,
                         "n_signals": 0, "flagged": 0, "max_prr": None, "max_ic": None,
                         "math_label": "PARSE_FAIL", "math_match": False,
                         "verdict_math_agree": False,
                         "grounded": 0, "avoids_serious_trap": 0,
                         "reason": "verdict did not parse"})
            continue

        vd = verdict.model_dump()
        match = (verdict.assessment == expected)

        # ---- Level 2: score the disproportionality math on its own -----------
        signals = verdict.signals or []
        math_label = math_signal_label(signals)
        prrs = [p for p in (_fnum(s.get("PRR")) for s in signals) if p is not None]
        ics = [i for i in (_fnum(s.get("IC")) for s in signals) if i is not None]

        j = judge_rationale(drug, vd)
        rows.append({"drug": drug, "expected": expected, "difficulty": difficulty,
                     "got": verdict.assessment, "match": match, "confidence": verdict.confidence,
                     "n_signals": len(signals),
                     "flagged": sum(1 for s in signals if s.get("signal")),
                     "max_prr": round(max(prrs), 2) if prrs else None,
                     "max_ic": round(max(ics), 2) if ics else None,
                     "math_label": math_label,
                     "math_match": (math_label == expected),
                     "verdict_math_agree": (verdict.assessment == math_label),
                     "grounded": j["grounded"], "avoids_serious_trap": j["avoids_serious_trap"],
                     "reason": j["reason"]})
        time.sleep(0.5)

    # ---- Scorecard --------------------------------------------------------
    n = len(rows)
    correct = sum(r["match"] for r in rows)

    def avg(k):
        vals = [r.get(k, 0) for r in rows if r.get(k, 0) > 0]
        return sum(vals) / len(vals) if vals else 0

    def split(diff):
        s = [r for r in rows if r.get("difficulty") == diff]
        return sum(r["match"] for r in s), len(s)
    ec, en = split("easy")
    hc, hn = split("hard")

    # ---- Level 2 aggregates: the signal DETECTOR (math only) --------------
    math_correct = sum(1 for r in rows if r.get("math_match"))
    agree = sum(1 for r in rows if r.get("verdict_math_agree"))
    #  Precision/recall for the positive class ('signal'), using the math label.
    tp = sum(1 for r in rows if r["expected"] == "signal" and r.get("math_label") == "signal")
    fp = sum(1 for r in rows if r["expected"] != "signal" and r.get("math_label") == "signal")
    fn = sum(1 for r in rows if r["expected"] == "signal" and r.get("math_label") != "signal")
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    W = 100
    print("\n" + "=" * W)
    print("AGENT EVAL SCORECARD  (assessment + signal-detector = deterministic; grnd/trap = LLM-judged 1-5)")
    print("=" * W)
    print(f"{'drug':<14}{'diff':<5}{'expected':<16}{'got':<16}{'ok':<4}"
          f"{'mathLbl':<16}{'maxPRR':>8}{'maxIC':>7}{'grnd':>6}{'trap':>6}")
    print("-" * W)
    for r in rows:
        print(f"{r['drug']:<14}{r.get('difficulty', '?'):<5}{r['expected']:<16}{str(r['got']):<16}"
              f"{'Y' if r['match'] else 'N':<4}{str(r.get('math_label', '—')):<16}"
              f"{str(r.get('max_prr', '—')):>8}{str(r.get('max_ic', '—')):>7}"
              f"{r.get('grounded', 0):>6}{r.get('avoids_serious_trap', 0):>6}")
    print("-" * W)
    print(f"1) Assessment accuracy (LLM verdict): {correct}/{n} = {correct / n * 100:.0f}%"
          f"    (easy {ec}/{en}, hard {hc}/{hn})")
    print(f"2) Signal detector (math only)      : {math_correct}/{n} = {math_correct / n * 100:.0f}%"
          f"    precision {precision:.2f}  recall {recall:.2f}  F1 {f1:.2f}   (positive = 'signal')")
    print(f"   Verdict <-> math agreement       : {agree}/{n} = {agree / n * 100:.0f}%"
          f"    (does the narrative match its own numbers?)")
    print(f"3) Avg rationale — grounded: {avg('grounded'):.2f}/5   "
          f"avoids-serious-trap: {avg('avoids_serious_trap'):.2f}/5")
    print("=" * W)

    stamp = time.strftime("%Y%m%d_%H%M%S")
    with open(f"agent_eval_{stamp}.json", "w") as f:
        json.dump({"accuracy": correct / n,
                   "signal_detector": {"accuracy": math_correct / n, "precision": precision,
                                       "recall": recall, "f1": f1,
                                       "tp": tp, "fp": fp, "fn": fn},
                   "verdict_math_agreement": agree / n,
                   "rows": rows}, f, indent=2)
    print(f"Saved agent_eval_{stamp}.json — this is your agent baseline.")


if __name__ == "__main__":
    main()
