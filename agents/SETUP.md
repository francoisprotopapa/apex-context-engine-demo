# Agent Builder setup — baseline vs Context Engine

Goal on stage: ask the **same question** to two agents that differ only in context, and compare tool calls, tokens, time and correctness
(Agents dashboard, built on the Agent Builder traces). `tools/provision.py ... agents` creates tools and agents from `kibana_export/`.

## 1. LLM: Azure OpenAI as an inference endpoint
Connectors for LLMs are deprecated in this project: use an **inference endpoint** (Dev Tools -> Console, paste the key from your clipboard):

```
PUT _inference/chat_completion/azure-openai-gpt-5-4-mini
{ "service": "azureopenai",
  "service_settings": { "api_key": "<KEY>", "resource_name": "<azure resource>", "deployment_id": "gpt-5-4-mini", "api_version": "2024-10-21" } }
```

(`python3 tools/provision.py --env demo/.env.new azure` does the same from the env file.) The endpoint id is the model id in Agent Builder and in the API
(`connector_id` of `/api/agent_builder/converse`). Use the same deployment for both agents and for the CLI. Raise the deployment capacity: an agent run
burns 50-300k tokens in seconds (50k TPM gives 429s; we use 300).

## 2. Tools (type `index_search`, one per index)
`apex_suppliers_search`, `apex_corporate_news_search`, `apex_contracts_search`, `apex_policy_vault_search`, `apex_service_tickets_search`.
Do **not** add `apex_knowledge_graph` (explicit relationships would shortcut the demo).

## 3. Agent A — `apex-analyst-baseline`
The 5 tools, the shared instructions below, `enable_elastic_capabilities: false` (otherwise it also gets the Context Engine tools). No AI index.

## 4. Agent B — `apex-analyst-context`
Same as A, plus `ai_indices: ["apex-supplier-intelligence"]`, the tools `platform.context_engine.{list_ai_indices,describe_ai_index,query_ai_indices}`
and the custom ES|QL tool **`apex_context_lookup`** (hybrid lookup on the AI index, takes the user's question as parameter), and a short protocol in the instructions
(call `apex_context_lookup` ONCE first, answer from it if it is enough, at most ONE more targeted call; see `kibana_export/agent.apex-analyst-context.json`).
The "once" matters with gpt-5.4-mini: with the looser protocol it explored (17 LLM calls, 163k tokens on HERO); with this one it takes about 4 calls and 44k tokens (`docs/RESULTS.md`).

> Why the extra tool: with the AI index merely attached, gpt-4.1-mini (and gpt-5.4-mini) rarely query it, and when it does it writes SQL or weak ES|QL.
> With the tool: 14/15 correct vs 3/15 for the baseline (`docs/RESULTS.md`). Say on stage that it is a tool that wraps the AI index lookup.

## 5. Shared instructions (both agents)

```
You are a procurement and third-party-risk analyst at Apex Conglomerate.
Always answer with: the suppliers concerned, the evidence (document or contract IDs),
the applicable policy version and threshold, and the contractual options with clause numbers.
If ownership is relevant, determine the ultimate parent company before assessing concentration.
Never guess: if the data does not support a conclusion, say so.
When you identify a corporate group, name every company of it that the evidence mentions, including acquired ones.
If Context Engine AI indices are available to you (list_ai_indices), query them first (query_ai_indices) for ownership, corporate groups and contract clauses, before searching the raw indices.
```

## 6. Questions for the stage (from `eval/golden_questions.jsonl`)
1. **HERO** — *Which of our suppliers could expose ApexPharm to compliance risk, and what do our contracts let us do about it?*
2. **Q09** — *Which of our ApexPharm suppliers belong to the same corporate group?*
3. **Q10** — *What share of ApexPharm critical supplier spend sits with a single corporate group?*

Expected from B: Veltrano Holding (Rheinchem + Lumen via Orvia, Kestrel directly), 32.5% > 30% (TPRM v2.0), the regulator review, clauses 14.3 / 12.6 / 9.4.
A typically burns 10-14 tool calls and 14 LLM calls and misses the group or confuses the policy versions.

## 7. Compare and trace
`python3 demo/agents_eval.py --runs 5` (keyword rubric, writes `agents_eval_results.json`).
Agent Builder collects traces by default (Stack Management -> AI -> GenAI Settings -> Agent Builder Traces); they land in the **same project** as the agent,
data stream `traces-agent_builder.otel-*`. The Agents dashboard (`observability/dashboards/agents-baseline-vs-context-SEARCH-project.ndjson`,
`tools/provision.py dashboards`) shows time, LLM calls, tool calls and tokens per agent.
