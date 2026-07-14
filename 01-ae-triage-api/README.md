# AE Triage API

A FastAPI service that uses Claude (Anthropic) to triage free-text adverse event (AE) reports into structured pharmacovigilance data — applying ICH E2A seriousness criteria automatically.

**Live API:** https://fde-sprint-production.up.railway.app  
**Interactive docs:** https://fde-sprint-production.up.railway.app/docs

---

## What it does

PV teams receive thousands of free-text AE reports daily. Manual triage is slow and inconsistent. This API takes a raw report and returns clean, structured JSON in under 2 seconds:

```json
{
  "seriousness": "serious",
  "suspected_drug": "Aspirin",
  "event": "Severe chest pain and shortness of breath requiring hospitalisation",
  "summary": "A 68-year-old female experienced severe chest pain 2 hours after taking Aspirin 500mg. She required hospital admission, meeting the ICH E2A seriousness criterion of hospitalisation.",
  "confidence": "high"
}
```

---

## Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Health check |
| POST | `/triage` | Triage a single free-text AE report |
| POST | `/triage/batch` | Upload a CSV and triage all reports in one call |

---

## Quick start

### Single report
```bash
curl -X POST "https://fde-sprint-production.up.railway.app/triage" \
  -H "Content-Type: application/json" \
  -d '{"report": "Patient was hospitalised after severe allergic reaction to Penicillin."}'
```

### Batch (CSV)
```bash
curl -X POST "https://fde-sprint-production.up.railway.app/triage/batch" \
  -F "file=@sample_aes.csv"
```

CSV format — must have a `report` column:
id,report
1,"Patient developed rash after Ibuprofen."
2,"68-year-old admitted to ICU after cardiac arrest."


---

## Run locally

```bash
git clone https://github.com/HarshaVardhanBV/fde-sprint.git
cd fde-sprint/AE_Triage
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
echo "ANTHROPIC_API_KEY=your-key-here" > .env
uvicorn main:app --reload
```

Visit `http://127.0.0.1:8000/docs` for the interactive UI.

---

## Run tests

```bash
pytest test_main.py -v
```

6 tests covering: root endpoint, input validation, structured output schema, ICH E2A seriousness logic, batch CSV validation, batch results.

---

## Design decisions

**Schema-first:** Input and output models defined with Pydantic before any prompt was written. The schema is the contract — FastAPI enforces it on both sides.

**Structured output via system prompt:** Claude is instructed to return only valid JSON matching the output schema. A `extract_json()` helper strips markdown fences Claude occasionally adds — defensive parsing so one bad response never crashes the API.

**Error handling:** `400` on bad input (caller's fault), `500` with raw Claude output on parse failure (prompt debugging, not code debugging).

**Batch resilience:** Per-row exception handling — one malformed report skips, never kills the whole batch.

---

## Stack

- **FastAPI** — typed API framework, auto-generates `/docs` UI
- **Anthropic SDK** — Claude claude-opus-4-8 for structured extraction
- **Pydantic** — input/output validation
- **pytest** — 6-test suite
- **Railway** — deployed, auto-deploys on push to main