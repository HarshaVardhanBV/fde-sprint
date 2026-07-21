"""Overview — a plain-language guide for anyone new to this space."""
import streamlit as st
import ui

ui.setup(
    page_title="Overview",
    icon_name="info",
    title="Overview",
    subtitle="What these tools are, and how to read them — in plain language, no background needed.",
)


def flow(steps):
    """Render a left-to-right 'input → … → output' strip from (icon, label) pairs."""
    parts = []
    for i, (ic, label) in enumerate(steps):
        if i:
            parts.append(f'<span class="pv-arr">{ui.icon("arrow", 18)}</span>')
        parts.append(f'<span class="pv-step"><span class="pv-ic">{ui.icon(ic, 16)}</span>{label}</span>')
    st.markdown('<div class="pv-flow">' + "".join(parts) + "</div>", unsafe_allow_html=True)


# ── Why this exists ──────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="pv-panel">
      <h4>Why this exists</h4>
      <p>When people take medicines, some of them have unwanted effects — from a mild
      headache to something serious. Around the world, companies and health authorities
      are <span class="lead">required</span> to watch for these effects, record them, and
      act quickly when a medicine looks risky. That ongoing watch is called
      <b>drug-safety monitoring</b> (its formal name is <i>pharmacovigilance</i>).</p>
      <p>It is a huge, detailed field — no single person or tool covers all of it. These
      three tools each take <b>one specific, everyday task</b> inside that work and make it
      faster and clearer, while leaving the final judgement to a trained person.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("### The three tools, one at a time")

# ── AE Triage ────────────────────────────────────────────────────────────────
st.markdown('<div class="pv-panel"><h4>1 · Adverse-Event Triage</h4>'
            '<p class="lead" style="margin-bottom:2px">Sorting incoming safety reports.</p></div>',
            unsafe_allow_html=True)
st.markdown(
    "**What you enter** — a short written report of something that happened to a patient "
    "after taking a medicine, exactly as a nurse, pharmacist, or member of the public might "
    "have written it. For example: *“A 68-year-old woman had severe chest pain after taking "
    "aspirin and was kept in hospital overnight.”*\n\n"
    "**What comes back** — the same information, tidied into fixed fields: which medicine is "
    "suspected, what happened in one line, a short summary, and — most importantly — whether "
    "it counts as **serious**.\n\n"
    "**How to read it** — a **red** label means *serious*: by an internationally agreed "
    "checklist (things like death, a life-threatening event, or a hospital stay), this report "
    "must be reported quickly and formally. **Green** means *not serious*. The **confidence** "
    "shows how clear-cut the report was."
)
st.markdown("**How it gets there**")
flow([("regulatory", "Your written report"),
      ("scan", "Pick out the medicine &amp; the event"),
      ("check", "Check against the ‘serious’ checklist"),
      ("triage", "Tidy, graded result")])

st.markdown('<hr class="pv-rule"/>', unsafe_allow_html=True)

# ── Regulatory Q&A ───────────────────────────────────────────────────────────
st.markdown('<div class="pv-panel"><h4>2 · Regulatory Q&amp;A</h4>'
            '<p class="lead" style="margin-bottom:2px">Answering questions about the rulebook.</p></div>',
            unsafe_allow_html=True)
st.markdown(
    "**What you enter** — a plain question about the official rules for reporting side "
    "effects. For example: *“What makes a side effect count as serious?”* or *“How quickly "
    "must a life-threatening reaction be reported?”*\n\n"
    "**What comes back** — a direct answer, drawn from the official guidance documents, with "
    "the exact passages it used shown underneath so you can check them yourself. If the answer "
    "genuinely isn’t in those documents, the tool says so rather than making something up.\n\n"
    "**How to read it** — read the answer, then open **Sources** to see the precise wording it "
    "came from. If it declines to answer, that is the honest, correct behaviour — it means the "
    "question is outside what the guidance covers."
)
st.markdown("**How it gets there**")
flow([("info", "Your question"),
      ("search", "Search the guidance documents"),
      ("regulatory", "Answer using only those passages"),
      ("check", "Answer + exact sources")])

st.markdown('<hr class="pv-rule"/>', unsafe_allow_html=True)

# ── Safety Signals ───────────────────────────────────────────────────────────
st.markdown('<div class="pv-panel"><h4>3 · Safety Signals</h4>'
            '<p class="lead" style="margin-bottom:2px">Spotting side effects reported more than expected.</p></div>',
            unsafe_allow_html=True)
st.markdown(
    "**What you enter** — the name of a medicine.\n\n"
    "**What comes back** — a verdict on whether there is a possible **signal**: a side effect "
    "that is being reported *more often than you’d expect* for this medicine compared with all "
    "others. Below the verdict is a table of the numbers behind it.\n\n"
    "**How to read the numbers** — each row is one reaction:\n"
    "- **Reports** — how many times this medicine and this reaction were mentioned together.\n"
    "- **PRR** and **ROR** — *how many times more often* the reaction is reported for this "
    "medicine than for others. A value near **1** is ordinary; **2** means roughly twice as "
    "often; higher means it stands out more.\n"
    "- **IC** — the same idea, but deliberately pulled toward zero when there are only a few "
    "reports, so a scary-looking number built on two or three cases doesn’t raise a false alarm.\n"
    "- **Flag (✓)** — the reaction stands out beyond chance **and** rests on enough reports to "
    "be taken seriously. A big ratio with too few reports does **not** get a flag — that is the "
    "tool being careful, not missing something."
)
st.markdown("**How it gets there**")
flow([("safety", "Medicine name"),
      ("database", "Pull the public reports database"),
      ("scan", "Count vs. all other medicines"),
      ("check", "Standard math → verdict + numbers")])

# ── Glossary ─────────────────────────────────────────────────────────────────
st.markdown("### Words you’ll come across")
st.markdown(
    "- **Adverse event** — any unwanted medical happening after someone takes a medicine. It "
    "doesn’t yet prove the medicine *caused* it; it’s simply what was observed and reported.\n"
    "- **Serious** — a specific, agreed meaning here, not just “bad”. It covers things like "
    "death, a life-threatening event, hospitalisation, lasting disability, or a birth defect. "
    "Serious reports must be reported to authorities quickly.\n"
    "- **Signal** — an early hint, from the pattern of reports, that a medicine *might* be "
    "linked to a particular side effect and deserves a closer look. A signal is a prompt to "
    "investigate, not a conclusion.\n"
    "- **Reported data** — the safety database is built from reports people *chose* to submit. "
    "It shows what gets reported, which is why these tools describe possibilities and leave the "
    "final call to an expert — they never claim a medicine definitely caused something.\n"
    "- **The guidance / the rulebook** — the official documents that define how side effects "
    "must be classified and reported. The Regulatory Q&A tool answers only from these."
)

st.markdown(
    """
    <div class="pv-panel" style="margin-top:14px">
      <h4>The one thing to remember</h4>
      <p>These tools speed up and clarify the routine parts of drug-safety work — sorting
      reports, checking the rules, and flagging patterns worth a look. They are there to help a
      trained person decide faster and more consistently. <b>A human always reviews before
      anything is acted on.</b></p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption("Ready to try it? Pick a tool from the sidebar. Every page has a demo mode, so nothing needs setting up.")
