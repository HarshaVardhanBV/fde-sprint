import os
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import anthropic

app = FastAPI(title="AE Triage API")
client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env automatically

# --- Request & Response schemas ---

class TriageRequest(BaseModel):
    report: str  # raw free-text AE report

class TriageResponse(BaseModel):
    seriousness: str        # "serious" | "non-serious" | "unknown"
    suspected_drug: str     # drug name or "unknown"
    event: str              # what happened, in clean 1-line
    summary: str            # 2-sentence plain-English summary
    confidence: str         # "high" | "medium" | "low"

# --- The triage logic ---

SYSTEM_PROMPT = """You are a pharmacovigilance specialist.
Given a free-text adverse event report, extract structured information.

Return ONLY valid JSON with these exact keys:
{
  "seriousness": "serious" | "non-serious" | "unknown",
  "suspected_drug": "<drug name or unknown>",
  "event": "<1-line description of what happened>",
  "summary": "<2-sentence plain English summary>",
  "confidence": "high" | "medium" | "low"
}

Seriousness criteria (ICH E2A): death, life-threatening, hospitalization,
disability, congenital anomaly, or medically important = serious.
"""

@app.post("/triage", response_model=TriageResponse)
def triage_ae_report(request: TriageRequest):
    if not request.report.strip():
        raise HTTPException(status_code=400, detail="Report text cannot be empty")

    message = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": f"AE Report:\n{request.report}"}
        ]
    )

    raw = message.content[0].text

    try:
        data = json.loads(raw)
        return TriageResponse(**data)
    except (json.JSONDecodeError, KeyError) as e:
        raise HTTPException(
            status_code=500,
            detail=f"Claude returned unexpected format: {raw[:200]}"
        )

@app.get("/")
def root():
    return {"status": "AE Triage API running", "docs": "/docs"}