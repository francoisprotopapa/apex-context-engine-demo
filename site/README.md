# Demo console (local, for the stage)

A small web app that walks through the three acts with clicks, instead of the terminal. Elastic brand, light blue.

```bash
site/run.sh                 # http://127.0.0.1:8765  (reads demo/.env, runs under EDOT so its calls show up on the scoreboard)
```

Open http://127.0.0.1:8765/ . The server listens on 127.0.0.1 only; API keys stay in the server process.

## Two modes (switch top right, or press `M`)
- **Live**: every click runs the real thing (Elasticsearch retrieval, Azure OpenAI, Agent Builder, Observability queries).
- **Practice**: every click shows the last recorded run from `site/data/practice.json`, labelled "recorded, not a new measurement".
  Agent runs are recorded 3 times and the typical run is shown, with how many of the 3 found all the key facts.

Record Practice the day before the talk (a few cents of Azure OpenAI, ~15 min):

```bash
cd demo && .venv/bin/python ../site/record_practice.py            # everything
cd demo && .venv/bin/python ../site/record_practice.py --only agent,scoreboard
```

## Pages
| Page | What it does |
|---|---|
| Try the demo | Act 1 retrieval modes side by side · Act 2 naive RAG, naive vs engineered, agents baseline vs Context Engine · Act 3 scoreboard and dashboard links. "Check the answer" panel on the right |
| How it works | Where every number comes from (the five sources) |
| Service status | The same go / no-go checks as `demo/stage.py preflight` |
| Guides | Pointers to the runbook, results and setup docs |

Keys: `←` `→` next step · `R` run again · `M` live/practice. Deep link: `/#/demo?run=Q02` (add `&mode=practice`).

## Notes
- Scoreboard looks at the last 2 hours (`SCORE_WINDOW`), so rehearsals do not pollute it. Run the CLI/steps in order on stage and it fills itself.
- The in-app browser cannot reach `~/Downloads`; start it from a terminal with `site/run.sh`.
- Not deployed anywhere: it needs the demo's keys. A public "Practice only" version (no keys) is the next step after the talk.

## Admin page
`#/admin` runs preflight, warmup, agent evaluation and Practice recording with buttons (one job at a time, live output). Local only; `APEX_ADMIN=0` disables it. Code: `site/admin.py`.

## Animated architecture (How it works)
`site/static/arch.js` draws an isometric architecture in plain SVG (no libraries): Domain data, Ingest, Elasticsearch, Secure & Govern, Retrieve & Rank, Build & Operate Agents (Agent Builder, Context Engine), Evaluate & Observe, the Agent layer and Azure OpenAI (`azure-openai-gpt-5-4-mini`).
Four scenes with the measured numbers: Overview, Act 1 (three retrieval modes on Q02), Act 2 (naive vs engineered prompt, baseline vs Context Engine agent), Act 3 (telemetry, Azure logs, billing, alert). *Auto* cycles through them; it respects `prefers-reduced-motion`.
Debug a still frame: `http://127.0.0.1:8765/?archScene=act2&archT=6.8#/how`.

