# Apex Conglomerate — Context Engine edition

**RAG is broken: how Elastic & Azure fix context, latency and token bills.**
Demo material for the *AI Dev Night with Microsoft and Elastic* (Cologne, 22 Oct 2026).

A synthetic multi-industry dataset (finance, manufacturing, pharma, telco, IT), extended from
[apex-conglomerate-search-ai](https://github.com/francoisprotopapa/apex-conglomerate-search-ai)
for **Elastic Cloud Serverless**, **Context Engine**, **Agent Builder** and **LLM Observability on Azure**.

```
data/
  core/            5 original indices (customers, interactions, payments, telemetry, pharma batches)
  extra_mile/      6 original indices (+ Third-Party Risk policy v1.0 2024 / v2.0 2026)
  context_engine/  NEW: apex_suppliers · apex_contracts · apex_corporate_news · apex_service_tickets
  multimodal/      optional (not needed for this use case)
eval/              golden_questions.jsonl — expected answers for accuracy monitoring
import/            Serverless import (mappings + script; --config targets another project)
context_engine/    AI index, hand-verified KIs (apex-targeted-kis workflow), acceptance checks
agents/            Agent Builder: baseline vs Context Engine (tools, instructions, results)
kibana_export/     tools, agents and workflows as JSON/YAML, recreated by tools/provision.py
demo/              CLI demo (retrieval modes, naive vs engineered prompts, EDOT) + agents_eval.py + stage.py (stage driver)
site/              demo console (web app with clicks for the stage: live or recorded practice mode)
observability/     LLM observability: Azure integrations, dashboards (ndjson), alert, scoreboard queries
azure/             setup_monitoring.sh — Azure side (service principal, Event Hub, diagnostics, Elastic Agent)
tools/             build_dataset.py (deterministic data) · provision.py (Search project) · provision_obs.py (Observability project)
docs/              STORY.md (answers) · RESULTS.md (measured results) · RUNBOOK.md (the 45-min show) · MIGRATION.md (new project)
```

## Architecture in one picture

| Source | How it gets in | Lands in | You see it in |
|---|---|---|---|
| Demo CLI | OpenTelemetry (EDOT) → managed OTLP endpoint | **Observability** project · `traces-*` | Scoreboard dashboard + alert (> 10k prompt tokens) |
| Agent Builder (2 agents) | built-in trace collection | **Search** project · `traces-agent_builder.otel-*` | Agents dashboard |
| Azure Monitor metrics | Azure AI Foundry integration, agentless | Observability · `metrics-azure.ai_foundry-*` | Foundry Overview |
| Azure diagnostic logs | Event Hub → Elastic Agent (container) | Observability · `logs-azure_ai_foundry.logs-*` | Azure OpenAI usage, latency and cost |
| Azure Cost Management | Azure Billing integration, agentless | Observability · `metrics-azure.billing-*` | Cognitive Services Billing (next day) |

Two Serverless projects on purpose: **Search** (data, Context Engine, agents) and **Observability** (everything measured).


## Quickstart

```bash
# 1. data -> Search project (Elasticsearch Serverless)
cd import && cp config.example.py config.py   # ES_URL, ES_API_KEY, TEXT_INFERENCE_ID
pip install -r requirements.txt
python3 import_apex.py                         # add --recreate to start clean, --with-multimodal if wanted

# 2. Kibana objects: Azure OpenAI inference endpoint, tools, agents, workflows, Agents dashboard
cp demo/.env.example demo/.env.new && edit it # ES_URL, ES_API_KEY, KIBANA_URL, Azure OpenAI ...
python3 tools/provision.py --env demo/.env.new all
# 3. Context Engine: create the AI index in the UI, then run the workflows -> context_engine/SETUP.md
# 4. Agents                              -> agents/SETUP.md
# 5. Observability project: Azure side + integrations + dashboards + alert -> observability/README.md
# 6. Demo CLI (./run.sh compare Q06, agents_eval.py), stage driver      -> demo/README.md, docs/RUNBOOK.md

# Moving to a new project, step by step: docs/MIGRATION.md
```

Every free-text field is indexed twice: as `text` (BM25 — exact codes such as `APX-MSA-2024-0117`)
and via `copy_to` into `<field>_semantic` (`semantic_text`), so hybrid search works on every index.

## What's new vs the original dataset

| Index | Docs | Purpose in the demo |
|---|---|---|
| `apex_suppliers` | 24 | master data + 2025 spend; parent company **not** disclosed |
| `apex_corporate_news` | 95 | press releases & registry extracts (EN/DE/IT/FR); the hidden ownership chain + decoys |
| `apex_contracts` | 72 | long MSAs/SLAs/SOWs (up to ~33k chars) with near-duplicate contract numbers |
| `apex_service_tickets` | 578 | maintenance tickets linked to telemetry anomalies; near-duplicate part codes (+4 spare-parts catalogue entries, Q05); cold-chain excursions |
| `apex_policy_vault` | +9 chunks | Third-Party Risk policy v1.0 (40%, 2024) and v2.0 (30%, 2026, group level) |

Also: five customer records that used the names of real public figures now use fictional names, and
suppliers in the knowledge graph carry company names instead of `Supplier-N`.

> ⚠️ `docs/STORY.md` and `eval/golden_questions.jsonl` contain the answers. Keep the repository
> private until after the talk.

Dataset content is entirely synthetic and fictional. MIT License.
