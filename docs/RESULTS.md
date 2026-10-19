# Measured results

> **Model:** the demo runs on `gpt-5.4-mini` since 19 Oct (see the last section, "Final numbers"). Everything up to the model experiment was measured on `gpt-4.1-mini` on 14 and 18 Oct and is kept for comparison.

Everything below was measured on the demo itself (Azure OpenAI `gpt-4.1-mini`, Data Zone EU deployment, Serverless 9.6).
Small samples: read them as indications, not benchmarks. Re-run before the talk (`demo/run.sh`, `demo/agents_eval.py`).

## Act 1 — wrong context (retrieval, hit@1)
Code-aware BM25 (`content.codes`) and hybrid with an exact-identifier leg find `APX-MSA-2024-0171`; plain semantic search does not (Q02).
Q05 (German question, near-duplicate part codes) is a **control**: all modes return `CAT-RCX-4410-A-DE` first, `-B` second
(the catalogue entries were missing from the data, see `docs/STORY.md`).

## Act 2 — too much context (CLI `compare`, `eval --act act2`)
| | naive (3 whole contracts) | engineered (highlighted fragments) |
|---|---|---|
| Prompt tokens, Q06 | 13,650 | 7,816 (-43%) |
| Cost per question (EUR 0.40 / 1.50 per 1M in / out) | 0.0058 | 0.0035 (-40%) |
| Cost per 10,000 questions | ~58 EUR | ~35 EUR |
| Accuracy (Q06-Q08, judge) | 3/3 | 3/3 (after `TOP_FRAGS=8`; with 3 fragments it was 1/3) |
| LLM latency, median of 18 runs | 2.3 s | 2.7 s |

**Latency is not a win for a single call**: it is dominated by the number of generated tokens (~13-15 ms each), not by the prompt size.
Do not promise a latency gain for Act 2. The win is tokens and cost.

## Agents — baseline vs Context Engine (`demo/agents_eval.py`, 5 runs per question, keyword rubric)
| Question | baseline correct | context correct | input tokens (base -> ctx) | time (base -> ctx) | LLM calls |
|---|---|---|---|---|---|
| HERO | 0/5 | 4/5 | 102k -> 52k | 22 s -> 11 s | 9.4 -> 3.2 |
| Q09 same group | 2/5 | 5/5 | 93k -> 32k | 19 s -> 8 s | 18.2 -> 2.4 |
| Q10 spend share | 1/5 | 5/5 | 67k -> 23k | 21 s -> 6 s | 11.8 -> 2.0 |

Conditions: agent B has the extra tool `apex_context_lookup` (a hybrid ES|QL lookup on the AI index) and a short protocol in its instructions.
Without that tool, with the AI index merely attached, B often ignored the index (gpt-4.1-mini writes poor ES|QL for `query_ai_indices`).
Say so on stage: the Context Engine is a private preview and this is a workaround, not the product default.
The agent comparison above is also visible in the Agents dashboard (Agent Builder traces).

## Observability facts worth knowing
- Azure does not emit latency metrics (`time_to_response`, `tokens_per_second`...) for this deployment: latency comes from the diagnostic logs (`duration_ms`) and from our traces.
- The managed Foundry dashboards for API Management and Guardrails need API Management gateway logs; with direct diagnostics they stay empty.
- Managed dashboards on the generic `metrics-*` data view show red warnings; copies on dedicated data views (`observability/dashboards`) do not.
- Billed cost (Cost Management) arrives with a delay of hours; the live cost is estimated from tokens and the public price list.

## Cost: billed by Azure vs estimated from tokens (13-14 Oct, Azure OpenAI only)
| | EUR |
|---|---|
| Billed (Cost Management, pretax): input Data Zone 1.165 + cached input 0.643 + output 0.250 | **2.059** |
| Estimated from Azure logs (595 calls, prompt x 0.40 + completion x 1.50 per 1M tokens) | 2.173 (+6%) |
| Monitoring plumbing 14-17 Oct (Container Instances, Event Hubs, Blob Storage) | 6.41 |

- The estimate is close, not identical: the invoice prices cached input tokens separately and counts ~10.2M input tokens (about 7M cached) against 5.1M prompt tokens in the logs (hypothesis: streaming/caching, not verified).
- The invoice arrives the next day; the live number on stage is always the estimate. The monitoring plumbing costs more than the model: say it.
- Shown in the console scoreboard (card "billed vs estimated") and in the dashboard *Azure billing: cost by product*.

## Re-measured on 18 Oct (agents, 5 runs per question; medians, because single runs vary a lot)
| Question | baseline correct | context correct | input tokens (median) | time (median) | LLM calls (median) |
|---|---|---|---|---|---|
| HERO | 0/5 | 3/5 | 96k -> 25k | 11 s -> 6 s | 8 -> 2 |
| Q09 same group | 4/5 | 5/5 | 45k -> 25k | 11 s -> 4 s | 13 -> 2 |
| Q10 spend share | 2/5 | 5/5 | 117k -> 23k | 22 s -> 4 s | 18 -> 2 |

The 14 Oct run had HERO 4/5 for the context agent: with these sample sizes 3/5 and 4/5 are the same thing. One context run on HERO took 12 LLM calls and 385k input tokens (the agent did not use the lookup first): that is why *means* hide the story, use medians.
Say "works in most runs, not always"; keep Practice as the fallback.

## Wrong context lab (the "ask for any contract" item of the console)
Question: *What is the termination for convenience notice period in APX-MSA-xxxx?* The truth is read from clause 15.3 of the contract itself.
- Naive RAG (semantic top-3, whole documents): **1 of 8** contracts answered right (and that one, APX-MSA-2024-0117, is the control: it happens to be one of the three documents the vector always returns).
  It retrieves the same documents (APX-SOW-2025-0313, APX-MSA-2024-0117, ...) whatever contract id is asked, and then answers confidently, sometimes with another contract's number (Q02: "120 days", which is 0117's clause, not 0171's 90).
- Engineered (hybrid + exact-identifier leg + fragments): **8 of 8**.
- `eval/golden_questions.jsonl`: the reference answer of Q02 now states 90 days (it did not mention days, so the judge marked the right answer wrong).

Note (18 Oct): the console's cost card spans 13-22 Oct (`BILLING_FROM`/`BILLING_TO`), but the invoice only exists up to the last day with usage (model: 14 Oct; monitoring: 17 Oct). Usage after that is shown as "not invoiced yet" (an estimate from the logs, ~EUR 3.7 for 18 Oct, mostly agent runs with 20-300k input tokens). Run the evaluations on 21 Oct: on the 22nd the invoice will have lines for that day.
The billing dashboard stores the range 13-23 Oct (a 7-day range would drop the 13-14 Oct model lines by the 22nd).

## Model experiment, 19 Oct: gpt-4.1-mini vs gpt-5.4-mini (same data, same code, deployment `gpt-5-4-mini`, DataZoneStandard, 200k TPM)
The code ran unchanged (`temperature=0` is accepted; no reasoning tokens by default). Prompt tokens are identical (HERO naive 7,591 vs 7,592; Q06 13,649 -> 7,815).
| | gpt-4.1-mini | gpt-5.4-mini |
|---|---|---|
| HERO naive / engineered (judge) | wrong / wrong | wrong / wrong |
| Q02 naive / engineered | wrong / right | wrong / right |
| Q03, Q04, Q06, Q07, Q08 (naive / engineered) | right / right | right / right |
| Wrong context lab, 8 contracts: naive / engineered | 1 / 8 | 1 / 8 |
| Agents HERO: baseline / Context Engine (5 runs) | 0/5 / 3/5 | 0/5 / **5/5** |
| Agents Q09 | 4/5 / 5/5 | 2/5 / 5/5 |
| Agents Q10 | 2/5 / 5/5 | 4/5 / 5/5 |
| Context agent, median LLM calls HERO / Q09 / Q10 | 2 / 2 / 2 | **17 / 9** / 2 |
| Context agent, median input tokens HERO / Q09 / Q10 | 25k / 25k / 23k | **163k / 80k** / 24k |
| Single call latency, Q06 naive | ~2.4 s | ~1.8 s |

Reading: the thesis holds with a newer model (retrieval problems stay, naive RAG still fails Q02 and HERO), the Context Engine agent is more accurate (5/5 on all three), but it no longer follows the "one lookup" path on HERO and Q09: it explores (5 tool calls, 17 LLM calls, 163k tokens), so the "fewer calls and tokens" line only holds for Q10.
In the lab the naive answers of gpt-5.4-mini often abstain ("I can't determine that from the provided context, the closest contracts say 120 / 90 days"): more honest than 4.1-mini, still no answer because the contract is not in the prompt.
Quota: 200k TPM only; two agents in parallel on HERO can exceed it (429). Raw results: `demo/agents_eval_results_gpt54mini_19oct.json` (not in git).

### gpt-5.4-mini with a tighter Context Engine protocol (test agent `apex-analyst-context-v2`, 5 runs per question, 19 Oct)
The only change is the protocol in the agent's instructions: "call `apex_context_lookup` ONCE; if the indicators already answer, answer from them; at most ONE more targeted call". The baseline agent is untouched.
| | baseline (gpt-5.4-mini) | Context Engine v2 (gpt-5.4-mini) |
|---|---|---|
| HERO correct | 0/5 | **5/5** |
| HERO median LLM calls / input tokens / time | 11 / 116k / 20 s | **4 / 44k / 7 s** |
| Q09 correct | 2/5 | 4/5 (one run missed Orvia) |
| Q09 median LLM calls / input tokens / time | 14 / 115k / 15 s | **2 / 25k / 3 s** |
| Q10 correct | 4/5 | 5/5 |
| Q10 median LLM calls / input tokens / time | 14 / 114k / 12 s | **2 / 24k / 3 s** |
So the "fewer calls, fewer tokens" line is back, on a newer model, with higher accuracy than the 4.1-mini run (HERO 5/5 vs 3/5). Not yet applied to the live agent `apex-analyst-context` (the v2 agent is a separate test agent in the Search project).

## Final numbers, 19 Oct: gpt-5.4-mini (`gpt-5-4-mini`, DataZoneStandard), Context Engine protocol v2, shared completeness instruction
Both agents got the same extra sentence in the shared instructions ("when you identify a corporate group, name every company of it that the evidence mentions, including acquired ones"); the Context Engine agent also has the "one lookup" protocol.
Prices (Azure retail list, EUR per 1M tokens, Data Zone, Germany West Central): input 0.726, cached input 0.0726, output 4.356.

**Prompts (CLI / console, judge = gpt-4.1-mini reference answers)**
| | naive | engineered |
|---|---|---|
| Prompt tokens, Q06 | 13,649 | 7,815 (-43%) |
| Cost per question, Q06 / per 10,000 | 0.0110 / ~110 EUR | 0.0070 / ~70 EUR (-36%) |
| Latency Q06 (one call) | ~1.4 s | ~1.7 s (about the same; do not promise a gain) |
| HERO naive | 7,591 tokens, ~0.011 EUR, wrong (no Veltrano) | |
| Q07 / Q08 tokens | 11,327 / 14,687 | 7,781 / 7,646 (-31% / -48%) |
| Accuracy Q06-Q08 | 3/3 | 3/3 |
| Wrong context lab, 8 contracts | 1/8 (4 of 6 recorded answers abstain: "I can't determine that from the context") | 8/8 |

**Agents (5 runs per question, medians)**
| Question | baseline | Context Engine |
|---|---|---|
| HERO | 1/5 · 14 LLM calls · 141k tokens · 20 s | **5/5 · 2 calls · 25k tokens · 4 s** |
| Q09 same group | 5/5 · 14 · 120k · 16 s | **5/5 · 2 · 25k · 3 s** |
| Q10 spend share | 4/5 · 18 · 170k · 19 s | **5/5 · 2 · 24k · 2 s** |

Reading: a newer model makes the baseline agent much better at finding the answer, but it pays 5-7x the tokens and 4-8x the time; the Context Engine agent is 15/15 with about 25k tokens and 2 LLM calls whatever the question. Naive prompts still fail Q02 and HERO: retrieval, not the model.
Raw results: `demo/agents_eval_results_gpt54mini_final_19oct.json` (not in git). The `gpt-4-1-mini` deployment (300k TPM) and `demo/.env.gpt41mini` are the fallback.

## Cost: billed vs estimated, updated 19 Oct (13-18 Oct, both models, agents included)
Billed (Cost Management, pretax) 3.87 EUR (input 2.229 + cached input 1.184 + output 0.453) against an estimate from the logs of 5.91 EUR (+53%), with 1,609 logged calls. Monitoring plumbing 8.19 EUR (14-18 Oct).
The estimate is an **upper bound**: the logs carry no cached-token count, and agent loops re-send the same context, which Azure bills at a fraction. On 13-14 Oct (light usage, few repeated prompts) the estimate was within 6%. The console prices each model separately (`MODEL_PRICES` in `site/app.py`).

