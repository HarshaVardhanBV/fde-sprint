"""Regulatory Q&A page — calls the live FastAPI backend on Railway, with a cached demo fallback."""
import requests
import streamlit as st

import ui
from demo_data import RAG_EXAMPLES, EVAL_STATS, match_text

ui.setup(
    page_title="Regulatory Q&A",
    icon_name="regulatory",
    title="Regulatory Q&A",
    subtitle="Ask a plain question about the reporting rules and get an answer quoted from official guidance.",
)

API = st.secrets.get("RAG_API", "https://reg-rag-production.up.railway.app")

# --- Data source toggle ------------------------------------------------------
mode = st.sidebar.radio(
    "Data source", ["Live", "Cached (demo)"],
    help="Cached serves saved answers so the page always renders — even with no connection or key.",
)
ev = EVAL_STATS["rag"]
st.sidebar.markdown(f"**Evaluated · {ev['headline']}**")
st.sidebar.caption(ev["detail"])
st.sidebar.caption(f"Source: `{ev['source']}`")

ui.newcomer_note([
    "Type a question about the official rules for reporting medicine side effects.",
    "You get back an answer **quoted from the guidance documents**, with the exact source passages shown below it.",
    "If the answer isn’t in the documents, the tool says so instead of guessing — expand **Sources** to check.",
    "In **Cached (demo)** mode it shows saved answers — nothing to set up.",
])

EXAMPLES = [
    "What are the criteria that make an adverse event serious?",
    "What is the definition of an adverse event?",
    "What is the recommended dose of aspirin for adults?",
]
st.write("Try:", " · ".join(f"`{e}`" for e in EXAMPLES))
st.caption("The third is a trap — it isn’t covered by the guidance documents, so a trustworthy tool should decline it.")

q = st.text_input("Your question", value=EXAMPLES[0])

if st.button("Ask", type="primary") and q.strip():
    d = None
    if mode == "Live":
        with st.spinner("Finding the relevant guidance and answering..."):
            try:
                r = requests.post(f"{API}/ask", json={"question": q}, timeout=90)
                if r.status_code == 200:
                    d = r.json()
                else:
                    st.warning(f"Live service returned {r.status_code}; showing a saved example.")
            except Exception as e:
                st.warning(f"Live service unreachable ({e}); showing a saved example.")
    if d is None:
        ex = match_text(RAG_EXAMPLES, "question", q)
        d = {"answer": ex["answer"], "sources": ex["sources"]}
        note = ex.get("note")
        st.info("Showing a saved example (demo mode)." + (f" {note}" if note else ""))

    st.markdown("### Answer")
    st.write(d.get("answer", ""))
    sources = d.get("sources", [])
    st.markdown(f"### Sources ({len(sources)})")
    for i, s in enumerate(sources, 1):
        with st.expander(f"Source {i}"):
            st.write(s)

st.caption("Answers come only from the retrieved guidance text — the tool says so when the answer isn’t in the documents.")
