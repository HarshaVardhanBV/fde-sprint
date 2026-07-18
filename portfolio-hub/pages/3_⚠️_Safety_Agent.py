"""Safety-Signal Agent page — runs the tool-use agent in-process, with a cached demo fallback."""
import os
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# Key resolution: local .env first, then Streamlit secrets (Community Cloud) wins.
load_dotenv(override=True)
try:
    if "ANTHROPIC_API_KEY" in st.secrets:
        os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
except Exception:
    pass

from agent_core import run_agent          # noqa: E402  (import after key is set)
from demo_data import AGENT_EXAMPLES, EVAL_STATS, match_drug   # noqa: E402

st.set_page_config(page_title="Safety Agent", page_icon="⚠️")
st.title("⚠️ Safety-Signal Agent")
st.caption("Enter a drug → the agent pulls live FDA data (openFDA) and computes real "
           "disproportionality signals (PRR · ROR · IC) before returning a structured verdict.")

# --- Data source toggle ------------------------------------------------------
has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
default_mode = 0 if has_key else 1
mode = st.sidebar.radio(
    "Data source", ["Live", "Cached (demo)"], index=default_mode,
    help="Cached serves canned verdicts + signals so the page always renders — even with no "
         "API key/credits. Live runs the real tool-use loop against openFDA.",
)
ev = EVAL_STATS["agent"]
st.sidebar.markdown(f"**Evaluated · {ev['headline']}**")
st.sidebar.caption(ev["detail"])
st.sidebar.caption(f"Source: `{ev['source']}`")

CACHED = ", ".join(sorted(AGENT_EXAMPLES))
drug = st.text_input("Generic drug name", value="atorvastatin",
                     help=f"Cached examples: {CACHED}. Live mode accepts any drug.")


def render_signals(signals):
    if not signals:
        return
    rows = []
    for s in signals:
        if "PRR" not in s:      # tool returned a 'note' (insufficient counts)
            rows.append({"reaction": s.get("reaction", "—"), "reports (a)": s.get("a", "—"),
                         "PRR": "—", "ROR": "—", "IC (95% CI)": s.get("note", "—"), "signal": ""})
            continue
        ic_ci = s.get("IC_CI95", ["", ""])
        rows.append({
            "reaction": s["reaction"],
            "reports (a)": s.get("a", "—"),
            "PRR": s.get("PRR", "—"),
            "ROR": s.get("ROR", "—"),
            "IC (95% CI)": f"{s.get('IC', '—')} [{ic_ci[0]}, {ic_ci[1]}]",
            "signal": "✅" if s.get("signal") else "—",
        })
    st.markdown("#### Disproportionality signals")
    st.caption("A reaction flags only when disproportionate AND stable (≥3 reports). "
               "IC is a shrinkage measure — it stays near 0 when counts are too small to trust.")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_verdict(v: dict, trace, note=None):
    if note:
        st.info(note, icon="ℹ️")
    badge = {"signal": "red", "no-signal": "green", "insufficient-data": "gray"}
    st.markdown(f"### Assessment: :{badge.get(v['assessment'], 'gray')}[{v['assessment'].upper()}]")
    a, b = st.columns(2)
    a.metric("Confidence", v["confidence"])
    frac = v.get("serious_fraction")
    b.metric("Serious fraction", f"{frac:.0%}" if isinstance(frac, (int, float)) else "—")
    if v.get("notable_reactions"):
        st.write("**Notable reactions:** " + ", ".join(v["notable_reactions"]))
    st.write(f"**Rationale:** {v['rationale']}")
    render_signals(v.get("signals"))
    with st.expander(f"🔧 How the agent worked ({len(trace)} tool call(s))"):
        st.write("The agent chose which tools to call, ran them, then reasoned over the results:")
        for t in trace:
            st.code(t, language="text")
    with st.expander("Raw verdict JSON"):
        st.json(v)


if st.button("Assess", type="primary") and drug.strip():
    v = trace = note = None

    if mode == "Live":
        if not has_key:
            st.warning("No ANTHROPIC_API_KEY configured — showing a cached example instead.")
        else:
            with st.spinner("Agent is calling FDA tools, computing disproportionality, and reasoning..."):
                try:
                    verdict, trace = run_agent(drug.strip())
                    if verdict is not None:
                        v = verdict.model_dump()
                    else:
                        st.warning("The agent did not return a valid verdict; showing a cached example.")
                except Exception as e:
                    st.warning(f"Live agent error ({e}); showing a cached example.")

    if v is None:   # cached path (chosen, or fallback)
        ex = match_drug(drug)
        if ex is None:
            st.info(f"No cached example for “{drug}”. Try one of: {CACHED} — or switch to Live.", icon="🗂️")
            st.stop()
        v, trace = ex["verdict"], ex["trace"]
        note = "Cached example output (demo mode). " + ex.get("note", "")

    render_verdict(v, trace, note)

st.caption("Reported-frequency FAERS data — not proven causation. Verdict validated by Pydantic; "
           "PRR/ROR/IC computed from 2×2 contingency tables (true EBGM needs a whole-database prior).")
