# Story bible (presenter only — contains the answers)

## The guiding question

> *Which of our suppliers could expose ApexPharm to compliance risk, and what do our contracts let us do about it?*

## The hidden group

Veltrano Holding S.A. (Luxembourg) → 100% Orvia Life Sciences B.V. (since 2024-11-12, NEWS-2024-1112-001, EN)

| Supplier | Legal name | 2025 spend EUR m | Group |
|---|---|---|---|
| SUPP-000002 | Rheinchem Pharma Services GmbH | 18.4 | **Veltrano** via Orvia Life Sciences (acquired 2025-03-18, news DE) |
| SUPP-000010 | Kestrel Cold Chain S.r.l. | 9.6 | **Veltrano** directly (acquired 2025-09-22, news IT) |
| SUPP-000011 | Aurelis Excipients S.A. | 14.2 | — |
| SUPP-000012 | Bergmann Glas & Verpackung GmbH | 11.8 | — |
| SUPP-000013 | Nordvik API Manufacturing AS | 21.5 | — |
| SUPP-000014 | Lumen Analytics Lab Kft. | 4.1 | **Veltrano** via Orvia Life Sciences (registry extract 2025-05-06) |
| SUPP-000015 | Sorell Sterile Fill Ltd | 12.9 | — |
| SUPP-000016 | Halden Biologics B.V. | 6.3 | — |

Group share: **EUR 32.1m / 98.8m = 32.5%** → above the **30%** threshold of TPRM **v2.0** (2026-02-01),
below the **40%** per-entity threshold of the stale **v1.0** (2024). A naive RAG that mixes versions concludes "no action needed".

Adverse media: NEWS-2026-0827-001 — Luxembourg regulator reviews Veltrano's ownership disclosures → EDD trigger by itself (policy v2.0 §3.2).

Decoy: Veltran Logistik GmbH (SUPP-000017) — unrelated to Veltrano Holding. Halden Biologics: independent (Series C, NEWS-2026-0602-002).

## Contracts

| Contract | Supplier | What it allows |
|---|---|---|
| APX-MSA-2024-0117 | Rheinchem | §14.1 notify CoC in 30 days · **§14.3 terminate on ≥60 days' notice within 12 months, no fee** |
| APX-MSA-2024-0171 | Halden (decoy) | no CoC clause — near-duplicate number |
| APX-SLA-2023-0042 | Kestrel | **§9.4 disclose >25% shareholder change in 30 days** · breach of 9.4 = material breach (§15.2, 30-day cure) · convenience 180 days |
| APX-MSA-2023-0089 | Lumen | **§12.6 CoC needs Apex prior written consent**, else immediate termination (also SOW APX-SOW-2025-0311) |
| APX-SOW-2025-0313 | Sorell (decoy) | near-duplicate of 0311 |

Operational signal: 14 Kestrel temperature excursions (Oct 2025 – Aug 2026) in `apex_service_tickets` (QA-*).

## Why each act breaks naive RAG

- **Act 1 — wrong context:** contract numbers differ by two transposed digits; vectors treat them as the same thing. Two policy versions, same topic. *Veltran* vs *Veltrano*.
- **Act 2 — too much context:** contracts are ~30k characters; naive RAG pastes three of them (~20k+ tokens) to answer a one-clause question.
- **Context Engine:** ownership needs 4 documents in 3 languages (EN registry, DE press release, IT news, EN group release). Precomputed entities & relationships turn that into one retrieval.

## Act 1 — what the live tests showed (Dev Tools, 13 Oct)

- **Semantic** finds APX-MSA-2024-0117 for Q01 *by meaning* (only 0117 and 0089 have change-of-control language) — scores 0.810 vs 0.806. Right answer, wrong reason.
- **Q02 (0171)** is the real trap: every contract has a convenience-termination clause, so meaning can't pick the contract.
- **BM25 with the standard analyzer** is fooled too: it splits `APX-MSA-2024-0171` into apx/msa/2024/0171, so the shorter **APX-DPA-2024-0171** (Mistral Clearing — same number, different contract type) wins. Kept on purpose as a bonus decoy.
- **Plain RRF hybrid** inherits both mistakes (Veltran 0125 first).
- **Fix = context engineering:** `content.codes` subfield (pattern tokenizer keeps whole codes) + an exact-identifier leg in the hybrid retriever when the question contains a code. Message for the stage: *identifiers are facts, not similarities.*

### Q05 (German query, near-duplicate part codes) — data fix, 14 Oct
The part codes were never described in the indexed data (only in the generator), so the question could not be answered by any retriever.
`tools/build_dataset.py` now adds 4 spare-parts-catalogue entries to `apex_service_tickets` (`CAT-RCX-4410-A/B`, DE + EN): A = Gleitringdichtung / mechanical seal kit for pumps,
B = same for heat exchangers, "not interchangeable". Result: bm25, semantic and hybrid all return `CAT-RCX-4410-A-DE` first and `-B` second.
Q05 is therefore a **control** (all modes right, with the look-alike -B right behind it), not a failure demo.
