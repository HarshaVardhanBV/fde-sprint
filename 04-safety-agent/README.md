# 04 — Safety-Signal Agent (Week 3, in progress)

A tool-use **agent** for pharmacovigilance: given a drug, it pulls real FDA
adverse-event data (openFDA) and flags potential safety signals. Where Projects
1–2 were a single Claude call, this one runs in a **loop** — it decides what data
it needs, fetches it, reasons, and answers.

## The mental model
```
Project 1/2 (single call):   question ─▶ Claude ─▶ answer

Agent (loop):                question ─▶ Claude ─▶ "call get_adverse_events(atorvastatin)"
                                            ▲                    │
                                            │              run the tool (openFDA)
                                            └──── tool result ◀──┘
                                         ...loop until Claude answers instead of calling a tool
```

## Files
| File | What it is |
|---|---|
| `agent.py` | The agent: one openFDA tool + the loop. Heavily commented. |

## Run
```bash
cd 04-safety-agent
python3 -m venv .venv && source .venv/bin/activate
pip install anthropic requests python-dotenv
# edit .env and paste your real key:  ANTHROPIC_API_KEY=sk-ant-...
python agent.py atorvastatin        # try any generic drug name
```
> The key lives in `.env` (gitignored — never committed). `load_dotenv()` reads it at startup.

## The three parts of any tool-use agent
1. **Tool** — a plain Python function (`get_adverse_events`) that does real work (hits openFDA).
2. **Schema** — a JSON description the model sees, so it knows the tool exists and when to use it.
3. **Loop** — call the model; if `stop_reason == "tool_use"`, run the tool(s), feed results back, repeat; stop on a text answer. `max_turns` caps it so it can't loop forever.

## Status / next
- [x] Day 17 — agent loop + openFDA tool (this file)
- [ ] Day 18 — 2nd tool (serious-event count) + safety-signal assessment (+ confidence)
- [ ] Evaluate it with the `03-evals` harness (before/after on a 15–20 case table)
- [ ] Deploy + design write-up
