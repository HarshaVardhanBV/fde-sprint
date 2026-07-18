"""
demo_data.py — cached example outputs + real eval baselines for the portfolio hub.

WHY THIS EXISTS
  A live demo that dies on a missing/expired/credit-less API key is worse than no
  demo — it's the sales asset. Every page can fall back to these canned results so
  it ALWAYS renders something, and a "Live / Cached (demo)" toggle lets the viewer
  choose. Cached mode also needs no backend, so the hub survives a cold Railway box.

  The numbers in EVAL_STATS are the REAL baselines from the eval harness (03-evals
  and 04-safety-agent), not decoration. Sources are named so they're checkable.
"""

# ---------------------------------------------------------------------------
# Real eval baselines (checked in to the repo alongside the harness output).
# ---------------------------------------------------------------------------
EVAL_STATS = {
    "triage": {
        "headline": "Typed & schema-validated",
        "detail": "Every response is Pydantic-validated against a fixed schema; "
                  "seriousness follows ICH E2A criteria. Malformed rows fail loudly, "
                  "never silently.",
        "source": "01-ae-triage-api (Pydantic response_model + test_main.py)",
    },
    "rag": {
        "headline": "RAG triad 4.79 / 5",
        "detail": "LLM-as-judge over an 8-question gold set (7 grounded + 1 refusal "
                  "trap). Answer quality 4.79/5, retrieval (context relevance) 4.57/5. "
                  "The trap question is scored on correctly refusing.",
        "source": "03-evals/results_20260708_083919.json",
    },
    "agent": {
        "headline": "89% match (8/9), rationale 5.0 / 5",
        "detail": "Assessment label vs. known-correct is deterministic: 8/9 across "
                  "easy + hard drugs. LLM-judged rationale groundedness 5.0/5 and "
                  "avoids-serious-fraction-trap 5.0/5. The one miss (aspirin) is shown, "
                  "not hidden.",
        "source": "04-safety-agent/agent_eval_20260713_233845.json",
    },
}

# ---------------------------------------------------------------------------
# AE Triage — cached single-report outputs.
# ---------------------------------------------------------------------------
TRIAGE_EXAMPLES = [
    {
        "report": ("68-year-old female developed severe chest pain and shortness of "
                   "breath after taking Aspirin 500mg, and was hospitalised overnight."),
        "response": {
            "seriousness": "serious",
            "suspected_drug": "Aspirin",
            "event": "Severe chest pain and shortness of breath requiring overnight hospitalisation",
            "summary": "A 68-year-old woman developed severe chest pain and breathlessness "
                       "after taking aspirin and was hospitalised. Hospitalisation makes this "
                       "a serious event under ICH E2A.",
            "confidence": "high",
        },
    },
    {
        "report": "Patient reports mild headache after Paracetamol 500mg. Resolved after 2 hours.",
        "response": {
            "seriousness": "non-serious",
            "suspected_drug": "Paracetamol",
            "event": "Mild, self-limiting headache",
            "summary": "A patient had a mild headache after paracetamol that resolved within "
                       "two hours. It meets no ICH E2A seriousness criterion.",
            "confidence": "high",
        },
    },
    {
        "report": "32-year-old male experienced anaphylactic shock after first dose of Amoxicillin.",
        "response": {
            "seriousness": "serious",
            "suspected_drug": "Amoxicillin",
            "event": "Anaphylactic shock following first dose",
            "summary": "A 32-year-old man had anaphylactic shock after his first amoxicillin dose. "
                       "Anaphylaxis is life-threatening and therefore serious.",
            "confidence": "high",
        },
    },
]

# Cached batch output (matches the sample CSV offered on the page).
TRIAGE_BATCH = [ex["response"] for ex in TRIAGE_EXAMPLES]

# ---------------------------------------------------------------------------
# Regulatory RAG — cached Q&A with source chunks.
# ---------------------------------------------------------------------------
RAG_EXAMPLES = [
    {
        "question": "What are the criteria that make an adverse event serious?",
        "answer": ("According to Source 1, an adverse event or reaction is serious when it "
                   "results in any of the following outcomes: it results in death, is "
                   "life-threatening, requires or prolongs inpatient hospitalisation, results "
                   "in persistent or significant disability or incapacity, or is a congenital "
                   "anomaly or birth defect. Source 1 also notes that important medical events "
                   "that may jeopardise the patient or require intervention to prevent one of "
                   "these outcomes should also be considered serious."),
        "sources": [
            "A serious adverse event or reaction is any untoward medical occurrence that at any "
            "dose results in death, is life-threatening, requires inpatient hospitalisation or "
            "prolongation of existing hospitalisation, results in persistent or significant "
            "disability/incapacity, or is a congenital anomaly/birth defect. Medical and "
            "scientific judgement should be exercised for other important medical events.",
            "The term 'life-threatening' refers to an event in which the patient was at risk of "
            "death at the time of the event; it does not refer to an event which hypothetically "
            "might have caused death if it were more severe.",
        ],
    },
    {
        "question": "What is the definition of an adverse event?",
        "answer": ("According to Source 1, an adverse event is any untoward medical occurrence in "
                   "a patient or clinical investigation subject administered a pharmaceutical "
                   "product, and which does not necessarily have a causal relationship with the "
                   "treatment. It can be any unfavourable and unintended sign, symptom, or "
                   "disease temporally associated with the use of the product, whether or not "
                   "considered related to it."),
        "sources": [
            "An adverse event (AE) is any untoward medical occurrence in a patient or clinical "
            "investigation subject administered a pharmaceutical product and which does not "
            "necessarily have a causal relationship with this treatment.",
        ],
    },
    {
        "question": "What is the recommended dose of aspirin for adults?",
        "answer": "I don't have enough information in the provided documents.",
        "sources": [
            "A serious adverse event or reaction is any untoward medical occurrence that at any "
            "dose results in death, is life-threatening, requires hospitalisation ...",
        ],
        "note": "Refusal (trap) — the corpus is ICH E2A guidance, not a dosing reference. "
                "Correctly declining is the win.",
    },
]

# ---------------------------------------------------------------------------
# Safety Agent — cached verdicts, tool traces, and disproportionality signals.
# ---------------------------------------------------------------------------
AGENT_EXAMPLES = {
    "atorvastatin": {
        "verdict": {
            "drug": "atorvastatin",
            "assessment": "signal",
            "confidence": "medium",
            "notable_reactions": ["Myalgia", "Rhabdomyolysis", "Blood creatine phosphokinase increased"],
            "serious_fraction": 0.41,
            "rationale": "Among serious reports, muscle-related events (myalgia, rhabdomyolysis, "
                         "raised CPK) stand out and are consistent with the known statin myotoxicity "
                         "risk. The signal rests on those specific reactions and their disproportionality, "
                         "not on the serious fraction, which is unremarkable for FAERS.",
            "signals": [
                {"reaction": "Rhabdomyolysis", "a": 812, "expected": 96.4, "PRR": 8.42,
                 "PRR_CI95": [7.8, 9.1], "ROR": 8.61, "ROR_CI95": [7.98, 9.29],
                 "IC": 3.07, "IC_CI95": [2.9, 3.24], "chi2_yates": 4211.0, "signal": True},
                {"reaction": "Myalgia", "a": 1503, "expected": 402.1, "PRR": 3.74,
                 "PRR_CI95": [3.55, 3.94], "ROR": 3.86, "ROR_CI95": [3.66, 4.07],
                 "IC": 1.9, "IC_CI95": [1.78, 2.02], "chi2_yates": 2988.0, "signal": True},
            ],
        },
        "trace": ["get_adverse_events(atorvastatin)", "get_serious_event_count(atorvastatin)",
                  "get_serious_reactions(atorvastatin)", "compute_disproportionality(atorvastatin, Rhabdomyolysis)",
                  "compute_disproportionality(atorvastatin, Myalgia)"],
    },
    "warfarin": {
        "verdict": {
            "drug": "warfarin",
            "assessment": "signal",
            "confidence": "medium",
            "notable_reactions": ["International normalised ratio increased", "Gastrointestinal haemorrhage", "Fall"],
            "serious_fraction": 0.66,
            "rationale": "Serious reports are dominated by bleeding-related events (raised INR, GI "
                         "haemorrhage) with strong disproportionality, consistent with warfarin's "
                         "established haemorrhage risk. The high serious fraction is set aside as "
                         "expected FAERS over-reporting.",
            "signals": [
                {"reaction": "International normalised ratio increased", "a": 2140, "expected": 61.2,
                 "PRR": 12.9, "PRR_CI95": [12.3, 13.6], "ROR": 13.4, "ROR_CI95": [12.7, 14.1],
                 "IC": 3.6, "IC_CI95": [3.49, 3.71], "chi2_yates": 9900.0, "signal": True},
                {"reaction": "Gastrointestinal haemorrhage", "a": 1188, "expected": 210.5,
                 "PRR": 4.71, "PRR_CI95": [4.44, 4.99], "ROR": 4.86, "ROR_CI95": [4.58, 5.16],
                 "IC": 2.14, "IC_CI95": [2.0, 2.28], "chi2_yates": 3550.0, "signal": True},
            ],
        },
        "trace": ["get_adverse_events(warfarin)", "get_serious_event_count(warfarin)",
                  "get_serious_reactions(warfarin)", "compute_disproportionality(warfarin, International normalised ratio increased)",
                  "compute_disproportionality(warfarin, Gastrointestinal haemorrhage)"],
    },
    "aspirin": {
        "verdict": {
            "drug": "aspirin",
            "assessment": "no-signal",
            "confidence": "medium",
            "notable_reactions": ["Nausea", "Dyspnoea", "Drug ineffective"],
            "serious_fraction": 0.70,
            "rationale": "The serious breakdown is dominated by non-specific reactions (nausea, "
                         "dyspnoea, 'drug ineffective') without a standout disproportionate signal, "
                         "and the 0.70 serious fraction is treated as FAERS reporting bias, not a "
                         "signal.",
            "signals": [
                {"reaction": "Gastrointestinal haemorrhage", "a": 640, "expected": 402.0,
                 "PRR": 1.62, "PRR_CI95": [1.5, 1.75], "ROR": 1.63, "ROR_CI95": [1.51, 1.76],
                 "IC": 0.67, "IC_CI95": [0.5, 0.84], "chi2_yates": 121.0, "signal": False},
            ],
        },
        "trace": ["get_adverse_events(aspirin)", "get_serious_event_count(aspirin)",
                  "get_serious_reactions(aspirin)", "compute_disproportionality(aspirin, Gastrointestinal haemorrhage)"],
        "note": "This is the agent's one eval miss (expected 'signal', got 'no-signal'). Aspirin's "
                "GI-bleed risk is real but its FAERS disproportionality is modest — a genuinely hard, "
                "borderline case. Shown deliberately.",
    },
    "cetirizine": {
        "verdict": {
            "drug": "cetirizine",
            "assessment": "no-signal",
            "confidence": "medium",
            "notable_reactions": ["Somnolence", "Drug ineffective", "Fatigue"],
            "serious_fraction": 0.55,
            "rationale": "Serious reports reflect non-specific, largely benign reactions (somnolence, "
                         "fatigue) with no disproportionate serious signal; the 0.55 serious fraction is "
                         "attributed to FAERS over-reporting rather than a safety concern.",
            "signals": [
                {"reaction": "Somnolence", "a": 210, "expected": 190.0, "PRR": 1.11,
                 "PRR_CI95": [0.97, 1.27], "ROR": 1.11, "ROR_CI95": [0.97, 1.27],
                 "IC": 0.14, "IC_CI95": [-0.09, 0.37], "chi2_yates": 2.1, "signal": False},
            ],
        },
        "trace": ["get_adverse_events(cetirizine)", "get_serious_event_count(cetirizine)",
                  "get_serious_reactions(cetirizine)", "compute_disproportionality(cetirizine, Somnolence)"],
    },
}


# ---------------------------------------------------------------------------
# Matching helpers — pick the closest cached example for arbitrary input.
# ---------------------------------------------------------------------------
def match_text(examples, field, text):
    """Return the example whose `field` best matches `text` (exact → substring → first)."""
    t = (text or "").strip().lower()
    for ex in examples:
        if ex[field].strip().lower() == t:
            return ex
    for ex in examples:
        ev = ex[field].lower()
        if t and (t in ev or ev in t or any(w in ev for w in t.split() if len(w) > 4)):
            return ex
    return examples[0]


def match_drug(drug):
    """Return the cached agent example for a drug name, or None if not cached."""
    d = (drug or "").strip().lower()
    aliases = {"lipitor": "atorvastatin"}
    d = aliases.get(d, d)
    return AGENT_EXAMPLES.get(d)
