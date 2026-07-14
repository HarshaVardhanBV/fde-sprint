"""Regulatory RAG Q&A page — calls the live FastAPI backend on Railway."""
import requests
import streamlit as st

API = st.secrets.get("RAG_API", "https://reg-rag-production.up.railway.app")

st.set_page_config(page_title="Regulatory Q&A", page_icon="📄")
st.title("📄 Regulatory RAG Q&A")
st.caption("Ask about ICH/FDA guidelines → cited answers. Backend: FastAPI + ChromaDB on Railway.")

EXAMPLES = [
    "What are the criteria that make an adverse event serious?",
    "What is the definition of an adverse event?",
    "What does 'life-threatening' mean for a serious adverse event?",
]
st.write("Try:", " · ".join(f"`{e}`" for e in EXAMPLES))

q = st.text_input("Your question", value=EXAMPLES[0])

if st.button("Ask", type="primary") and q.strip():
    with st.spinner("Retrieving and generating a grounded answer..."):
        try:
            r = requests.post(f"{API}/ask", json={"question": q}, timeout=90)
        except Exception as e:
            st.error(f"Could not reach the API: {e}")
            st.stop()

    if r.status_code == 200:
        d = r.json()
        st.markdown("### Answer")
        st.write(d.get("answer", ""))
        sources = d.get("sources", [])
        st.markdown(f"### Sources ({len(sources)})")
        for i, s in enumerate(sources, 1):
            with st.expander(f"Source {i}"):
                st.write(s)
    else:
        st.error(f"API error {r.status_code}: {r.text[:300]}")

st.caption("Answers strictly from retrieved context — the system says so when the answer isn't in the docs.")
