"""
eval_agent.py — evaluate the safety-signal agent against a golden set of drugs.

This is 03-evals discipline pointed at the agent. Two-level scoring:
  1. assessment label  -> DETERMINISTIC: does the agent's verdict match the
                          known-correct label? (exact match, no LLM needed)
  2. rationale quality -> LLM-JUDGE: is the rationale grounded, and did it AVOID
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
                         "got": "PARSE_FAIL", "match": False, "grounded": 0,
                         "avoids_serious_trap": 0, "reason": "verdict did not parse"})
            continue

        vd = verdict.model_dump()
        match = (verdict.assessment == expected)
        j = judge_rationale(drug, vd)
        rows.append({"drug": drug, "expected": expected, "difficulty": difficulty,
                     "got": verdict.assessment, "match": match, "confidence": verdict.confidence,
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

    print("\n" + "=" * 82)
    print("AGENT EVAL SCORECARD  (assessment = deterministic, grnd/trap = LLM-judged 1-5)")
    print("=" * 82)
    print(f"{'drug':<15}{'diff':<6}{'expected':<18}{'got':<18}{'ok':<5}{'grnd':<6}{'trap':<6}")
    print("-" * 82)
    for r in rows:
        print(f"{r['drug']:<15}{r.get('difficulty', '?'):<6}{r['expected']:<18}{str(r['got']):<18}"
              f"{'Y' if r['match'] else 'N':<5}{r.get('grounded', 0):<6}{r.get('avoids_serious_trap', 0):<6}")
    print("-" * 82)
    print(f"Assessment accuracy: {correct}/{n} = {correct / n * 100:.0f}%"
          f"    (easy {ec}/{en}, hard {hc}/{hn})")
    print(f"Avg rationale — grounded: {avg('grounded'):.2f}/5   "
          f"avoids-serious-trap: {avg('avoids_serious_trap'):.2f}/5")
    print("=" * 82)

    stamp = time.strftime("%Y%m%d_%H%M%S")
    with open(f"agent_eval_{stamp}.json", "w") as f:
        json.dump({"accuracy": correct / n, "rows": rows}, f, indent=2)
    print(f"Saved agent_eval_{stamp}.json — this is your agent baseline.")


if __name__ == "__main__":
    main()
