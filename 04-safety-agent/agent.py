"""
agent.py — a minimal tool-use AGENT for pharmacovigilance safety signals.

THE ONE NEW IDEA (vs Projects 1 & 2):
  Project 1/2 = ONE Claude call -> one answer. A straight line.
  Agent       = Claude runs in a LOOP. It decides to CALL A TOOL, sees the
                result, reasons, maybe calls another tool, and stops when it
                has enough to answer. You hand it CAPABILITIES, not a script —
                the model plans the steps itself.

Tool today: get_adverse_events(drug) -> hits openFDA (real FDA FAERS data)
and returns the most-reported adverse reactions for that drug, with counts.

RUN:
  pip install anthropic requests python-dotenv
  # put your key in a .env file (same folder):  ANTHROPIC_API_KEY=sk-ant-...
  python agent.py atorvastatin
"""

import os
import sys
import json
import re
import math
import requests
import anthropic
from typing import Literal, List, Optional
from pydantic import BaseModel, ValidationError
from dotenv import load_dotenv

load_dotenv(override=True)              # .env wins even if a stale key is set in the shell
client = anthropic.Anthropic()          # picks up ANTHROPIC_API_KEY from there
MODEL = "claude-opus-4-8"
OPENFDA = "https://api.fda.gov/drug/event.json"   # no API key needed for light use


# ===========================================================================
# 0. THE VERDICT SCHEMA  — the machine-readable answer the agent must produce.
#    A label commits; an essay can hedge forever. This is what an eval scores.
# ===========================================================================
class Verdict(BaseModel):
    drug: str
    assessment: Literal["signal", "no-signal", "insufficient-data"]
    confidence: Literal["high", "medium", "low"]
    notable_reactions: List[str]
    serious_fraction: Optional[float] = None
    # Exact disproportionality rows computed by the tool and attached by the loop
    # (not reproduced by the model, so the numbers can't drift).
    signals: Optional[List[dict]] = None
    rationale: str


def extract_json(text: str) -> str:
    """Strip markdown code fences Claude sometimes wraps JSON in (Project-1 pattern)."""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text)
    return text


# ===========================================================================
# 1. THE TOOL  — just a normal Python function. Nothing magic.
# ===========================================================================
def get_adverse_events(drug: str, limit: int = 10) -> dict:
    """Top reported adverse reactions for a drug from openFDA (FAERS)."""
    params = {
        "search": f'patient.drug.openfda.generic_name:"{drug}"',
        "count": "patient.reaction.reactionmeddrapt.exact",   # rank reactions by frequency
    }
    r = requests.get(OPENFDA, params=params, timeout=30)
    if r.status_code == 404:
        return {"drug": drug, "top_reactions": [], "note": "no records for this generic name"}
    r.raise_for_status()
    results = r.json().get("results", [])
    top = [{"reaction": x["term"], "reports": x["count"]} for x in results[:limit]]
    return {"drug": drug, "top_reactions": top}


def _count(search: str) -> int:
    """Helper: how many FAERS reports match this openFDA search query."""
    r = requests.get(OPENFDA, params={"search": search, "limit": 1}, timeout=30)
    if r.status_code == 404:
        return 0                              # openFDA returns 404 when zero matches
    r.raise_for_status()
    return r.json().get("meta", {}).get("results", {}).get("total", 0)


def get_serious_event_count(drug: str) -> dict:
    """How many of a drug's FAERS reports were flagged SERIOUS, vs the total."""
    base = f'patient.drug.openfda.generic_name:"{drug}"'
    total = _count(base)
    serious = _count(base + " AND serious:1")     # serious:1 = serious in FAERS
    fraction = round(serious / total, 3) if total else None
    return {"drug": drug, "serious_reports": serious,
            "total_reports": total, "serious_fraction": fraction}


def get_serious_reactions(drug: str, limit: int = 10) -> dict:
    """Top reactions AMONG SERIOUS reports only. Surfaces low-volume but critical
    events (e.g. GI haemorrhage) that the overall top-10 buries under minor noise."""
    params = {
        "search": f'patient.drug.openfda.generic_name:"{drug}" AND serious:1',
        "count": "patient.reaction.reactionmeddrapt.exact",
    }
    r = requests.get(OPENFDA, params=params, timeout=30)
    if r.status_code == 404:
        return {"drug": drug, "top_serious_reactions": []}
    r.raise_for_status()
    results = r.json().get("results", [])
    top = [{"reaction": x["term"], "reports": x["count"]} for x in results[:limit]]
    return {"drug": drug, "top_serious_reactions": top}


# ---------------------------------------------------------------------------
# THE COMPUTE-A-DECISION TOOL — real disproportionality math, not a fraction.
#
#   The other three tools are document/count-in, structured-out. This one does
#   the actual PV signal-detection statistics regulators use: it builds the 2x2
#   contingency table for a drug-reaction pair from openFDA marginals and returns
#   PRR, ROR, and the Information Component (IC, a BCPNN-style shrinkage measure
#   that behaves like EBGM for our purpose — it stays near 0 when counts are too
#   small to trust), each with a 95% interval, plus standard signal flags.
#
#   True EBGM needs a gamma-Poisson prior fitted across the WHOLE database; that
#   can't be done from a handful of per-query calls, so IC (which has an analytic
#   shrinkage) is the honest, computable stand-in. Flagged as such, not faked.
# ---------------------------------------------------------------------------
_FAERS_TOTAL = {"N": None}   # cache the all-reports denominator within a process


def _meta_total(search: str = None) -> int:
    """Total number of FAERS reports matching `search` (all reports if None)."""
    params = {"limit": 1}
    if search:
        params["search"] = search
    r = requests.get(OPENFDA, params=params, timeout=30)
    if r.status_code == 404:
        return 0
    r.raise_for_status()
    return r.json().get("meta", {}).get("results", {}).get("total", 0)


def _faers_total() -> int:
    if _FAERS_TOTAL["N"] is None:
        _FAERS_TOTAL["N"] = _meta_total()
    return _FAERS_TOTAL["N"]


def compute_disproportionality(drug: str, reaction: str) -> dict:
    """PRR / ROR / IC for ONE drug-reaction pair, from a 2x2 FAERS table.

      a = reports with BOTH drug and reaction     b = drug reports without it
      c = reaction reports with OTHER drugs        d = all other reports
    """
    base = f'patient.drug.openfda.generic_name:"{drug}"'
    ev = f'patient.reaction.reactionmeddrapt.exact:"{reaction}"'
    try:
        a = float(_meta_total(f"{base} AND {ev}"))
        n_drug = _meta_total(base)
        n_event = _meta_total(ev)
        N = _faers_total()
    except Exception as e:
        return {"drug": drug, "reaction": reaction, "error": str(e)}

    if not N or not n_drug or not n_event or a < 1:
        return {"drug": drug, "reaction": reaction, "a": int(a),
                "note": "insufficient counts for a stable estimate"}

    b, c, d = n_drug - a, n_event - a, N - n_drug - n_event + a
    if min(b, c, d) < 0:
        return {"drug": drug, "reaction": reaction, "note": "inconsistent marginals from openFDA"}

    E = (n_drug * n_event) / N   # expected count under independence

    def _ci(log_val, se):
        return [round(math.exp(log_val - 1.96 * se), 2), round(math.exp(log_val + 1.96 * se), 2)]

    out = {"drug": drug, "reaction": reaction, "a": int(a), "b": int(b),
           "c": int(c), "d": int(d), "expected": round(E, 2)}

    prr = (a / (a + b)) / (c / (c + d))
    prr_se = math.sqrt(1 / a - 1 / (a + b) + 1 / c - 1 / (c + d))
    out["PRR"] = round(prr, 2)
    out["PRR_CI95"] = _ci(math.log(prr), prr_se)

    if b > 0 and d > 0:
        ror = (a * d) / (b * c)
        ror_se = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
        out["ROR"] = round(ror, 2)
        out["ROR_CI95"] = _ci(math.log(ror), ror_se)

    denom = (a + b) * (c + d) * (a + c) * (b + d)
    chi2 = (N * (abs(a * d - b * c) - N / 2) ** 2 / denom) if denom > 0 and abs(a * d - b * c) > N / 2 else 0.0
    out["chi2_yates"] = round(chi2, 2)

    ic = math.log2((a + 0.5) / (E + 0.5))
    ic_var = (1 / math.log(2) ** 2) * ((N - a) / (a * (1 + N))
             + (N - n_drug) / (n_drug * (1 + N)) + (N - n_event) / (n_event * (1 + N)))
    out["IC"] = round(ic, 2)
    out["IC_CI95"] = [round(ic - 2 * math.sqrt(ic_var), 2), round(ic + 2 * math.sqrt(ic_var), 2)]

    # Standard signal criteria. Note the a>=3 guard: a huge ratio on 1-2 reports
    # is noise, so it must NOT flag — the intervals/shrinkage enforce that.
    out["signal_PRR"] = bool(out["PRR"] >= 2 and chi2 >= 4 and a >= 3)      # Evans 2001
    out["signal_ROR"] = bool(out.get("ROR_CI95", [0])[0] > 1 and a >= 3)
    out["signal_IC"] = bool(out["IC_CI95"][0] > 0)
    out["signal"] = bool(out["signal_PRR"] or out["signal_ROR"] or out["signal_IC"])
    return out


# ===========================================================================
# 2. THE TOOL SCHEMAS  — how the MODEL learns the tools exist and how to call them.
#    The description is prompt engineering: it tells Claude WHEN to use each.
# ===========================================================================
TOOLS = [
    {
        "name": "get_adverse_events",
        "description": (
            "Get the most frequently reported adverse reactions for a drug from the "
            "FDA FAERS database (openFDA). Call this to see WHICH reactions are reported. "
            "Input is a generic drug name."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "drug": {"type": "string", "description": "Generic drug name, e.g. 'atorvastatin'"}
            },
            "required": ["drug"],
        },
    },
    {
        "name": "get_serious_event_count",
        "description": (
            "Get how many of a drug's FAERS reports were flagged SERIOUS, and the total "
            "report count, so you can judge the PROPORTION that were serious. Call this to "
            "gauge severity, not just which reactions occur. Input is a generic drug name."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "drug": {"type": "string", "description": "Generic drug name, e.g. 'atorvastatin'"}
            },
            "required": ["drug"],
        },
    },
    {
        "name": "get_serious_reactions",
        "description": (
            "Get the top reactions AMONG SERIOUS reports only. This surfaces critical events "
            "(e.g. gastrointestinal haemorrhage) that the overall breakdown buries under "
            "high-volume minor complaints. Use this to identify SPECIFIC serious signals "
            "before deciding 'signal'. Input is a generic drug name."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "drug": {"type": "string", "description": "Generic drug name, e.g. 'aspirin'"}
            },
            "required": ["drug"],
        },
    },
    {
        "name": "compute_disproportionality",
        "description": (
            "Compute REAL signal-detection statistics for one drug-reaction pair: PRR, ROR, "
            "and the Information Component (IC, a shrinkage measure) with 95% intervals and "
            "signal flags, from the 2x2 FAERS contingency table. This is what decides whether "
            "a reaction is genuinely disproportionate vs. just frequent. Call it on the 2-4 "
            "most clinically concerning SERIOUS reactions after get_serious_reactions. Inputs "
            "are a generic drug name and one reaction term (MedDRA PT, as returned by the other "
            "tools, e.g. 'RHABDOMYOLYSIS')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "drug": {"type": "string", "description": "Generic drug name, e.g. 'atorvastatin'"},
                "reaction": {"type": "string", "description": "Reaction term, e.g. 'RHABDOMYOLYSIS'"},
            },
            "required": ["drug", "reaction"],
        },
    },
]

# Registry: tool name -> the Python function that actually runs it.
# Add a new tool = write a function + a schema + one line here. The LOOP never changes.
TOOL_FUNCS = {
    "get_adverse_events": get_adverse_events,
    "get_serious_event_count": get_serious_event_count,
    "get_serious_reactions": get_serious_reactions,
    "compute_disproportionality": compute_disproportionality,
}

SYSTEM = """You are a pharmacovigilance assistant that produces a structured safety verdict.

STEP 1 — Gather data first:
  - get_adverse_events      -> WHICH reactions are reported overall (the breakdown)
  - get_serious_event_count -> HOW SERIOUS (what fraction of reports were serious)
  - get_serious_reactions   -> WHICH reactions appear among SERIOUS reports specifically

STEP 2 — QUANTIFY the candidates. For the 2-4 most clinically concerning serious reactions
from get_serious_reactions, call compute_disproportionality(drug, reaction). This returns the
real signal-detection statistics — PRR, ROR, and IC with 95% intervals and signal flags. A
reaction is a genuine signal only when it is DISPROPORTIONATE, not merely frequent.

STEP 3 — When you have the data, reply with ONLY valid JSON (no prose, no markdown fences),
matching exactly:
{
  "drug": "<name>",
  "assessment": "signal" | "no-signal" | "insufficient-data",
  "confidence": "high" | "medium" | "low",
  "notable_reactions": ["<reaction>", ...],
  "serious_fraction": <number 0-1, or null>,
  "rationale": "<2-3 sentences, citing the disproportionality of specific reactions>"
}
(Do NOT put the statistics in the JSON — the exact PRR/ROR/IC rows are attached automatically.)

RULES (read carefully):
- Decide "signal" from the DISPROPORTIONALITY results: a reaction flags when PRR>=2 with
  chi-square>=4 and at least 3 reports, or the IC lower bound is above 0. A large ratio built
  on 1-2 reports is noise, not a signal.
- FAERS OVER-REPORTS serious events, so a high serious_fraction (even 60-90%) is NORMAL and is
  NOT by itself a signal. Never justify a verdict with the serious_fraction.
- Use "insufficient-data" when the tools return little or no data.
- Never invent reactions; ground everything in the tool results.
- This is reported-frequency data, not proven causation — let that lower your confidence."""


# ===========================================================================
# 3. THE AGENT LOOP  — the whole new mechanic, ~15 lines.
# ===========================================================================
def run_agent(user_question: str, max_turns: int = 5) -> str:
    messages = [{"role": "user", "content": user_question}]
    signal_rows = []   # exact compute_disproportionality outputs, attached to the verdict

    for turn in range(1, max_turns + 1):
        print(f"\n--- turn {turn} ---")
        resp = client.messages.create(
            model=MODEL, max_tokens=1024, system=SYSTEM,
            tools=TOOLS, messages=messages,
        )
        # Record the model's turn (may contain text and/or tool_use blocks).
        messages.append({"role": "assistant", "content": resp.content})

        # STOPPING CONDITION: if the model didn't ask for a tool, it's done —
        # and its final turn should be the JSON verdict. Parse + validate it.
        if resp.stop_reason != "tool_use":
            raw = "".join(b.text for b in resp.content if b.type == "text")
            try:
                verdict = Verdict(**json.loads(extract_json(raw)))
                # Attach the exact statistics the tool computed (not model-reproduced).
                if signal_rows and not verdict.signals:
                    verdict.signals = signal_rows
                print("\n=== VERDICT ===")
                print(json.dumps(verdict.model_dump(), indent=2))
                return verdict
            except (json.JSONDecodeError, ValidationError) as e:
                # Same defensive posture as Project 1: fail loudly, show the raw output.
                print("\n[verdict parse failed] " + str(e))
                print("raw:\n" + raw[:500])
                return None

        # Otherwise: run every tool the model asked for, collect the results.
        tool_results = []
        for block in resp.content:
            if block.type == "tool_use":
                print(f"[tool call] {block.name}({block.input})")
                try:
                    result = TOOL_FUNCS[block.name](**block.input)
                except Exception as e:
                    result = {"error": str(e)}
                if block.name == "compute_disproportionality" and "error" not in result:
                    signal_rows.append(result)
                print(f"[tool result] {json.dumps(result)[:200]}...")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                })

        # Feed the results back as the next 'user' turn -> the loop continues,
        # and now the model can reason over real data (or call another tool).
        messages.append({"role": "user", "content": tool_results})

    print("\n[stopped: hit max_turns without a final answer]")
    return ""


if __name__ == "__main__":
    drug = sys.argv[1] if len(sys.argv) > 1 else "atorvastatin"
    run_agent(f"Are there any notable safety signals for {drug}? Use the tool to check the FDA data.")
