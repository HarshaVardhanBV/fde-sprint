# Portfolio Hub — Streamlit front end

One multi-page Streamlit app that demos all three FDE pharma systems from a single URL.
Thin UI: the API-backed projects call their **live Railway backends**; the agent runs
**in-process**.

## Pages
| Page | What it does | Backend |
|---|---|---|
| 🩺 AE Triage | free-text AE report → structured triage | FastAPI on Railway (`/triage`) |
| 📄 Regulatory Q&A | question → cited answer from ICH/FDA docs | FastAPI + ChromaDB on Railway (`/ask`) |
| ⚠️ Safety Agent | drug → tool-use agent → structured verdict | runs `agent_core.py` in-process (openFDA + Claude) |

## Run locally
```bash
cd portfolio-hub
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
mkdir -p .streamlit && cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# edit .streamlit/secrets.toml -> paste your real ANTHROPIC_API_KEY
streamlit run Home.py
```
Only the **Safety Agent** page needs the key; Triage and Q&A just call the Railway APIs.

## Deploy to Streamlit Community Cloud (one time, ~5 min)
1. Push `fde-learning` to GitHub (if not already).
2. Go to https://share.streamlit.io → **New app** → pick the repo.
3. **Main file path:** `portfolio-hub/Home.py`
4. **Advanced → Secrets:** paste the contents of `secrets.toml.example` with your real
   `ANTHROPIC_API_KEY`.
5. Deploy → you get one public URL for the whole portfolio.

> Why Community Cloud (not Railway) for the UI: it's free, purpose-built for Streamlit,
> and deploys straight from the repo. The FastAPI backends stay on Railway. Match the
> platform to the layer.

## Architecture note (interview-ready)
The UI is deliberately thin — a front end over already-deployed services. Triage and
Q&A demonstrate a clean **frontend/backend split** (UI calls a typed API); the agent
runs in-process because `run_agent()` is an importable function that returns a validated
`Verdict` plus a tool-call trace (shown in the "How the agent worked" expander).

`agent_core.py` is a deployment copy of `../04-safety-agent/agent.py` — change behaviour
in both.
