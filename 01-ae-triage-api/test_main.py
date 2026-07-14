import io
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# ── Test 1: Root endpoint ──────────────────────────────────────────
def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "status" in response.json()

# ── Test 2: Empty input returns 400 ───────────────────────────────
def test_empty_report_returns_400():
    response = client.post("/triage", json={"report": ""})
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()

# ── Test 3: Valid report returns correct structure ─────────────────
def test_valid_triage_returns_structure():
    response = client.post("/triage", json={
        "report": "Patient was hospitalised after severe reaction to Penicillin."
    })
    assert response.status_code == 200
    data = response.json()
    # Check all required fields are present
    assert "seriousness" in data
    assert "suspected_drug" in data
    assert "event" in data
    assert "summary" in data
    assert "confidence" in data
    # Check values are within expected ranges
    assert data["seriousness"] in ["serious", "non-serious", "unknown"]
    assert data["confidence"] in ["high", "medium", "low"]

# ── Test 4: Serious case is flagged correctly ──────────────────────
def test_hospitalisation_flagged_as_serious():
    response = client.post("/triage", json={
        "report": "68-year-old male admitted to ICU after cardiac arrest following Metoprolol overdose."
    })
    assert response.status_code == 200
    assert response.json()["seriousness"] == "serious"

# ── Test 5: Batch — missing column returns 400 ────────────────────
def test_batch_missing_column_returns_400():
    csv_content = "id,text\n1,some report"   # 'report' column missing
    response = client.post(
        "/triage/batch",
        files={"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    )
    assert response.status_code == 400

# ── Test 6: Batch — valid CSV returns list ────────────────────────
def test_batch_valid_csv():
    csv_content = (
        "id,report\n"
        "1,Patient developed rash after Ibuprofen.\n"
        "2,Patient died after Warfarin overdose.\n"
    )
    response = client.post(
        "/triage/batch",
        files={"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # Death should be flagged serious
    assert data[1]["seriousness"] == "serious"