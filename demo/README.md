# Demo CLI

Terminal demo for Acts 1 and 2. Every command is traced with OpenTelemetry (EDOT), so the
numbers on screen are the same numbers that appear in Kibana afterwards.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
edot-bootstrap --action=install
cp .env.example .env      # Elasticsearch, Azure OpenAI, prices, OTLP endpoint, KIBANA_URL
```

- `run.sh` calls `opentelemetry-instrument`: activate the venv, or `PATH="$PWD/.venv/bin:$PATH" ./run.sh ...`.
- `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf` is in `.env.example`: gRPC fails behind some corporate VPNs/proxies (ALPN error).
- Quote values with spaces in `.env` (`OTEL_EXPORTER_OTLP_HEADERS="Authorization=ApiKey ..."`), `run.sh` sources the file.
- `PRICE_IN_PER_1M` / `PRICE_OUT_PER_1M` (EUR) make `cost` appear in the table, the spans and the scoreboard.
  Used in the demo: 0.726 / 4.356 (Azure retail price list, EUR, gpt-5.4-mini Data Zone, Germany West Central, 19 Oct 2026; check yours). For gpt-4.1-mini it was 0.40 / 1.50. Cached input tokens are billed at one tenth of the input price, the estimate ignores that.

## Stage script

| Act | Command | What the audience sees |
|---|---|---|
| 1 · wrong context | `./run.sh retrieve Q01` then `./run.sh retrieve Q02` | semantic search returns the near-duplicate contract (0117 ↔ 0171); BM25 and hybrid get it right |
| 1 · stale policy | `./run.sh retrieve Q03` | v1.0 (40%) vs v2.0 (30%) |
| 1 · decoy name | `./run.sh retrieve Q04` | *Veltran* vs *Veltrano* |
| 1 · German query | `./run.sh retrieve Q05` | control: all modes return the spare-parts catalogue entry for `RCX-4410-A` first, `-B` right behind |
| 2 · too much context | `./run.sh compare Q06` | naive: 3 whole contracts in the prompt · engineered: the relevant clauses only — token and **cost** deltas (-43% / -40%); latency is about the same, say so |
| 2 · accuracy | `./run.sh eval --act act2` | accuracy and total prompt tokens per mode |
| free | `./run.sh ask "…" --index apex_contracts` | audience question (pick from 3 prepared ones) |

`RERANK_INFERENCE_ID` (optional) adds a `rerank` mode on top of hybrid.
`PRICE_IN_PER_1M` / `PRICE_OUT_PER_1M` (optional) show cost — use your Azure price sheet.

Rehearse every command on the event network and record a backup video of each act.

## Agents (Act 2, second half)

```bash
python agents_eval.py --runs 5      # baseline vs Context Engine through the Agent Builder converse API
```

Needs `KIBANA_URL` (Search project) in `.env`. Correctness is a keyword rubric (`HERO`: Veltrano, 32.5, 14.3, 12.6, 9.4), not an LLM judge.
Results are written to `agents_eval_results.json` (git-ignored). Pause between calls (`--pause`) keeps Azure under its tokens-per-minute limit.
Reference results and caveats: `../docs/RESULTS.md`.

## Rehearsal checklist
- Run the CLI under EDOT, then check the spans in Discover (`traces-*`, `service.name == "apex-rag-demo"`).
- Clean scoreboard: run `compare Q06`, `eval --act act2`, `retrieve Q01..Q05` and `agents_eval.py` once, set the dashboards to *Last 1 hour*.
- Latency of a single Azure call varies a lot (2-9 s); never promise a number, show the median.

## Stage driver (the 45-minute show)

```bash
.venv/bin/python stage.py list          # running order with minutes
.venv/bin/python stage.py preflight     # go / no-go (run 30 and 5 minutes before)
.venv/bin/python stage.py warmup        # one quiet pass; add --agents for one agent run each
.venv/bin/python stage.py show          # cue card + command per step; Enter runs, r replays the last recording
.venv/bin/python stage.py replay all    # offline fallback: re-play the last recorded output of every step
```

Every live run is recorded in `stage_cache/` (git-ignored), so `replay` works if the network or Azure fail. See `../docs/RUNBOOK.md`.
