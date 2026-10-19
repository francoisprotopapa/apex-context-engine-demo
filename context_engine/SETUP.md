# Context Engine setup (Serverless)

> Context Engine is **private preview / experimental**. Requirements per the
> [quickstart](https://www.elastic.co/docs/explore-analyze/ai-features/context-engine/quickstart):
> an Elastic Cloud Serverless project (or Stack 9.6 + Enterprise license), permission to change
> Advanced Settings, and permission to create/run Workflows and manage AI indices.
> UI labels below follow the quickstart; check the docs if a label has moved.

## 0. Enable it

Kibana → **Stack Management → Advanced Settings** → search *Context Engine* → enable
`contextEngine:enabled` (per Kibana space) → open **Context** from the navigation.

## 1. Create the AI indices

Create two AI indices. Name and description matter: agents use them to decide when an AI index is relevant.

### `apex-supplier-intelligence`  (demo: RELATE + PRECOMPUTE)

Description (paste as is):

> Context about Apex Conglomerate's suppliers and third-party risk: supplier master data and spend,
> ownership and corporate-group relationships derived from press releases and registry extracts,
> key clauses of supplier contracts (change of control, termination, disclosure duties), and the
> Third-Party Risk Management policy (current version 2.0). Use it for questions about supplier
> groups, concentration risk, compliance exposure and contractual remedies. It does not contain
> customer, payment or telemetry data.

Sources (Elasticsearch data / ES|QL):

| Source | Why |
|---|---|
| `apex_suppliers` | master data, criticality, 2025 spend — parent company is *not* disclosed |
| `apex_corporate_news` | the only place where ownership appears (4 documents, 3 languages) |
| `apex_contracts` | 72 long contracts; key clauses to precompute as facts |
| ES\|QL: `FROM apex_policy_vault \| WHERE topic == "third_party_risk"` | TPRM policy v1.0 (2024) and v2.0 (2026) |

### `apex-operations-map`  (demo: MAP, optional)

> Context about Apex industrial operations: asset telemetry, maintenance tickets, spare parts and
> technical documentation. Use it to trace failures across assets, tickets and suppliers.

Sources: `apex_operational_telemetry`, `apex_service_tickets`, `apex_technical_docs`, `apex_it_knowledge_base`.

## 2. Automations → Knowledge Indicators

For each AI index:

1. **Automations → Suggest automation.** Agent Builder proposes the *Index/Table Metadata*
   automation (one `index_metadata` KI per source: what it contains, limitations, verified ES|QL).
   Approve it, then ask Agent Builder to **run** it. This is the "semantic metadata" layer of the slide.
2. Add automations for the other KI types (see
   [Create and manage automations](https://www.elastic.co/docs/explore-analyze/ai-features/context-engine/create-and-manage-automations)):
   - **Entities & relationships** over `apex_corporate_news` + `apex_suppliers` — goal: an ownership
     map (Orvia → Veltrano; Rheinchem, Lumen → Orvia; Kestrel → Veltrano).
   - **Facts & summaries** over `apex_contracts` — goal: per contract, the change-of-control,
     disclosure and termination clauses with clause numbers.
3. **Evaluate** the generated KIs
   ([Evaluate and improve KIs](https://www.elastic.co/docs/explore-analyze/ai-features/context-engine/evaluate-and-improve-knowledge-indicators))
   against `eval/golden_questions.jsonl` (Q09, Q10, Q12, HERO).

**Run the automations the day before the event** (precompute has a one-off token cost) and schedule
a refresh, so nothing is computed live on stage.

## 3. What the KIs must contain (acceptance check)

- Rheinchem Pharma Services, Lumen Analytics Lab and Kestrel Cold Chain → same group, **Veltrano Holding S.A.**
- Veltran Logistik → **not** related (family-owned decoy)
- Group share of ApexPharm critical spend → **32.5%** (EUR 32.1m of EUR 98.8m) vs **30%** threshold (policy v2.0)
- APX-MSA-2024-0117 cl. 14.3 (60 days CoC termination) ≠ APX-MSA-2024-0171 (no CoC clause)

## 4. Connect to agents

Agent Builder → agent → **AI Indices → Additional indices** → add the AI index. See `agents/SETUP.md`.

## 5. What we actually did (14 Oct) — tested, and where the UI helper failed

- **AI index** `apex-supplier-intelligence` created in the UI with 4 sources (`apex_suppliers`, `apex_corporate_news`, `apex_contracts`, the TPRM ES|QL).
- **Metadata KIs**: workflow `supplier-intelligence-sources` (template *Index/Table Metadata*): 4 `index_metadata` KIs. The *Suggest automation* helper installed
  3 disabled copies and a unit-profile workflow that profiled supplier categories, not ownership groups: delete those, keep one.
- **Facts the templates cannot produce** (ownership group, 32.5% vs the 30% threshold, contract remedies, the decoys) are written as KIs by the workflow
  `apex-targeted-kis` (`kibana_export/workflow.apex-targeted-kis.yaml`, built from the `context-engine.createKi` step, every ES|QL verified before writing):
  `group/veltrano-holding`, `group/veltran-logistik-not-related`, `group/veltrano-contract-remedies`, and the clauses of `0117`, `0171`, `SLA-0042`, `0089`.
  Titles and descriptions carry the words users ask with ("ApexPharm suppliers", "compliance risk", "corporate group"): retrieval depends on them.
- **Attach a saved workflow to the AI index from the API** (the UI refused): MCP/agent tool `save_automation` with `aiIndexId` + `workflowId`; run with `run_automation`.
  `python3 tools/provision.py ... workflows` saves both workflows; attach them to the AI index and run them (expect 4 + 7 KIs).
- Acceptance check: 4 metadata + 2 entity + 5 document KIs; the hybrid query returns `group/veltrano-holding` first for the HERO question and for Q10.
- The AI index is queried by the agent through the tool `apex_context_lookup` (see `agents/SETUP.md`).
