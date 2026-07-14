"""AE Triage page — calls the live FastAPI backend on Railway."""
import requests
import streamlit as st

API = st.secrets.get("TRIAGE_API", "https://fde-sprint-production.up.railway.app")

st.set_page_config(page_title="AE Triage", page_icon="🩺")
st.title("🩺 Adverse-Event Triage")
st.caption("Paste a free-text adverse-event report → structured triage. Backend: FastAPI on Railway.")

EXAMPLE = ("68-year-old female developed severe chest pain and shortness of breath "
           "after taking Aspirin 500mg, and was hospitalised overnight.")

report = st.text_area("Adverse-event report", value=EXAMPLE, height=140)

if st.button("Triage", type="primary") and report.strip():
    with st.spinner("Calling the triage API..."):
        try:
            r = requests.post(f"{API}/triage", json={"report": report}, timeout=60)
        except Exception as e:
            st.error(f"Could not reach the API: {e}")
            st.stop()

    if r.status_code == 200:
        d = r.json()
        serious = str(d.get("seriousness", "")).lower()
        color = {"serious": "red", "non-serious": "green"}.get(serious, "gray")
        st.markdown(f"### Seriousness: :{color}[{d.get('seriousness', '?').upper()}]")
        a, b = st.columns(2)
        a.metric("Suspected drug", d.get("suspected_drug", "—"))
        b.metric("Confidence", d.get("confidence", "—"))
        st.write(f"**Event:** {d.get('event', '')}")
        st.write(f"**Summary:** {d.get('summary', '')}")
        with st.expander("Raw JSON"):
            st.json(d)
    elif r.status_code == 400:
        st.warning("The API rejected the input (400) — report cannot be empty.")
    else:
        st.error(f"API error {r.status_code}: {r.text[:300]}")

st.caption("Grounded in ICH E2A seriousness criteria. Structured output validated by Pydantic.")
