"""Portfolio hub — landing page. Run: streamlit run Home.py"""
import streamlit as st
import ui

st.set_page_config(page_title="PV Suite — Drug-Safety Tools", layout="wide")
ui.inject_css()
ui.sidebar_brand()

# ---- Hero ------------------------------------------------------------------
st.markdown(
    """
    <div class="pv-hero">
      <div class="eyebrow">Pharmacovigilance · point solutions</div>
      <h1>Three focused tools for drug-safety teams</h1>
      <p>Each one takes a single, well-defined job in the work of watching medicines for
      harmful effects — and does it end to end, evaluated, and ready to show. New to this
      space? Open <b>Overview</b> in the sidebar for a plain-language guide.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---- Three cards -----------------------------------------------------------
cards = [
    ("triage", "AE Triage", "AE_Triage",
     "Turn a free-text safety report into a structured, seriousness-graded record.",
     "For case intake teams"),
    ("regulatory", "Regulatory Q&A", "Regulatory_QA",
     "Ask about the reporting rules and get an answer quoted from the official guidance.",
     "For regulatory & safety staff"),
    ("safety", "Safety Signals", "Safety_Agent",
     "Enter a medicine and see whether a side effect is reported more than expected.",
     "For signal-detection teams"),
]
cols = st.columns(3, gap="medium")
for col, (ic, title, slug, job, who) in zip(cols, cards):
    col.markdown(
        f'<a class="pv-cardlink" href="{slug}" target="_self">'
        f'<div class="pv-card"><div class="pv-ic">{ui.icon(ic, 22)}</div>'
        f'<h3>{title}</h3><div class="job">{job}</div><div class="who">{who}</div>'
        f'<div class="go">Open {ui.icon("arrow", 15)}</div></div></a>',
        unsafe_allow_html=True,
    )

# Overview call-to-action — a purposeful full-width strip, not a stray button row.
st.markdown(
    f'<a class="pv-cta" href="Overview" target="_self">'
    f'<span class="ic">{ui.icon("info", 20)}</span>'
    f'<span class="tx"><b>New to drug safety?</b>'
    f'<span>Start with the two-minute Overview — a plain-language guide to what each tool does and how to read it.</span></span>'
    f'<span class="arr">{ui.icon("arrow", 20)}</span></a>',
    unsafe_allow_html=True,
)

# ---- Method note -----------------------------------------------------------
st.markdown(
    """
    <div class="pv-panel" style="margin-top:22px">
      <h4>What the three share isn’t a product — it’s a method</h4>
      <p>Every tool returns structured, checked output; each ships with its own scorecard,
      not just a demo; each keeps working in a <span class="lead">demo mode</span> when a
      connection or key isn’t available; and each is built to be read and trusted, with a
      human reviewing before anything is acted on.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption("Not a claim to “solve” drug safety — that space is vast. Three sharp tools, each doing one job well.")
