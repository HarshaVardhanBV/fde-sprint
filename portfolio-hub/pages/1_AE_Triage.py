"""AE Triage page — calls the live FastAPI backend on Railway, with a cached demo fallback."""
import requests
import pandas as pd
import streamlit as st

import ui
from demo_data import TRIAGE_EXAMPLES, TRIAGE_BATCH, EVAL_STATS, match_text

ui.setup(
    page_title="AE Triage",
    icon_name="triage",
    title="Adverse-Event Triage",
    subtitle="Turn a free-text patient safety report into a structured, seriousness-graded record.",
)

API = st.secrets.get("TRIAGE_API", "https://fde-sprint-production.up.railway.app")

# --- Data source toggle: keeps the demo alive with no key / cold backend -----
mode = st.sidebar.radio(
    "Data source", ["Live", "Cached (demo)"],
    help="Cached serves saved example outputs so the page always renders — even with no "
         "connection or key. A dead demo is worse than no demo.",
)
ev = EVAL_STATS["triage"]
st.sidebar.markdown(f"**Evaluated · {ev['headline']}**")
st.sidebar.caption(ev["detail"])
st.sidebar.caption(f"Source: `{ev['source']}`")

ui.newcomer_note([
    "Paste a short written report of something that happened to a patient after taking a medicine.",
    "You get back whether it counts as **serious** (by an internationally agreed medical checklist), "
    "which medicine is suspected, and a plain one-line summary.",
    "**Red = serious** (needs fast, formal reporting). **Green = not serious.**",
    "In **Cached (demo)** mode it shows saved example results — nothing to set up.",
])


def render_single(d: dict):
    serious = str(d.get("seriousness", "")).lower()
    cls = {"serious": "red", "non-serious": "green"}.get(serious, "gray")
    st.markdown(
        f'<span class="pv-badge {cls}">{d.get("seriousness", "?").upper()}</span>',
        unsafe_allow_html=True,
    )
    st.write("")
    a, b = st.columns(2)
    a.metric("Suspected medicine", d.get("suspected_drug", "—"))
    b.metric("Confidence", d.get("confidence", "—"))
    st.write(f"**Event:** {d.get('event', '')}")
    st.write(f"**Summary:** {d.get('summary', '')}")
    with st.expander("Raw structured output"):
        st.json(d)


tab_single, tab_batch = st.tabs(["Single report", "Batch CSV"])

# ── Single report ────────────────────────────────────────────────────────────
with tab_single:
    EXAMPLE = ("68-year-old female developed severe chest pain and shortness of breath "
               "after taking Aspirin 500mg, and was hospitalised overnight.")
    report = st.text_area("Adverse-event report", value=EXAMPLE, height=140)

    if st.button("Triage report", type="primary") and report.strip():
        d = None
        if mode == "Live":
            with st.spinner("Processing the report..."):
                try:
                    r = requests.post(f"{API}/triage", json={"report": report}, timeout=60)
                    if r.status_code == 200:
                        d = r.json()
                    else:
                        st.warning(f"Live service returned {r.status_code}; showing a saved example.")
                except Exception as e:
                    st.warning(f"Live service unreachable ({e}); showing a saved example.")
        if d is None:
            d = match_text(TRIAGE_EXAMPLES, "report", report)["response"]
            st.info("Showing a saved example (demo mode).")
        render_single(d)

# ── Batch CSV ────────────────────────────────────────────────────────────────
with tab_batch:
    st.markdown(
        "Upload a CSV with an **`id`** column and a **`report`** column. "
        "Every row is processed together and returned as a structured table."
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
            with st.spinner("Processing all rows…"):
                try:
                    r = requests.post(
                        f"{API}/triage/batch",
                        files={"file": (uploaded.name, uploaded.getvalue(), "text/csv")},
                        timeout=120,
                    )
                    if r.status_code == 200:
                        results = r.json()
                    else:
                        st.warning(f"Live service returned {r.status_code}; showing saved results.")
                except Exception as e:
                    st.warning(f"Live service unreachable ({e}); showing saved results.")
        if results is None:
            results = TRIAGE_BATCH
            st.info("Showing saved example results (demo mode).")

        df = pd.DataFrame(results)
        styler = df.style
        # pandas >= 2.1 renamed Styler.applymap -> Styler.map; support both.
        color_fn = styler.map if hasattr(styler, "map") else styler.applymap

        def _color(val):
            return "color:#b91c1c" if str(val).lower() == "serious" else "color:#15803d"

        st.success(f"Processed {len(df)} reports")
        st.dataframe(color_fn(_color, subset=["seriousness"]), use_container_width=True)
        st.download_button("Download results CSV", df.to_csv(index=False).encode(),
                           "triage_results.csv", "text/csv")
        with st.expander("Raw structured output"):
            st.json(results)
