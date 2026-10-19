# LLM Observability — what we monitor and how

Four layers, all landing in Elastic. Two Serverless projects on purpose: **Search** (data, Context Engine, agents) and
**Observability** (everything measured). `tools/provision_obs.py` and `azure/setup_monitoring.sh` recreate this layer.

| Layer | What it shows | How it gets in | Where |
|---|---|---|---|
| **A. Azure platform** | requests, tokens, availability per deployment (metrics) | Azure AI Foundry integration, **agentless** (service principal, Monitoring Reader) | Observability · `metrics-azure.ai_foundry-*` |
| **B. Azure logs** | one record per call: duration, tokens, status | diagnostic settings -> Event Hub -> **Elastic Agent in a container** (the agentless API leaves the Event Hub input disabled) | Observability · `logs-azure_ai_foundry.logs-*` |
| **C. Azure cost** | billed cost per day | Azure Billing integration, agentless (Cost Management Reader); arrives with a delay of hours | Observability · `metrics-azure.billing-*` |
| **D. Our app** | every demo step: retrieval mode, prompt size, tokens, cost, accuracy | EDOT Python -> managed OTLP endpoint | Observability · `traces-*` |
| **E. Agents** | agent runs, LLM calls, tool calls, tokens | Agent Builder trace collection (on by default) | **Search** · `traces-agent_builder.otel-*` |

## Set up

```bash
# Azure side (needs `az login`): service principal, Event Hub, diagnostics, storage; writes demo/.env.azure-monitor
RG=rg-apex-demo AOAI=<azure-openai-resource> ./azure/setup_monitoring.sh

# Observability project (an Observability Serverless project, with a Kibana API key in demo/.env.obs)
python3 tools/provision_obs.py --env demo/.env.obs --azure-env demo/.env.azure-monitor integrations
#   -> start the Elastic Agent in ACI as printed by azure/setup_monitoring.sh (logs input needs an agent)
python3 tools/provision_obs.py --env demo/.env.obs dashboards
python3 tools/provision_obs.py --env demo/.env.obs alert
python3 tools/provision.py --env demo/.env.new dashboards      # Agents dashboard goes to the SEARCH project
```

`demo/.env.obs`: `OBS_KIBANA_URL=` and `OBS_API_KEY=` (Kibana -> Stack Management -> API keys). Delete the key after provisioning.
The demo CLI sends traces with `OTEL_EXPORTER_OTLP_*` (Add data -> OpenTelemetry in the Observability project), see `demo/README.md`.

## Dashboards (`observability/dashboards/*.ndjson`)

| Dashboard | Project | Data |
|---|---|---|
| Scoreboard — RAG is Broken | Observability | traces (naive vs engineered, hit@1, tokens per question, receipt, cost per 10,000 questions) + Azure logs (latency, tokens, estimated cost) |
| [LLM Observability] Azure OpenAI — usage, latency and cost | Observability | Azure logs: calls, tokens, p95 latency, estimated cost per 15 min, status |
| [LLM Observability] Azure Foundry — Overview (dedicated data view) | Observability | Azure metrics: requests, tokens, models, availability |
| Agents — baseline vs Context Engine | **Search** | Agent Builder traces: run time, LLM calls, tool calls, tokens |
| [LLM Observability] Azure billing: cost by product (dedicated data view) | Observability | billed cost per product from Cost Management (appears the day after); copy of the managed Billing dashboard on `metrics-azure.billing-dedicated`, no warnings |

**Navigation and stars.** The four Observability dashboards share a link bar at the top (1 Scoreboard · 2 Azure OpenAI usage and cost · 3 Foundry overview · 4 Azure billing), so you never land on the managed copies. Each link keeps the target's own time range. Re-apply with `python3 tools/relink_dashboards.py --env demo/.env.obs` (e.g. after importing the exports). Stars are per user and the API refuses them for API keys: click the star on the four dashboards (and on *Agents* in the Search project) once, then filter Dashboards by *Starred*.

Why copies instead of the managed dashboards: the managed ones use the generic `metrics-*` data view and show red "field not found" warnings
(the data view also matches indices where the field does not exist). The copies use `metrics-azure.ai_foundry-*`.
The managed *API Management* and *Guardrails* dashboards need Azure **API Management gateway logs** (`properties.backend_request_body.*`);
with direct diagnostics they stay empty. Put API Management in front of the model if you want them.

## Alert

`alert-prompt-too-large.json`: ES|QL rule, every minute, `prompt_tokens > 10,000` in one call in the last 5 minutes on `traces-*`.
Naive prompts are 11-15k tokens, engineered ones below 8k, so it fires on the naive call and recovers after 5 minutes.
(The original idea of 20,000 never fires with these questions.)

## Scoreboard queries (ES|QL)

Field names are OTel-native: span attributes live under `attributes.*`. Verified on the demo's spans (`attributes.apex.*`).

```esql
FROM traces-*
| WHERE service.name == "apex-rag-demo" AND attributes.apex.act == "act2" AND attributes.apex.prompt_tokens IS NOT NULL
| STATS prompt_tokens = ROUND(AVG(attributes.apex.prompt_tokens)), llm_ms = ROUND(AVG(attributes.apex.llm_latency_ms)),
        accuracy_pct = ROUND(100 * AVG(CASE(attributes.apex.eval.correct == true, 1.0, 0.0))), runs = COUNT(*)
  BY mode = attributes.apex.mode
```

```esql
FROM traces-*
| WHERE service.name == "apex-rag-demo" AND attributes.apex.act == "act1" AND attributes.apex.question_id != "Q05"
| STATS hit_at_1_pct = ROUND(100 * AVG(CASE(attributes.apex.hit_at_1 == true, 1.0, 0.0))), runs = COUNT(*) BY mode = attributes.apex.mode
```

Cost per 10,000 questions (needs `PRICE_*` in `.env`):

```esql
FROM traces-*
| WHERE service.name == "apex-rag-demo" AND attributes.apex.act == "act2" AND attributes.apex.cost_eur > 0 AND @timestamp > NOW() - 24 hours
| STATS runs = COUNT(*), eur_per_question = ROUND(AVG(attributes.apex.cost_eur), 5) BY mode = attributes.apex.mode
| EVAL eur_per_10k_questions = ROUND(eur_per_question * 10000, 2)
```

Azure side, from the diagnostic logs (latency per call, estimated cost):

```esql
FROM logs-azure_ai_foundry.logs-*
| WHERE azure.ai_foundry.category == "RequestResponse" AND @timestamp > NOW() - 24 hours
| STATS calls = COUNT(*), avg_ms = ROUND(AVG(azure.ai_foundry.duration_ms)), p95_ms = ROUND(PERCENTILE(azure.ai_foundry.duration_ms, 95)),
        prompt_tokens = SUM(azure.ai_foundry.properties.prompt_tokens), completion_tokens = SUM(azure.ai_foundry.properties.completion_tokens)
  BY deployment = azure.ai_foundry.properties.model_deployment_name
| EVAL cost_eur = ROUND((prompt_tokens * 0.726 + completion_tokens * 4.356) / 1000000, 4)   // gpt-5.4-mini; the console prices each model separately (site/app.py MODEL_PRICES)
```

Agents (Search project): per agent run, join the `invoke_agent`, `chat` and `execute_tool` spans of a `trace_id`; see the Agents dashboard.

## Things that cost us time
- **Latency metrics are empty** (`time_to_response`...): Azure does not emit them for this deployment. Use the logs (`duration_ms`) or the traces.
- **Costs**: the live number is an estimate (tokens x price list); the billed number arrives the next day and includes other services (Event Hub, container).
- **Agentless + Event Hub**: not supported by the managed-integrations API in this project; use a normal agent policy.
- **Cleanup**: `az group delete -n <rg>`, `az ad sp delete --id <client id>`, delete the Kibana API keys.
