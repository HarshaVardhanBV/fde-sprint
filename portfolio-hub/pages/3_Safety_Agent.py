"""Safety-Signals page — runs the tool-use agent in-process, with a cached demo fallback."""
import os
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

import ui

ui.setup(
    page_title="Safety Signals",
    icon_name="safety",
    title="Safety Signals",
    subtitle="Enter a medicine and get a first-pass read on whether a side effect is reported more than expected.",
)

# Key resolution: local .env first, then Streamlit secrets (Community Cloud) wins.
load_dotenv(override=True)
try:
    if "ANTHROPIC_API_KEY" in st.secrets:
        os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
except Exception:
    pass

from agent_core import run_agent          # noqa: E402  (import after key is set)
from demo_data import AGENT_EXAMPLES, EVAL_STATS, match_drug   # noqa: E402

# --- Data source toggle ------------------------------------------------------
has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
default_mode = 0 if has_key else 1
mode = st.sidebar.radio(
    "Data source", ["Live", "Cached (demo)"], index=default_mode,
    help="Cached serves saved results so the page always renders — even with no key. "
         "Live pulls the public safety database and computes the numbers fresh.",
)
ev = EVAL_STATS["agent"]
st.sidebar.markdown(f"**Evaluated · {ev['headline']}**")
st.sidebar.caption(ev["detail"])
st.sidebar.caption(f"Source: `{ev['source']}`")

ui.newcomer_note([
    "Type the everyday or generic name of a medicine.",
    "You get back a verdict — is there a possible **signal** (a side effect reported more often than expected)? "
    "— plus a table of the numbers behind it.",
    "**Signal** (red) = worth a closer look. **No signal** (green) = nothing stands out. "
    "A reaction only flags when it stands out beyond chance *and* rests on enough reports to trust.",
    "In **Cached (demo)** mode, try: " + ", ".join(sorted(AGENT_EXAMPLES)) + ".",
])

CACHED = ", ".join(sorted(AGENT_EXAMPLES))
drug = st.text_input("Medicine name", value="atorvastatin",
                     help=f"Saved examples: {CACHED}. Live mode accepts any medicine.")


def render_signals(signals):
    if not signals:
        return
    rows = []
    for s in signals:
        if "PRR" not in s:      # tool returned a 'note' (insufficient counts)
            rows.append({"reaction": s.get("reaction", "—"), "reports": s.get("a", "—"),
                         "PRR": "—", "ROR": "—", "IC (95% CI)": s.get("note", "—"), "flag": ""})
            continue
        ic_ci = s.get("IC_CI95", ["", ""])
        rows.append({
            "reaction": s["reaction"],
            "reports": s.get("a", "—"),
            "PRR": s.get("PRR", "—"),
            "ROR": s.get("ROR", "—"),
            "IC (95% CI)": f"{s.get('IC', '—')} [{ic_ci[0]}, {ic_ci[1]}]",
            "flag": "✓" if s.get("signal") else "—",
        })
    st.markdown("#### How much each reaction stands out")
    st.caption("PRR / ROR — how many times more often a reaction is reported for this medicine than for others. "
               "IC — the same idea, but pulled toward zero when there are too few reports to trust. "
               "A ✓ means the reaction stands out beyond chance and rests on enough reports.")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_verdict(v: dict, trace, note=None):
    if note:
        st.info(note)
    cls = {"signal": "red", "no-signal": "green", "insufficient-data": "gray"}.get(v["assessment"], "gray")
    label = {"signal": "SIGNAL", "no-signal": "NO SIGNAL",
             "insufficient-data": "INSUFFICIENT DATA"}.get(v["assessment"], v["assessment"].upper())
    st.markdown(f'<span class="pv-badge {cls}">{label}</span>', unsafe_allow_html=True)
    st.write("")
    a, b = st.columns(2)
    a.metric("Confidence", v["confidence"])
    frac = v.get("serious_fraction")
    b.metric("Serious fraction", f"{frac:.0%}" if isinstance(frac, (int, float)) else "—")
    if v.get("notable_reactions"):
        st.write("**Notable reactions:** " + ", ".join(v["notable_reactions"]))
    st.write(f"**Rationale:** {v['rationale']}")
    render_signals(v.get("signals"))
    with st.expander(f"How this result was produced ({len(trace)} step(s))"):
        st.write("The tool chose which checks to run, ran them, then reasoned over the results:")
        for t in trace:
            st.code(t, language="text")
    with st.expander("Raw structured output"):
        st.json(v)


if st.button("Assess medicine", type="primary") and drug.strip():
    v = trace = note = None

    if mode == "Live":
        if not has_key:
            st.warning("No key configured for live mode — showing a saved example instead.")
        else:
            with st.spinner("Pulling the safety database and computing the numbers..."):
                try:
                    verdict, trace = run_agent(drug.strip())
                    if verdict is not None:
                        v = verdict.model_dump()
                    else:
                        st.warning("Could not produce a valid result; showing a saved example.")
                except Exception as e:
                    st.warning(f"Live run failed ({e}); showing a saved example.")

    if v is None:   # cached path (chosen, or fallback)
        ex = match_drug(drug)
        if ex is None:
            st.info(f"No saved example for “{drug}”. Try one of: {CACHED} — or switch to Live.")
            st.stop()
        v, trace = ex["verdict"], ex["trace"]
        note = "Showing a saved example (demo mode). " + ex.get("note", "")

    render_verdict(v, trace, note)

st.caption("Based on voluntarily reported data — it shows what is reported, not proof a medicine caused an effect. "
           "Every result is meant for a human expert to review.")
