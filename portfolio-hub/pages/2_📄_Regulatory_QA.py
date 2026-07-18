"""Regulatory RAG Q&A page — calls the live FastAPI backend on Railway, with a cached demo fallback."""
import requests
import streamlit as st

from demo_data import RAG_EXAMPLES, EVAL_STATS, match_text

API = st.secrets.get("RAG_API", "https://reg-rag-production.up.railway.app")

st.set_page_config(page_title="Regulatory Q&A", page_icon="📄")
st.title("📄 Regulatory RAG Q&A")
st.caption("Ask about ICH/FDA guidelines → cited answers, grounded in the retrieved text. "
           "Backend: FastAPI + ChromaDB on Railway.")

# --- Data source toggle ------------------------------------------------------
mode = st.sidebar.radio(
    "Data source", ["Live", "Cached (demo)"],
    help="Cached serves canned Q&A so the page always renders — even with no API key/credits "
         "or a cold backend.",
)
ev = EVAL_STATS["rag"]
st.sidebar.markdown(f"**Evaluated · {ev['headline']}**")
st.sidebar.caption(ev["detail"])
st.sidebar.caption(f"Source: `{ev['source']}`")

EXAMPLES = [
    "What are the criteria that make an adverse event serious?",
    "What is the definition of an adverse event?",
    "What is the recommended dose of aspirin for adults?",
]
st.write("Try:", " · ".join(f"`{e}`" for e in EXAMPLES))
st.caption("The third is a trap — it's not in the ICH corpus. A grounded system should decline it.")

q = st.text_input("Your question", value=EXAMPLES[0])

if st.button("Ask", type="primary") and q.strip():
    d = None
    if mode == "Live":
        with st.spinner("Retrieving and generating a grounded answer..."):
            try:
                r = requests.post(f"{API}/ask", json={"question": q}, timeout=90)
                if r.status_code == 200:
                    d = r.json()
                else:
                    st.warning(f"Live API returned {r.status_code}; showing a cached example.")
            except Exception as e:
                st.warning(f"Live API unreachable ({e}); showing a cached example.")
    if d is None:
        ex = match_text(RAG_EXAMPLES, "question", q)
        d = {"answer": ex["answer"], "sources": ex["sources"]}
        note = ex.get("note")
        st.info("Cached example output (demo mode)." + (f" {note}" if note else ""), icon="🗂️")

    st.markdown("### Answer")
    st.write(d.get("answer", ""))
    sources = d.get("sources", [])
    st.markdown(f"### Sources ({len(sources)})")
    for i, s in enumerate(sources, 1):
        with st.expander(f"Source {i}"):
            st.write(s)

st.caption("Answers strictly from retrieved context — the system says so when the answer isn't in the docs.")
