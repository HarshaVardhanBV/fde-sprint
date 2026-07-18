"""AE Triage page — calls the live FastAPI backend on Railway, with a cached demo fallback."""
import requests
import pandas as pd
import streamlit as st

from demo_data import TRIAGE_EXAMPLES, TRIAGE_BATCH, EVAL_STATS, match_text

API = st.secrets.get("TRIAGE_API", "https://fde-sprint-production.up.railway.app")

st.set_page_config(page_title="AE Triage", page_icon="🩺")
st.title("🩺 Adverse-Event Triage")
st.caption("Free-text AE report → structured, seriousness-graded output. "
           "FastAPI on Railway · Pydantic-validated · ICH E2A · routed to Haiku (high-volume path).")

# --- Data source toggle: keeps the demo alive with no key / cold backend -----
mode = st.sidebar.radio(
    "Data source", ["Live", "Cached (demo)"],
    help="Cached serves canned example outputs so the page always renders — even with no "
         "API key/credits or a cold backend. A dead demo is worse than no demo.",
)
ev = EVAL_STATS["triage"]
st.sidebar.markdown(f"**Evaluated · {ev['headline']}**")
st.sidebar.caption(ev["detail"])
st.sidebar.caption(f"Source: `{ev['source']}`")


def render_single(d: dict):
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


tab_single, tab_batch = st.tabs(["Single report", "Batch CSV"])

# ── Single report ────────────────────────────────────────────────────────────
with tab_single:
    EXAMPLE = ("68-year-old female developed severe chest pain and shortness of breath "
               "after taking Aspirin 500mg, and was hospitalised overnight.")
    report = st.text_area("Adverse-event report", value=EXAMPLE, height=140)

    if st.button("Triage", type="primary") and report.strip():
        d = None
        if mode == "Live":
            with st.spinner("Calling the triage API..."):
                try:
                    r = requests.post(f"{API}/triage", json={"report": report}, timeout=60)
                    if r.status_code == 200:
                        d = r.json()
                    else:
                        st.warning(f"Live API returned {r.status_code}; showing a cached example.")
                except Exception as e:
                    st.warning(f"Live API unreachable ({e}); showing a cached example.")
        if d is None:
            d = match_text(TRIAGE_EXAMPLES, "report", report)["response"]
            st.info("Cached example output (demo mode).", icon="🗂️")
        render_single(d)

# ── Batch CSV ────────────────────────────────────────────────────────────────
with tab_batch:
    st.markdown(
        "Upload a CSV with an **`id`** column and a **`report`** column. "
        "The API triages every row **concurrently** and returns structured results."
    )

    SAMPLE_CSV = (
        "id,report\n"
        '1,"68-year-old female developed severe chest pain after taking Aspirin 500mg. Hospitalised overnight."\n'
        '2,"Patient reports mild headache after Paracetamol 500mg. Resolved after 2 hours."\n'
        '3,"32-year-old male experienced anaphylactic shock after first dose of Amoxicillin."\n'
    )
    st.download_button("Download sample CSV", SAMPLE_CSV, "sample_aes.csv", "text/csv")

    uploaded = st.file_uploader("Upload CSV", type="csv")

    if st.button("Run batch triage", type="primary"):
        results = None
        if mode == "Live" and uploaded:
            with st.spinner("Triaging all rows concurrently…"):
                try:
                    r = requests.post(
                        f"{API}/triage/batch",
                        files={"file": (uploaded.name, uploaded.getvalue(), "text/csv")},
                        timeout=120,
                    )
                    if r.status_code == 200:
                        results = r.json()
                    else:
                        st.warning(f"Live API returned {r.status_code}; showing cached results.")
                except Exception as e:
                    st.warning(f"Live API unreachable ({e}); showing cached results.")
        if results is None:
            results = TRIAGE_BATCH
            st.info("Cached batch output (demo mode).", icon="🗂️")

        df = pd.DataFrame(results)

        def _color(val):
            return "color: red" if str(val).lower() == "serious" else "color: green"

        st.success(f"Triaged {len(df)} reports")
        st.dataframe(df.style.applymap(_color, subset=["seriousness"]), use_container_width=True)
        st.download_button("Download results CSV", df.to_csv(index=False).encode(),
                           "triage_results.csv", "text/csv")
        with st.expander("Raw JSON"):
            st.json(results)
