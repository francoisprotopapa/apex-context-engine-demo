# Runbook — "RAG is Broken" (AI Dev Night · Köln · 22 Oct 2026, 19:30, 45 min)

Mike Richter (Microsoft) speaks before you: Foundry Hosted Agents, governance. Your bridge: *"Mike made the agents safe. Now: what do they cost, and how do you know they're right?"*
Script to follow: `docs/SPEECH_SCRIPT.md` (the speech word for word, slide by slide and demo by demo) and `docs/TALK_SCRIPT.md` (cheat sheet with numbers and what to do if something fails), in the same order as `stage.py show`.
Deck: `DevNight_Opening_v5.pptx` (11 slides: 1 title, 2 the bet, 3 what you just saw, 4-6 Apex, the question, three acts, 7-8 architecture, 9 scoreboard filled in, 10 Q&A, 11 thank you). Driver: `demo/stage.py` (`list`, `preflight`, `warmup`, `show`, `run`, `replay`).

## Running order (45 min)

| Min | Step id | What | Slide | Command (via `stage.py`) |
|---|---|---|---|---|
| 0-3 | `bet` | Bridge + the bet (tokens of a naive RAG for ONE question) | 1-2 | none |
| 3-6 | `bet-reveal` | Naive RAG on HERO, live in the console; **reveal the bet** | (console) | `./run.sh answer HERO --mode naive` or the console |
| 6-10 | `context` | What you just saw (RAG isn't dead), Apex, the question, three acts, what is running | 3-7 | none |
| 10-14 | `act1-q02` | The vector can't tell 0117 from 0171 (main example) | | `./run.sh retrieve Q02` |
| 14-16 | `act1-q01` | The twist: keywords fail here, the vector is right by luck | | `./run.sh retrieve Q01` |
| 16-17 | `act1-q03` | Two policy versions: relevant is not valid | | `./run.sh retrieve Q03` |
| 17-18 | `act1-q04` | Veltran vs Veltrano | | `./run.sh retrieve Q04` |
| 18-21 | `act2-compare` | Recap of the bet, then engineered prompt: tokens -43%, cost -40% | | `./run.sh compare Q06` |
| 21-24 | `act2-lab` | Wrong context lab: ask for any contract (1/8 vs 8/8) | | console only |
| 24-30 | `act2-agents` | Agents: baseline vs Context Engine (+ Agents dashboard) | | console or Kibana Agent Builder |
| 30-31 | `act3-fire-alert` | Fire the alert first (one naive call); slide 8 while it warms up | 8 | `./run.sh compare Q06` or console button |
| 31-38 | `act3-dashboards` | Six beats: scoreboard, Azure logs, metrics, agents, billing, alert | | opens the tabs |
| 38-41 | `close` | Three messages, slide 9 (scoreboard filled in) | 9 | none |
| 41-45 | `qa` | Questions (cheat sheet in `stage.py show`); slide 11 when you finish | 10-11 | none |

`demo/.venv/bin/python demo/stage.py show` walks through this with a cue card per step (Enter runs, `s` skips, `r` replays the last recording, `o` opens the links).

## Demo console (alternative to the terminal)
`site/run.sh`, then http://127.0.0.1:8765 (see `site/README.md`). Same steps as `stage.py`, with clicks:

| Running order step | Console |
|---|---|
| `act1-q02`, `act1-q01`, `act1-q03`, `act1-q04` | Try the demo, Act 1: *Contract 0117 vs 0171*, *Q01 right for the wrong reason*, *Two policy versions*, *Veltran vs Veltrano* |
| `bet-reveal` | Act 2: *Naive RAG on the HERO question* (the bet), right after the bet slide |
| `act2-compare` | Act 2: *Compare: long contracts (Q06)* |
| (optional, console only, after `act2-compare`) | Act 2: *Wrong context lab: ask for any contract*: type any contract id, the truth is read from the contract; naive 1/8 right, engineered 8/8 |
| `act2-agents` | Act 2: *Agents: baseline vs Context Engine* (*Run both*, 10-40 s) |
| `act3-fire-alert` | run *Compare Q07* or the CLI once (the console runs under EDOT, so its calls count for the alert) |
| `act3-dashboards` | Act 3: *The scoreboard* and *Dashboards and the alert* |

**How it works** page: animated architecture (Overview, Act 1, Act 2, Act 3, Auto): a good backdrop for the questions or for Act 3's map; it needs no network except the page itself.

Keys: `←` `→` next step · `R` run again · `M` live/practice · `D` open/close *Under the hood* (the queries, the prompt and why right/wrong). If anything fails, **Practice** shows the last recorded run (labelled as such); `stage.py` and the CLI stay as the second fallback.
Before the talk: `site/run.sh`, check **Service status**, record Practice the day before (`site/record_practice.py`).

## Admin page (the preparation commands behind buttons)
In the console, **Admin** (top right of the menu, `http://127.0.0.1:8765/#/admin`) runs the preparation commands one at a time, with what each does, when, cost and live output:
- **Day before:** *Agent evaluation, 5 runs* (~8-10 min), then *Record Practice* (~5-6 min). *Record only the scoreboard* if just that page looks empty.
- **T-30 and T-5:** *Preflight* (must say GO), then *Warmup* (*Warmup with agents* once at T-30).
- **During the talk:** nothing.
Practice data are reloaded by the console after a recording (no restart). `APEX_ADMIN=0` hides the page (use it for the public practice-only version). The same commands from a terminal: `python3 demo/stage.py preflight|warmup [--agents]`, `python3 demo/agents_eval.py --runs 5`, `python3 site/record_practice.py`.

## Timing facts that matter
- **Azure Monitor metrics arrive 5-10 min late**: the traffic of Act 1-2 is what the Azure dashboards show in Act 3. Don't pause the demo between acts. Diagnostic logs take 1-2 min.
- **The alert looks at the last 5 minutes** (rule runs every minute): that is why `act3-fire-alert` happens right before the dashboards. The alert goes active 1-2 minutes after the call and shows as *recovered* about 5 minutes after the last big call: on the Alerts page choose **All** statuses (the console's *Dashboards and the alert* page has a *Fire the alert now* button, the list of past alerts and links that open it already on All).
- **Billing from Azure arrives the next day**: show yesterday's data or a screenshot (console scoreboard card *billed vs estimated*, dashboard *Azure billing*); the live number is an estimate (tokens x public price list).
- **An agent run takes 10-40 s**: start the baseline, then the context agent in a second tab while the first is still working.

## Checklist
**T-3 days** — Re-create local secrets if lost (`demo/.env`, `demo/.env.new`, `demo/.env.obs`, `import/config*.py`: see `docs/MIGRATION.md`). Check Azure deployment capacity (200k tokens/min on `gpt-5-4-mini`; the `gpt-4-1-mini` fallback has 300k) and the billing dashboard has data.
**T-1 day** — `demo/.venv/bin/python demo/stage.py preflight`; `demo/.venv/bin/python demo/stage.py warmup --agents`; `demo/.venv/bin/python demo/agents_eval.py --runs 5` (fills the Agents dashboard); run the whole show once with `stage.py show` **and record a screen video of each act** (backup). Write the naive HERO prompt-token number on a card (the bet; measured 7,592: re-check).
**T-30 min (venue)** — Network: if gRPC is blocked, keep `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf`. `stage.py preflight` must say GO. Open the tabs: Kibana Search (Agent Builder), Kibana Observability (Scoreboard, Azure usage and cost, Foundry overview, billing, Alerts). Dashboards on *Last 1 hour*. Mute notifications; power; external display mirrored.
**T-5 min** — `stage.py preflight` again, `stage.py warmup` (one quiet pass). Slide 1 on screen.

## Tab layout
1. Terminal (large font, dark theme, `cd demo`) — used for `stage.py show`.
2. Kibana **Search**: Agent Builder (two chats, two tabs) · Agents dashboard.
3. Kibana **Observability**: Scoreboard · Azure OpenAI usage and cost · Foundry overview · Billing · Alerts.

## What can go wrong, and what to do
| Symptom | Cause | Do |
|---|---|---|
| CLI prints 429 or hangs | Azure tokens-per-minute limit (`gpt-5-4-mini` is 200k; the baseline agent alone uses ~140k tokens per run, so avoid running two heavy things at once) | wait 60 s; `stage.py replay <step>`; say "rate limit, this is why we observe" |
| No spans on the scoreboard | OTLP blocked (gRPC behind proxy/VPN) | `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf`; otherwise show the recorded dashboard |
| Context agent ignores the AI index | LLM variance (3-4 of 5 correct on HERO); preview feature | rerun once; if it fails again, show the Agents dashboard numbers and say so |
| Agent takes > 40 s | Azure variance / many tool calls | keep talking through the tool calls; the baseline's 10+ calls are the point |
| Alert not firing | window is 5 min / naive call not sent | `stage.py run act3-fire-alert`; wait 1-2 min; show the Alerts page history |
| Azure dashboards empty | metrics delay (5-10 min) | show the logs-based dashboard (usage and cost): it is 1-2 min late |
| Kibana slow | network | have screenshots of each dashboard in the deck folder |

## Numbers cheat sheet (measured 14 and 18 Oct — re-check before the talk; `docs/RESULTS.md`)
| | naive | engineered / with Context Engine |
|---|---|---|
| Act 1 hit@1 (Q01-Q04) | semantic 75%, bm25 75% | hybrid 100% (Q02: semantic fails, bm25 + hybrid find 0171) |
| **The bet**: HERO naive prompt tokens | **7,591** (~0.011 EUR; answer has no Veltrano) | — |
| Act 2 prompt tokens, Q06 (long contracts) | 13,649 | 7,815 (-43%) |
| HERO naive vs engineered (CLI) | 7,591 | ~7,400 (-3%): **do not use HERO for the token comparison** |
| Act 2 cost per question / per 10,000 (gpt-5.4-mini, 0.726 / 4.356 EUR per 1M) | 0.0110 / ~110 EUR | 0.0070 / ~70 EUR (-36%) |
| Act 2 latency (single call) | ~1.4 s | ~1.7 s: **about the same; do not promise a gain** |
| Agents HERO correct (5 runs, 19 Oct, medians) | 1/5, 20 s, 14 LLM calls, 141k tokens | 5/5, 4 s, 2 LLM calls, 25k tokens |
| Agents Q09 same group / Q10 spend share (19 Oct) | 5/5 (16 s, 14 calls, 120k) / 4/5 (19 s, 18 calls, 170k) | 5/5 (3 s, 2 calls, 25k) / 5/5 (2 s, 2 calls, 24k) |
| Wrong context lab: notice period of 8 contracts | naive 1/8 right (same 3 documents every time) | engineered 8/8 |
| Cost, billed vs estimated (13-18 Oct, mixed models) | estimate 5.91 EUR (upper bound: no cache discount) | billed 3.87 EUR; monitoring plumbing 8.19 EUR (14-18 Oct). On 13-14 Oct (light usage) it was 2.17 vs 2.06 |
| Alert | fires above 10,000 prompt tokens in one call (naive 11-15k, engineered < 8k) | |

## Key lines (English)
- *Identifiers are facts, not similarities.* (Act 1)
- *Same question, same model, same data. Only the context changes.* (Act 2)
- *The win is tokens and cost: for a single call the latency is about the same, because the answer length dominates.* (Act 2, say it before someone asks)
- *The context agent uses a tool of ours that wraps the AI index lookup; Context Engine is a private preview.* (Act 2)
- *Every number on this scoreboard was measured tonight, not copied from a slide.* (Act 3)

## After the event
Delete the Azure resources (`az group delete -n <rg>`, `az ad sp delete --id <client id>`), the Kibana API keys (`apex-provisioning`, the OTLP key if shared) and the Azure OpenAI key if it leaked on screen. Make the repo public (it contains the answers: `docs/STORY.md`, `eval/golden_questions.jsonl`).
