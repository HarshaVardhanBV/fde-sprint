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
]

TOOL_FUNCS = {"get_adverse_events": get_adverse_events,
              "get_serious_event_count": get_serious_event_count,
              "get_serious_reactions": get_serious_reactions}

SYSTEM = """You are a pharmacovigilance assistant that produces a structured safety verdict.

STEP 1 — Gather data first, using ALL THREE tools:
  - get_adverse_events      -> WHICH reactions are reported overall
  - get_serious_event_count -> HOW SERIOUS (fraction of reports that were serious)
  - get_serious_reactions   -> WHICH reactions appear among SERIOUS reports specifically
Base "signal" decisions primarily on get_serious_reactions: the overall top-10 is dominated
by high-volume minor complaints, so a critical event (e.g. GI haemorrhage) can be a real
signal even when it is NOT in the overall top-10.

STEP 2 — When you have the data, reply with ONLY valid JSON (no prose, no fences):
{
  "drug": "<name>",
  "assessment": "signal" | "no-signal" | "insufficient-data",
  "confidence": "high" | "medium" | "low",
  "notable_reactions": ["<reaction>", ...],
  "serious_fraction": <number 0-1, or null>,
  "rationale": "<2-3 sentences, grounded ONLY in the tool data>"
}

RULES:
- "signal" ONLY when specific serious reactions stand out consistent with a known/plausible risk.
- A high serious_fraction (even 60-90%) is NORMAL for FAERS and is NOT by itself a signal.
- "insufficient-data" when the tools return little or no data. Never invent reactions.
- Reported-frequency data, not proven causation — let that lower confidence."""


def run_agent(drug: str, max_turns: int = 5):
    """Returns (verdict: Verdict|None, trace: list[str]). No printing."""
    client = anthropic.Anthropic()   # lazy: reads ANTHROPIC_API_KEY set by the caller
    messages = [{"role": "user",
                 "content": f"Assess the safety signals for {drug} using the tools."}]
    trace = []

    for _ in range(max_turns):
        resp = client.messages.create(model=MODEL, max_tokens=1024, system=SYSTEM,
                                      tools=TOOLS, messages=messages)
        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason != "tool_use":
            raw = "".join(b.text for b in resp.content if b.type == "text")
            try:
                return Verdict(**json.loads(extract_json(raw))), trace
            except (json.JSONDecodeError, ValidationError):
                return None, trace

        tool_results = []
        for block in resp.content:
            if block.type == "tool_use":
                trace.append(f"{block.name}({block.input.get('drug', '')})")
                try:
                    result = TOOL_FUNCS[block.name](**block.input)
                except Exception as e:
                    result = {"error": str(e)}
                tool_results.append({"type": "tool_result", "tool_use_id": block.id,
                                     "content": json.dumps(result)})
        messages.append({"role": "user", "content": tool_results})

    return None, trace
