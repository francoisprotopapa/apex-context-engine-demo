# CLAUDE.md — handoff for Claude Code

Talk to François in **Italian** (he presents in English/German). Keep answers concise and technical.

## What this is

Demo repo for François Protopapa (Principal SA, Elastic) — evening tech talk
**"RAG is Broken: How Elastic & Azure Fix Context, Latency, and Token Bills"**,
AI Dev Night with Microsoft and Elastic, KölnBusiness, **22 Oct 2026, ~19:30, 45 min**, ~47 RSVPs
(developers, AI/ML engineers, cloud architects, security). Mike Richter (Microsoft) speaks before
(Foundry Hosted Agents + Elastic, agent governance, "ELK Burgers"). No coordination with Mike possible.

Story: Apex Conglomerate. Guiding question: *"Which of our suppliers could expose ApexPharm to
compliance risk, and what do our contracts let us do about it?"* — full answers in `docs/STORY.md`.
Talk structure: bridge from Mike → Apex case → Act 1 wrong context (exact codes, stale policy, decoys)
→ Act 2 too much context (naive vs engineered prompt; Context Engine vs baseline agent)
→ Act 3 invisible context (observability scoreboard + "real receipt") → Q&A.

## Environment

- Two Elastic Cloud **Serverless** projects, region **Azure germanywestcentral**: **Search** (data, Context Engine, agents, agent traces)
  and **Observability** (CLI traces, Azure metrics/logs/costs, dashboards, alert). URLs and keys live only in git-ignored files:
  `import/config*.py`, `demo/.env*` (see `.env.example`). **Never print, commit or echo keys.**
- Azure OpenAI deployment `gpt-5-4-mini` (model gpt-5.4-mini, DataZoneStandard, 200k TPM; Data Zone EU, do not claim "data stays in Germany"). Until 19 Oct the demo ran on `gpt-4-1-mini` (still deployed, 300k TPM, as a fallback: `demo/.env.gpt41mini`).
- Embeddings: `.jina-embeddings-v5-text-small` (verified OK).

## Status (14 Oct)

Done and verified: import (15 indices, 9,264 docs), Act 1 retrieval (`content.codes` fix), Act 2 CLI (tokens -43%, cost -40%),
Context Engine KIs (11: 4 metadata + 7 hand-verified, workflow `apex-targeted-kis`), agents baseline vs context (+ tool `apex_context_lookup`),
Azure OpenAI as inference endpoint, EDOT traces, Azure monitoring (metrics, logs via Event Hub + Elastic Agent in ACI, billing),
dashboards (observability/dashboards), alert (> 10k prompt tokens), deck `DevNight_Opening_v2.pptx` (outside the repo).
Results and caveats: `docs/RESULTS.md`. The show: `docs/RUNBOOK.md` and `demo/stage.py` (preflight, warmup, show, replay). Move to a new project: `docs/MIGRATION.md`.

Open points: billing dashboard needs ~1 day of data; re-run `agents_eval.py --runs 5` and the CLI the day before for a clean scoreboard;
rehearse on the event network and record a backup video of each act; delete Azure resources and API keys after the event
(`az group delete`, `az ad sp delete`, Kibana API keys); keep the repo private until after the talk.

## Guardrails

- Context Engine is **private preview / experimental** — don't present it as GA; don't invent APIs:
  follow the Elastic docs, say when something is unverified. The agent result relies on the custom tool `apex_context_lookup`: say so.
- Don't promise a latency win for naive vs engineered (single call): tokens and cost are the win (`docs/RESULTS.md`).
- Data is synthetic; regenerate with `python3 tools/build_dataset.py` (deterministic) rather than hand-editing NDJSON.
- Keep the repo private until after the talk (it contains the answers).
