"""Portfolio hub — landing page. Run: streamlit run Home.py"""
import streamlit as st

st.set_page_config(page_title="FDE Pharma AI Portfolio", page_icon="🧬", layout="centered")

st.title("🧬 FDE Pharma AI Portfolio")
st.caption("Three independent point solutions for pharmacovigilance teams — each built and evaluated the same way.")

st.markdown(
    """
> **13 years turning Fortune-50 pharma problems into strategy — now I build and deploy
> the AI systems myself.**
>
> Not a platform, and not a claim to "solve PV" — that space is too big for any one tool.
> Instead: three sharp point solutions, each owning **one bounded job for one owner**.
> Pick one from the sidebar. →
"""
)

st.divider()

st.subheader("Three point solutions")

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown("### 🩺 AE Triage")
    st.write("**Job:** cut manual case-intake time. Free-text AE report → structured, "
             "seriousness-graded output.")
    st.caption("For case processing · FastAPI · Pydantic · ICH E2A")
with c2:
    st.markdown("### 📄 Regulatory Q&A")
    st.write("**Job:** stop hunting through guidance PDFs. Cited answers from ICH/FDA text, "
             "or an honest \"not in the docs.\"")
    st.caption("For reg affairs / PV scientists · RAG · grounded")
with c3:
    st.markdown("### ⚠️ Safety Agent")
    st.write("**Job:** a fast, defensible first-pass signal read. Drug → disproportionality "
             "stats (PRR·ROR·IC) on public FAERS.")
    st.caption("For signal detection · openFDA · tool-use · evals")

st.divider()

st.markdown(
    """
**What the three share isn't a product — it's a method.** Each is typed and schema-validated,
each ships with its own eval harness (not just a demo), each routes work to the right model
(Haiku for high-volume extraction, Opus for judgment), and each stays alive in **demo mode**
when there's no API key or credits. That discipline is the throughline.
"""
)
st.caption("They also share typed contracts, so they *can* be composed when a workflow needs it — "
           "see `pv-copilot-architecture.svg` (appendix). But each stands on its own; start there.")
