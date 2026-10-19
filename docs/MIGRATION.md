# Migrating the demo to a new Elastic Serverless project

Everything except the credentials is in this repo. The old project keeps working (nothing below touches it).

## 0. Create the project (Elastic Cloud console)
- Type: **Elasticsearch** (general purpose / not "vector database") on **Azure germanywestcentral**.
- Note: Endpoint (Elasticsearch URL), Kibana URL, and create an **API key** with full access for the import.
- Check that Context Engine is available: Stack Management -> Advanced Settings -> `contextEngine:enabled`.

## 1. Fill the new config files (both git-ignored; do not paste keys in chat)
- `import/config_new.py`  -> `ES_URL`, `ES_API_KEY` of the NEW project.
- `demo/.env.new`         -> `ES_URL`, `ES_API_KEY`, `KIBANA_URL`, Azure OpenAI values (same endpoint/key/deployment as the old `.env`), `OTEL_*` unchanged.

## 2. Check the new project
```bash
demo/.venv/bin/python tools/provision.py --env demo/.env.new check
```
Expect `build_flavor: serverless` and `jina embeddings present: True`. If Jina is missing, set `TEXT_INFERENCE_ID` in `import/config_new.py` to an available text-embedding endpoint (and tell me: the semantic_text mappings will use it).

## 3. Import the data (15 indices, ~9,260 docs)
```bash
cd import && ../demo/.venv/bin/python import_apex.py --config config_new.py
```
Add `--recreate` to wipe and rebuild. The `content.codes` / `text.codes` subfields are in `mappings.json` already.

## 4. Azure OpenAI as chat model for the agents
```bash
demo/.venv/bin/python tools/provision.py --env demo/.env.new azure
```
Creates the inference endpoint `azure-openai-gpt-5-4-mini` (the key is read from the env file, never printed).

## 5. Context Engine AI index (UI, ~5 min)
Context -> create AI index `apex-supplier-intelligence`; description and sources as in `context_engine/SETUP.md`
(sources: `apex_suppliers`, `apex_corporate_news`, `apex_contracts`, ES|QL `FROM apex_policy_vault | WHERE topic == "third_party_risk"`).

## 6. Knowledge indicators
```bash
demo/.venv/bin/python tools/provision.py --env demo/.env.new workflows
```
Then in the AI index page attach both workflows (`supplier-intelligence-sources` for metadata, `apex-targeted-kis` for the hand-verified KIs) and run them. Expect 4 `index_metadata` + 7 targeted KIs.
(If the script cannot create a workflow, paste `kibana_export/workflow.*.yaml` in Workflows -> Create workflow.)

## 7. Agents and tools
```bash
demo/.venv/bin/python tools/provision.py --env demo/.env.new agents
```
Creates the 5 `index_search` tools and the 2 agents (`apex-analyst-baseline`, `apex-analyst-context`).

## 8. Smoke tests
The demo CLI reads `demo/.env`. Switch to the new project (keeping the old one as a backup), then test:
```bash
cp demo/.env demo/.env.old-cluster && cp demo/.env.new demo/.env
cd demo && PATH="$PWD/.venv/bin:$PATH" ./run.sh compare Q06
.venv/bin/python agents_eval.py --runs 1
```
To go back: `cp demo/.env.old-cluster demo/.env`.

## 9. Observability project (only if it is also new)
```bash
RG=<rg> AOAI=<azure openai resource> ./azure/setup_monitoring.sh          # Azure side, writes demo/.env.azure-monitor
python3 tools/provision_obs.py --env demo/.env.obs --azure-env demo/.env.azure-monitor all
python3 tools/provision.py --env demo/.env.new dashboards                  # Agents dashboard (Search project)
```
See `observability/README.md` (an Elastic Agent in a container is needed for the Event Hub logs).

## What does NOT move
- Observability project and the Azure resources stay as they are unless you redo step 9.
- Old KIs/agents live in the old project only; this procedure recreates them.
