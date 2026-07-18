from dotenv import load_dotenv
load_dotenv(override = True)

import os
import json
import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import anthropic

import re
import csv
import io
from fastapi import UploadFile, File
from typing import List


app = FastAPI(title="AE Triage API")
client = anthropic.Anthropic()          # sync client for the single-report path
aclient = anthropic.AsyncAnthropic()    # async client for concurrent batch triage

# --- Model routing: pick the model by TASK, not one-size-fits-all -----------
# Triage is extraction + a bounded classification — the high-volume, low-judgment
# path. Route it to Haiku: ~10x cheaper and faster than Opus, with no quality loss
# on structured extraction. (Reserve Opus for genuine judgment, e.g. the safety
# agent's signal call.) Saying "I route by task" also signals production maturity.
TRIAGE_MODEL = "claude-haiku-4-5-20251001"
MAX_CONCURRENCY = 8                      # bound in-flight batch calls

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
        model=TRIAGE_MODEL,
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



async def _triage_one(report_text: str, sem: asyncio.Semaphore):
    """Triage a single report with the async client, bounded by a semaphore.
    Returns a TriageResponse, or None so one bad row never fails the batch."""
    async with sem:
        try:
            message = await aclient.messages.create(
                model=TRIAGE_MODEL,
                max_tokens=512,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": f"AE Report:\n{report_text}"}],
            )
            data = json.loads(extract_json(message.content[0].text))
            return TriageResponse(**data)
        except Exception:
            return None


@app.post("/triage/batch", response_model=List[TriageResponse])
async def triage_batch(file: UploadFile = File(...)):
    # 1. Read and decode the uploaded CSV
    contents = await file.read()
    text = contents.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))

    # 2. Validate the CSV has a "report" column
    if "report" not in (reader.fieldnames or []):
        raise HTTPException(status_code=400, detail="CSV must have a 'report' column")

    reports = [row["report"].strip() for row in reader if (row.get("report") or "").strip()]

    # 3. Triage all rows CONCURRENTLY (bounded), preserving input order.
    #    The old version was a sequential loop calling Opus per row — 500 rows
    #    would time out. gather() fans out; the semaphore caps in-flight calls.
    sem = asyncio.Semaphore(MAX_CONCURRENCY)
    results = await asyncio.gather(*[_triage_one(r, sem) for r in reports])
    return [r for r in results if r is not None]



@app.get("/")
def root():
    return {"status": "AE Triage API running", "docs": "/docs"}