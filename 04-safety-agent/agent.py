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
]

# Registry: tool name -> the Python function that actually runs it.
# Add a new tool = write a function + a schema + one line here. The LOOP never changes.
TOOL_FUNCS = {
    "get_adverse_events": get_adverse_events,
    "get_serious_event_count": get_serious_event_count,
    "get_serious_reactions": get_serious_reactions,
}

SYSTEM = """You are a pharmacovigilance assistant that produces a structured safety verdict.

STEP 1 — Gather data first, using ALL THREE tools:
  - get_adverse_events      -> WHICH reactions are reported overall (the breakdown)
  - get_serious_event_count -> HOW SERIOUS (what fraction of reports were serious)
  - get_serious_reactions   -> WHICH reactions appear among SERIOUS reports specifically
Base "signal" decisions primarily on get_serious_reactions: the overall top-10 is dominated
by high-volume minor complaints, so a critical event (e.g. GI haemorrhage) can be a real
signal even when it is NOT in the overall top-10. Look at the serious breakdown before deciding.

STEP 2 — When you have the data, reply with ONLY valid JSON (no prose, no markdown fences),
matching exactly:
{
  "drug": "<name>",
  "assessment": "signal" | "no-signal" | "insufficient-data",
  "confidence": "high" | "medium" | "low",
  "notable_reactions": ["<reaction>", ...],
  "serious_fraction": <number 0-1, or null>,
  "rationale": "<2-3 sentences, grounded ONLY in the tool data>"
}

RULES (read carefully):
- Call "signal" ONLY when specific serious reactions stand out that are consistent with a
  known or plausible drug risk — NOT merely because serious_fraction is high.
- FAERS OVER-REPORTS serious events, so a high serious_fraction (even 60-90%) is NORMAL and
  is NOT by itself a signal. Do not treat it as one.
- Use "insufficient-data" when the tools return little or no data.
- Never invent reactions; ground everything in the tool results.
- This is reported-frequency data, not proven causation — let that lower your confidence."""


# ===========================================================================
# 3. THE AGENT LOOP  — the whole new mechanic, ~15 lines.
# ===========================================================================
def run_agent(user_question: str, max_turns: int = 5) -> str:
    messages = [{"role": "user", "content": user_question}]

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
