"""Safety-Signal Agent page — runs the tool-use agent in-process."""
import os
import streamlit as st
from dotenv import load_dotenv

# Key resolution: local .env first, then Streamlit secrets (Community Cloud) wins.
load_dotenv(override=True)
try:
    if "ANTHROPIC_API_KEY" in st.secrets:
        os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
except Exception:
    pass

from agent_core import run_agent   # noqa: E402  (import after key is set)

st.set_page_config(page_title="Safety Agent", page_icon="⚠️")
st.title("⚠️ Safety-Signal Agent")
st.caption("Enter a drug → the agent pulls live FDA data (openFDA) and returns a structured verdict.")

drug = st.text_input("Generic drug name", value="atorvastatin",
                     help="Try: warfarin, isotretinoin, aspirin, cetirizine")

if st.button("Assess", type="primary") and drug.strip():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        st.error("No ANTHROPIC_API_KEY configured. Add it in the app's Secrets.")
        st.stop()
    with st.spinner("Agent is calling FDA tools and reasoning..."):
        try:
            verdict, trace = run_agent(drug.strip())
        except Exception as e:
            st.error(f"Agent error: {e}")
            st.stop()

    if verdict is None:
        st.error("The agent did not return a valid verdict. Try another drug name.")
        st.stop()

    v = verdict.model_dump()
    badge = {"signal": "red", "no-signal": "green", "insufficient-data": "gray"}
    st.markdown(f"### Assessment: :{badge.get(v['assessment'], 'gray')}[{v['assessment'].upper()}]")

    a, b = st.columns(2)
    a.metric("Confidence", v["confidence"])
    frac = v.get("serious_fraction")
    b.metric("Serious fraction", f"{frac:.0%}" if isinstance(frac, (int, float)) else "—")

    if v.get("notable_reactions"):
        st.write("**Notable reactions:** " + ", ".join(v["notable_reactions"]))
    st.write(f"**Rationale:** {v['rationale']}")

    with st.expander(f"🔧 How the agent worked ({len(trace)} tool call(s))"):
        st.write("The agent decided which tools to call, ran them, then reasoned over the results:")
        for t in trace:
            st.code(t, language="text")

    with st.expander("Raw verdict JSON"):
        st.json(v)

st.caption("Reported-frequency FAERS data — not proven causation. Verdict validated by Pydantic.")
