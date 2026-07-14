"""AE Triage page — calls the live FastAPI backend on Railway."""
import requests
import pandas as pd
import streamlit as st

API = st.secrets.get("TRIAGE_API", "https://fde-sprint-production.up.railway.app")

st.set_page_config(page_title="AE Triage", page_icon="🩺")
st.title("🩺 Adverse-Event Triage")
st.caption("Backend: FastAPI on Railway · Pydantic-validated · ICH E2A seriousness criteria")

tab_single, tab_batch = st.tabs(["Single report", "Batch CSV"])

# ── Single report ────────────────────────────────────────────────────────────
with tab_single:
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

# ── Batch CSV ────────────────────────────────────────────────────────────────
with tab_batch:
    st.markdown(
        "Upload a CSV with an **`id`** column and a **`report`** column. "
        "The API triages every row and returns structured results."
    )

    SAMPLE_CSV = (
        "id,report\n"
        '1,"68-year-old female developed severe chest pain after taking Aspirin 500mg. Hospitalised overnight."\n'
        '2,"Patient reports mild headache after Paracetamol 500mg. Resolved after 2 hours."\n'
        '3,"32-year-old male experienced anaphylactic shock after first dose of Amoxicillin."\n'
    )
    st.download_button("Download sample CSV", SAMPLE_CSV, "sample_aes.csv", "text/csv")

    uploaded = st.file_uploader("Upload CSV", type="csv")

    if uploaded and st.button("Run batch triage", type="primary"):
        with st.spinner("Triaging all rows…"):
            try:
                r = requests.post(
                    f"{API}/triage/batch",
                    files={"file": (uploaded.name, uploaded.getvalue(), "text/csv")},
                    timeout=120,
                )
            except Exception as e:
                st.error(f"Could not reach the API: {e}")
                st.stop()

        if r.status_code == 200:
            results = r.json()
            df = pd.DataFrame(results)
            def _color(val):
                return "color: red" if str(val).lower() == "serious" else "color: green"
            st.success(f"Triaged {len(df)} reports")
            st.dataframe(
                df.style.applymap(_color, subset=["seriousness"]),
                use_container_width=True,
            )
            st.download_button(
                "Download results CSV",
                df.to_csv(index=False).encode(),
                "triage_results.csv",
                "text/csv",
            )
            with st.expander("Raw JSON"):
                st.json(results)
        else:
            st.error(f"API error {r.status_code}: {r.text[:300]}")
