"""Portfolio hub — landing page. Run: streamlit run Home.py"""
import streamlit as st

st.set_page_config(page_title="FDE Pharma AI Portfolio", page_icon="🧬", layout="centered")

st.title("🧬 FDE Pharma AI Portfolio")
st.caption("Three deployed, evaluated LLM systems for regulated pharma workflows.")

st.markdown(
    """
> **13 years turning Fortune-50 pharma problems into strategy — now I build and deploy
> the AI systems myself.** Pick a demo from the sidebar. →
"""
)

st.divider()

st.subheader("The three systems")

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown("### 🩺 AE Triage")
    st.write("Free-text adverse-event reports → structured triage via a typed API.")
    st.caption("FastAPI · Pydantic · Claude")
with c2:
    st.markdown("### 📄 Regulatory Q&A")
    st.write("Cited answers from ICH/FDA guidelines. RAG, grounded, no hallucination.")
    st.caption("ChromaDB · embeddings · Claude")
with c3:
    st.markdown("### ⚠️ Safety Agent")
    st.write("Tool-use agent that pulls FDA data and returns a structured signal verdict.")
    st.caption("openFDA · tool-use loop · evals")

st.divider()

st.markdown(
    """
**Architecture:** this UI is a thin Streamlit front end. The AE Triage and Regulatory Q&A
pages call their **FastAPI backends live on Railway**; the Safety Agent runs its tool-use
loop **in-process**. Every system was built *and evaluated* — build → evaluate → deploy.
"""
)
st.caption("Use the sidebar to open each demo.")
