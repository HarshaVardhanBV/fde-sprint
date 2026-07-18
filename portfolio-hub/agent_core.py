"""
agent_core.py — the safety-signal agent, importable by the Streamlit hub.

Mirrors 04-safety-agent/agent.py (same 3 tools + tool-use loop), but adapted for
a UI: no CLI prints, the client is created lazily (so the key can be set at
runtime from Streamlit secrets), and run_agent() returns (verdict, trace) so the
UI can show which tools the agent chose to call.

NOTE: this is a copy of the agent for deployment convenience. If you change the
agent's behaviour, update BOTH this and 04-safety-agent/agent.py.
"""

import os
import re
import json
import math
import requests
import anthropic
from typing import Literal, List, Optional
from pydantic import BaseModel, ValidationError

MODEL = "claude-opus-4-8"
OPENFDA = "https://api.fda.gov/drug/event.json"


# ---- Verdict schema -------------------------------------------------------
class Verdict(BaseModel):
    drug: str
    assessment: Literal["signal", "no-signal", "insufficient-data"]
    confidence: Literal["high", "medium", "low"]
    notable_reactions: List[str]
    serious_fraction: Optional[float] = None
    signals: Optional[List[dict]] = None   # exact PRR/ROR/IC rows attached by the loop
    rationale: str


def extract_json(text: str) -> str:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    return re.sub(r"\s*```$", "", text)


# ---- Tools ----------------------------------------------------------------
def get_adverse_events(drug: str, limit: int = 10) -> dict:
    params = {"search": f'patient.drug.openfda.generic_name:"{drug}"',
              "count": "patient.reaction.reactionmeddrapt.exact"}
    r = requests.get(OPENFDA, params=params, timeout=30)
    if r.status_code == 404:
        return {"drug": drug, "top_reactions": [], "note": "no records for this generic name"}
    r.raise_for_status()
    results = r.json().get("results", [])
    return {"drug": drug, "top_reactions": [{"reaction": x["term"], "reports": x["count"]} for x in results[:limit]]}


def _count(search: str) -> int:
    r = requests.get(OPENFDA, params={"search": search, "limit": 1}, timeout=30)
    if r.status_code == 404:
        return 0
    r.raise_for_status()
    return r.json().get("meta", {}).get("results", {}).get("total", 0)


def get_serious_event_count(drug: str) -> dict:
    base = f'patient.drug.openfda.generic_name:"{drug}"'
    total = _count(base)
    serious = _count(base + " AND serious:1")
    fraction = round(serious / total, 3) if total else None
    return {"drug": drug, "serious_reports": serious, "total_reports": total, "serious_fraction": fraction}


def get_serious_reactions(drug: str, limit: int = 10) -> dict:
    params = {"search": f'patient.drug.openfda.generic_name:"{drug}" AND serious:1',
              "count": "patient.reaction.reactionmeddrapt.exact"}
    r = requests.get(OPENFDA, params=params, timeout=30)
    if r.status_code == 404:
        return {"drug": drug, "top_serious_reactions": []}
    r.raise_for_status()
    results = r.json().get("results", [])
    return {"drug": drug, "top_serious_reactions": [{"reaction": x["term"], "reports": x["count"]} for x in results[:limit]]}


# ---- Disproportionality: real PV signal-detection math (PRR / ROR / IC) ----
# Mirrors 04-safety-agent/agent.py::compute_disproportionality. IC is a BCPNN-style
# shrinkage measure standing in for EBGM (true EBGM needs a whole-database prior).
_FAERS_TOTAL = {"N": None}


def _meta_total(search: str = None) -> int:
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

    E = (n_drug * n_event) / N

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

    out["signal_PRR"] = bool(out["PRR"] >= 2 and chi2 >= 4 and a >= 3)
    out["signal_ROR"] = bool(out.get("ROR_CI95", [0])[0] > 1 and a >= 3)
    out["signal_IC"] = bool(out["IC_CI95"][0] > 0)
    out["signal"] = bool(out["signal_PRR"] or out["signal_ROR"] or out["signal_IC"])
    return out


TOOLS = [
    {"name": "get_adverse_events",
     "description": "Get the most frequently reported adverse reactions for a drug (openFDA FAERS). Overall breakdown.",
     "input_schema": {"type": "object", "properties": {"drug": {"type": "string"}}, "required": ["drug"]}},
    {"name": "get_serious_event_count",
     "description": "How many of a drug's FAERS reports were flagged SERIOUS vs the total (the serious fraction).",
     "input_schema": {"type": "object", "properties": {"drug": {"type": "string"}}, "required": ["drug"]}},
    {"name": "get_serious_reactions",
     "description": "Top reactions AMONG SERIOUS reports only. Surfaces critical events buried under minor noise.",
     "input_schema": {"type": "object", "properties": {"drug": {"type": "string"}}, "required": ["drug"]}},
    {"name": "compute_disproportionality",
     "description": "Real signal-detection stats (PRR, ROR, IC with 95% intervals + flags) for one drug-reaction "
                    "pair from the 2x2 FAERS table. Call on the 2-4 most concerning serious reactions. A reaction "
                    "is a signal only if DISPROPORTIONATE, not merely frequent.",
     "input_schema": {"type": "object",
                      "properties": {"drug": {"type": "string"}, "reaction": {"type": "string"}},
                      "required": ["drug", "reaction"]}},
]

TOOL_FUNCS = {"get_adverse_events": get_adverse_events,
              "get_serious_event_count": get_serious_event_count,
              "get_serious_reactions": get_serious_reactions,
              "compute_disproportionality": compute_disproportionality}

SYSTEM = """You are a pharmacovigilance assistant that produces a structured safety verdict.

STEP 1 — Gather data:
  - get_adverse_events      -> WHICH reactions are reported overall
  - get_serious_event_count -> HOW SERIOUS (fraction of reports that were serious)
  - get_serious_reactions   -> WHICH reactions appear among SERIOUS reports specifically

STEP 2 — QUANTIFY. For the 2-4 most clinically concerning serious reactions, call
compute_disproportionality(drug, reaction) to get PRR / ROR / IC with 95% intervals and
signal flags. A reaction is a real signal only when DISPROPORTIONATE, not merely frequent.

STEP 3 — Reply with ONLY valid JSON (no prose, no fences):
{
  "drug": "<name>",
  "assessment": "signal" | "no-signal" | "insufficient-data",
  "confidence": "high" | "medium" | "low",
  "notable_reactions": ["<reaction>", ...],
  "serious_fraction": <number 0-1, or null>,
  "rationale": "<2-3 sentences, citing the disproportionality of specific reactions>"
}
(Do NOT put the statistics in the JSON — the exact rows are attached automatically.)

RULES:
- Decide "signal" from the disproportionality results (PRR>=2 with chi-square>=4 and >=3 reports,
  or IC lower bound >0). A big ratio on 1-2 reports is noise, not a signal.
- A high serious_fraction (even 60-90%) is NORMAL for FAERS and is NEVER by itself a signal.
- "insufficient-data" when the tools return little or no data. Never invent reactions.
- Reported-frequency data, not proven causation — let that lower confidence."""


def run_agent(drug: str, max_turns: int = 5):
    """Returns (verdict: Verdict|None, trace: list[str]). No printing."""
    client = anthropic.Anthropic()   # lazy: reads ANTHROPIC_API_KEY set by the caller
    messages = [{"role": "user",
                 "content": f"Assess the safety signals for {drug} using the tools."}]
    trace = []
    signal_rows = []   # exact compute_disproportionality outputs, attached to the verdict

    for _ in range(max_turns):
        resp = client.messages.create(model=MODEL, max_tokens=1024, system=SYSTEM,
                                      tools=TOOLS, messages=messages)
        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason != "tool_use":
            raw = "".join(b.text for b in resp.content if b.type == "text")
            try:
                verdict = Verdict(**json.loads(extract_json(raw)))
                if signal_rows and not verdict.signals:
                    verdict.signals = signal_rows
                return verdict, trace
            except (json.JSONDecodeError, ValidationError):
                return None, trace

        tool_results = []
        for block in resp.content:
            if block.type == "tool_use":
                label = ", ".join(str(v) for v in block.input.values())
                trace.append(f"{block.name}({label})")
                try:
                    result = TOOL_FUNCS[block.name](**block.input)
                except Exception as e:
                    result = {"error": str(e)}
                if block.name == "compute_disproportionality" and "error" not in result:
                    signal_rows.append(result)
                tool_results.append({"type": "tool_result", "tool_use_id": block.id,
                                     "content": json.dumps(result)})
        messages.append({"role": "user", "content": tool_results})

    return None, trace
