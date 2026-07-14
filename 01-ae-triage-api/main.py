from dotenv import load_dotenv
load_dotenv(override = True)

import os
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import anthropic

import re
import csv
import io
from fastapi import UploadFile, File
from typing import List


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



def extract_json(text: str) -> str:
    """Strip markdown code fences Claude sometimes adds."""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text)
    return text


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
        data = json.loads(extract_json(raw))
        return TriageResponse(**data)
    except (json.JSONDecodeError, KeyError) as e:
        raise HTTPException(
            status_code=500,
            detail=f"Claude returned unexpected format: {raw[:200]}"
        )



@app.post("/triage/batch", response_model=List[TriageResponse])
async def triage_batch(file: UploadFile = File(...)):
    # 1. Read and decode the uploaded CSV
    contents = await file.read()
    text = contents.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))

    # 2. Validate the CSV has a "report" column
    if "report" not in (reader.fieldnames or []):
        raise HTTPException(status_code=400, detail="CSV must have a 'report' column")

    # 3. Triage each row
    results = []
    for row in reader:
        report_text = row["report"].strip()
        if not report_text:
            continue  # skip empty rows

        message = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"AE Report:\n{report_text}"}]
        )

        raw = message.content[0].text
        try:
            data = json.loads(extract_json(raw))
            results.append(TriageResponse(**data))
        except (json.JSONDecodeError, KeyError):
            # Don't fail the whole batch for one bad row — skip it
            continue

    return results



@app.get("/")
def root():
    return {"status": "AE Triage API running", "docs": "/docs"}