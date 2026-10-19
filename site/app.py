#!/usr/bin/env python3
"""
Demo console for the talk "RAG is Broken" (local web app, presenter use).

  site/run.sh                       # http://127.0.0.1:8765   (reads demo/.env, runs under EDOT so spans reach Observability)

Two modes, switchable in the UI:
  LIVE      every click runs the real thing: Elasticsearch retrieval, Azure OpenAI, Agent Builder, Observability queries.
  PRACTICE  every click shows the last recorded run (site/data/practice.json, written by site/record_practice.py).
            It is labelled "recorded, not a new measurement" everywhere, like the live/practice switch of other demos.

Keys never leave this process: the browser only talks to /api/*. Bind address is 127.0.0.1 on purpose.
"""
import json, os, re, sys, time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "demo"
sys.path.insert(0, str(DEMO))
os.chdir(DEMO)  # dotenv/relative paths of the demo modules

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import agents_eval as ae
import apex_demo as d
import stage

SITE = Path(__file__).resolve().parent
PRACTICE_FILE = SITE / "data" / "practice.json"
CONNECTOR = os.environ.get("AGENT_CONNECTOR", "azure-openai-gpt-5-4-mini")
# EUR per 1M tokens (Azure retail list, Data Zone, Germany West Central): input, output. Used to estimate the cost of the logged calls per model.
MODEL_PRICES = {"gpt-4.1-mini": (0.40, 1.50), "gpt-5.4-mini": (0.726, 4.356)}


def price_eval(m="azure.ai_foundry.properties.model_name", p="azure.ai_foundry.properties.prompt_tokens", c="azure.ai_foundry.properties.completion_tokens"):
    """ES|QL: per-row estimated cost from the model name in the Azure logs (unknown models fall back to the first price)."""
    d0 = MODEL_PRICES["gpt-4.1-mini"]
    pin = "CASE(" + "".join(f'{m} == "{k}", {v[0]}, ' for k, v in MODEL_PRICES.items() if k != "gpt-4.1-mini") + f"{d0[0]})"
    pout = "CASE(" + "".join(f'{m} == "{k}", {v[1]}, ' for k, v in MODEL_PRICES.items() if k != "gpt-4.1-mini") + f"{d0[1]})"
    return f"EVAL row_cost = ({p} * {pin} + {c} * {pout}) / 1000000"
CLAUSE_IDS = ["APX-MSA-2024-0171", "APX-MSA-2025-0230", "APX-MSA-2022-0388", "APX-MSA-2024-0297", "APX-MSA-2023-0089", "APX-MSA-2024-0117"]   # last one: the control where naive is right by luck
BILLING_FROM = os.environ.get("BILLING_FROM", "2026-10-13")   # the cost card spans the whole project life up to the talk
BILLING_TO = os.environ.get("BILLING_TO", "2026-10-22")
SCORE_WINDOW = os.environ.get("SCORE_WINDOW", "2 hours")   # scoreboard looks only at recent runs (rehearsals excluded)


def load_practice():
    return json.loads(PRACTICE_FILE.read_text()) if PRACTICE_FILE.exists() else {}


PRACTICE = load_practice()
app = FastAPI(title="RAG is Broken — demo console")
import admin  # noqa: E402  (preparation commands behind buttons; local only)
def _reload_practice(job_id):
    if job_id.startswith("record_"):
        PRACTICE.clear(); PRACTICE.update(load_practice())
admin.on_done = _reload_practice
app.include_router(admin.router)


# ----------------------------------------------------------------------------- live actions
LABEL_FIELDS = {"apex_contracts": ["supplier_name", "contract_type"], "apex_policy_vault": ["policy_version", "doc_title"], "apex_corporate_news": ["title", "companies_mentioned"],
                "apex_service_tickets": ["part_code", "asset_type", "category"]}


def doc_labels(index, ids, question):
    """A short, factual label per document (from the document itself) so the audience sees WHAT came back, and a flag when it is a near miss."""
    fld = d.ID_FIELD.get(index)
    if not fld or not ids:
        return {}
    hits = d.es(f"/{index}/_search", {"query": {"terms": {fld: list(ids)}}, "size": 50, "_source": LABEL_FIELDS.get(index, []) + [fld]})["hits"]["hits"]
    src = {}
    for h in hits:
        src.setdefault(h["_source"].get(fld) or h["_id"], h["_source"])
    out = {}
    versions = [float(v["policy_version"]) for v in src.values() if v.get("policy_version")]
    for i in ids:
        x = src.get(i)
        if not x:
            continue
        if index == "apex_contracts":
            out[i] = {"text": f"{x.get('supplier_name', '')} · {x.get('contract_type', '')}", "flag": None}
        elif index == "apex_policy_vault":
            older = bool(versions) and float(x.get("policy_version", 0)) < max(versions)
            out[i] = {"text": f"Policy v{x.get('policy_version')}", "note": "older version, superseded" if older else "current version", "flag": "warn" if older else "ok"}
        elif index == "apex_corporate_news":
            cos = x.get("companies_mentioned") or []
            names = lambda c: " ".join(c.lower().replace(",", " ").split()[:2])
            same = any(names(c) in question.lower() for c in cos)
            t = x.get("title") or ""
            out[i] = {"text": t if len(t) <= 48 else t[:46] + "…", "flag": "ok" if same else "warn",
                      "note": ("the company asked about" if same else "another company: " + (cos[0] if cos else "?")) if cos else None}
        elif index == "apex_service_tickets":
            out[i] = {"text": " · ".join(str(v) for v in (x.get("part_code") or x.get("category"), x.get("asset_type")) if v), "flag": None}
    return out


def do_retrieve(q):
    question, index, g = d.resolve(q, None)
    expected = g["sources"] if g else []
    rows = []
    codes = d.CODE_RE.findall(question) if index in d.CODE_FIELDS else []
    for m in ("bm25", "semantic", "hybrid"):
        with d.tracer.start_as_current_span(f"apex.retrieve.{m}") as sp:   # same span as the CLI, so the scoreboard sees the console too
            hits, ms = d.search(m, index, question, size=3)
            ids = [d.doc_id(h, index) for h in hits]
            hit = bool(ids) and ids[0] in expected
            for k, v in {"apex.act": "act1", "apex.mode": m, "apex.question_id": q if g else "adhoc", "apex.index": index, "apex.hit_at_1": hit, "apex.latency_ms": ms}.items():
                sp.set_attribute(k, v)
        req = {"retriever": d.retriever(m, index, question), "size": 3}
        rank = None
        if not hit and expected:
            wide, _ = d.search(m, index, question, size=20)
            wide_ids = [d.doc_id(h, index) for h in wide]
            rank = next((i + 1 for i, x in enumerate(wide_ids) if x in expected), None)
        scores = [round(h.get("_score") or 0, 3) for h in hits]
        rows.append({"mode": m, "ids": ids, "scores": scores, "hit": hit, "ms": round(ms), "rank_of_expected": rank,
                     "request": f"POST /{index}/_search\n" + json.dumps(req, indent=2, ensure_ascii=False),
                     **explain(m, index, codes, hit, ids, scores, expected, rank, bm25_terms(index, question, set(expected)) if m == "bm25" else None)})
    labels = doc_labels(index, sorted({i for r in rows for i in r["ids"]}), question)
    return {"q": q, "question": question, "index": index, "expected": expected, "trap": (g or {}).get("trap", ""), "expected_answer": (g or {}).get("expected_answer", ""), "rows": rows, "labels": labels}


def bm25_terms(index, question, expected):
    """Which single term (field:term) gave the top document most of its BM25 score, and the same for the expected document (from Elasticsearch's own explain)."""
    body = {"retriever": d.retriever("bm25", index, question), "size": 3, "explain": True, "_source": {"includes": [d.ID_FIELD.get(index, "")]}}
    hits = d.es(f"/{index}/_search", body)["hits"]["hits"]
    def top(e):
        out = []
        def walk(x):
            m = re.match(r"weight\((\S+?) in \d+\)", x["description"])
            if m:
                out.append((x["value"], m.group(1)))
            for y in x.get("details", []):
                walk(y)
        walk(e)
        return max(out) if out else None
    res = {"winner": top(hits[0]["_explanation"]) if hits else None, "expected": None}
    for h in hits:
        if d.doc_id(h, index) in expected:
            res["expected"] = top(h["_explanation"]); break
    return res


def explain(mode, index, codes, hit, ids, scores, expected, rank, terms=None):
    """Three short texts per retrieval mode: how this kind of query behaves, why it was right or wrong HERE (from the real result), and where it usually fails."""
    f = d.FIELDS[index]; cid = codes[0] if codes else None
    if mode == "bm25":
        behavior = ("BM25 is lexical: it scores a document by how many of the query's words it contains, weighted by how rare each word is. It never looks at meaning: no synonyms, no paraphrase, no translation."
                    + (f" In '{f}' an identifier is cut at the hyphens ({cid.lower().replace('-', ', ')}), so many contracts share those pieces. The '{f}.codes' subfield keeps the identifier as one token (boost 3), so only the exact one gets that big bonus." if cid else ""))
        weak = "Fails when the answer uses other words than the question (synonyms, other languages) and it cannot rank by meaning."
    elif mode == "semantic":
        behavior = ("Semantic search turns the question and every chunk into a vector (Jina v5) and returns the closest ones. It is strong on paraphrase and other languages."
                    + (f" But '{cid}' and its neighbours are almost the same string to an embedding, and similarity scores are compressed into a narrow band, so a near miss can rank first." if cid else " It returns the nearest meaning even when it is not the right document."))
        weak = "Fails on exact facts: identifiers, part codes, names that differ by a digit or a letter."
    else:
        behavior = ("Hybrid runs BM25 and semantic search separately and merges the two ranked lists with RRF (reciprocal rank fusion): a document that is high in either list floats up. The RRF score is built from ranks, so it is not comparable with the other two columns."
                    + (f" Here a third leg, terms on '{f}.codes' = {[c.lower() for c in codes]}, is added because the question contains an identifier: identifiers are facts, not similarities." if cid else " The question has no identifier, so there is no exact-match leg."))
        weak = "More moving parts: the legs and the rank window must be tuned. Without the exact leg, an identifier can still lose to a similar one."
    top = f"#1 is {ids[0]} (score {scores[0]})" if ids else "no result"
    gap = ""
    if mode != "hybrid" and len(scores) > 1 and scores[0]:
        pct = abs(scores[0] - scores[1]) / scores[0] * 100
        gap = f"; the gap to #2 is {abs(scores[0] - scores[1]):.3f} ({pct:.0f}%)" + (", practically a tie" if pct < 1 else "")
    if hit:
        why = f"Right: the expected document {ids[0]} is first{gap}."
        if mode == "bm25" and cid:
            why += f" It wins because it is the only one that matches the whole identifier."
        if mode == "hybrid" and cid:
            why += " The exact-identifier leg ranks it first and RRF adds that to the other two lists, so it ends on top."
        elif mode == "hybrid":
            why += " It ranks high enough in the lists that RRF merges, so it ends on top."
        if mode == "semantic":
            why += (" But the margin is tiny: it is first by meaning, not because of the identifier, so it could as easily have been the neighbour." if cid and len(scores) > 1 and scores[0] and abs(scores[0] - scores[1]) / scores[0] < 0.05
                    else " Close in meaning, and nothing in the question fooled the vector.")
    else:
        where = f"it is #{rank}" if rank else "it is not even in the top 20"
        why = f"Wrong: {top}{gap}. The expected {', '.join(expected)}: {where}."
        if mode == "semantic" and cid:
            why += " The scores are almost the same, so the order is decided by tiny differences in the vectors, not by the identifier."
    if mode == "bm25" and terms and terms.get("winner"):
        w = terms["winner"]
        why += f" Elasticsearch's explain: #1 scored mostly on '{w[1]}' ({w[0]:.2f})"
        if not hit and terms.get("expected"):
            why += f", while the expected document's best term was '{terms['expected'][1]}' ({terms['expected'][0]:.2f}): BM25 weighs a rare word as much as an identifier."
        else:
            why += "."
    return {"behavior": behavior, "why": why, "weak": weak}


def retrieval_request(mode, index, question):
    """The search request that picks the documents for the prompt (shown to the audience, copyable)."""
    f = d.FIELDS[index]
    if mode == "naive":
        body = {"retriever": d.retriever("semantic", index, question), "size": 3}
        return (f"# 1) the closest three documents by meaning only\nPOST /{index}/_search\n" + json.dumps(body, indent=2, ensure_ascii=False)
                + f"\n\n# 2) then the WHOLE documents are fetched by _id and pasted into the prompt\nPOST /{index}/_search\n" + json.dumps({"query": {"ids": {"values": ["<the 3 ids>"]}}, "size": 3}, indent=2))
    body = {"retriever": d.retriever("rerank" if d.RERANK_ID else "hybrid", index, question), "size": 5,
            "highlight": {"fields": {f"{f}_semantic": {"type": "semantic", "number_of_fragments": d.TOP_FRAGS, "order": "score"}}}}
    return (f"# hybrid retrieval, then only the best-matching fragments of each document are kept\nPOST /{index}/_search\n" + json.dumps(body, indent=2, ensure_ascii=False))


def context_parts(mode, prompt_text, docs):
    """Chars (and share of the prompt) per document in the context."""
    ctx = prompt_text.split("Context:\n", 1)[1].rsplit("\n\nQuestion:", 1)[0]
    parts = []
    if mode == "naive":
        chunks = ctx.split("\n\n---\n\n")
        for i, c in enumerate(chunks):
            parts.append({"id": docs[i] if i < len(docs) else f"document {i + 1}", "chars": len(c), "fragments": None})
    else:
        for blk in ctx.split("\n\n[")[0:]:
            blk = blk if blk.startswith("[") else "[" + blk
            m = re.match(r"\[([^\]]+)\]\n", blk)
            if m:
                parts.append({"id": m.group(1), "chars": len(blk), "fragments": blk.count("\n…\n") + 1})
    tot = sum(p["chars"] for p in parts) or 1
    for p in parts:
        p["share"] = round(p["chars"] / tot * 100)
    return parts


BEHAVIOR = {
    "naive": "Naive RAG: the closest three documents by meaning (semantic search only), then the WHOLE documents are pasted into the prompt. It is only as good as the vector, and every extra character is paid for in tokens.",
    "engineered": "Engineered context: hybrid retrieval (BM25 + vector + exact-identifier leg), then only the best-matching fragments of the top documents go into the prompt (8 per top-2 document, 3 for the others). Smaller and, here, more precise.",
}


def decorate(r, mode, index, question, g=None, must=None, truth=None):
    """Add what a developer wants to see: the request, the prompt, the parts, and WHY it is right or wrong (from the real result)."""
    pt = r["prompt_text"]
    parts = context_parts(mode, pt, r["docs"])
    r["parts"] = parts
    r["request"] = retrieval_request(mode, index, question)
    r["behavior"] = BEHAVIOR[mode]
    expected = (g or {}).get("sources", [])
    why = [f"{r['prompt']:,} prompt tokens: {len(parts)} document{'s' if len(parts) != 1 else ''}, {r['context_chars']:,} characters of context."]
    if expected:
        got = [e for e in expected if e in r["docs"]]
        why.append(f"Expected sources in the context: {len(got)} of {len(expected)}" + ("." if len(got) == len(expected) else f" (missing: {', '.join(e for e in expected if e not in got)})."))
    if must:
        in_ctx = [t for t in must if re.search(re.escape(t), pt, re.I)]
        in_ans = [t for t in must if re.search(re.escape(t), r["answer"], re.I)]
        r["must_in_context"] = {t: t in in_ctx for t in must}
        why.append(f"Key facts found in the context: {len(in_ctx)} of {len(must)}" + (f" (missing: {', '.join(t for t in must if t not in in_ctx)})." if len(in_ctx) < len(must) else ".")
                   + (" The model cannot use what is not in the prompt: this is a retrieval problem, not a model problem." if len(in_ctx) < len(must) else "")
                   + f" Key facts in the answer: {len(in_ans)} of {len(must)}.")
    if truth is not None:
        nums = list(dict.fromkeys(re.findall(r"(\d+)[ -]days", r["answer"])))
        abstain = bool(re.search(r"can.t determine|cannot determine|not included|not in the (provided )?context|does not contain|doesn.t contain|not (available|provided|present)", r["answer"], re.I))
        r["abstained"] = abstain
        r["days"] = nums; r["truth"] = truth
        got_doc = truth_doc(question) in r["docs"] if truth_doc(question) else None
        r["correct"] = bool(nums) and set(nums) == {truth} and not (abstain and got_doc is False)
        said = (', '.join(nums) + ' days') if nums else 'no number'
        if abstain and not r["correct"]:
            why.append(f"Truth from the document (clause 15.3): {truth} days. The model declined to answer for this contract, because it is not in the prompt"
                       + (f" (it quotes the closest contracts instead: {said})." if nums else ".") + " Honest, but still no answer: the right contract never reached the model.")
        else:
            why.append(f"Truth from the document (clause 15.3): {truth} days. The answer says: {said if nums else 'no number (it could not find the clause)'}." + (" Right." if r["correct"] else " Wrong.")
                       + (f" The contract asked for is {'in' if got_doc else 'NOT in'} the retrieved set ({', '.join(r['docs'][:3])})." if got_doc is not None else ""))
    elif r.get("judge_reason"):
        why.append("Judge: " + ("correct" if r["correct"] else "wrong") + ". " + (r["judge_reason"] if len(r["judge_reason"]) < 330 else r["judge_reason"][:327] + "..."))
    r["why"] = why
    return r


def truth_doc(question):
    m = d.CODE_RE.search(question)
    return m.group(0) if m else None


def clause_truth(cid):
    h = d.es("/apex_contracts/_search", {"query": {"term": {"contract_id": cid}}, "size": 1, "_source": ["content"]})["hits"]["hits"]
    if not h:
        return None
    m = re.search(r"terminate this Agreement for convenience on (\d+) days", h[0]["_source"]["content"])
    return m.group(1) if m else None


def do_answer(q, mode):
    question, index, g = d.resolve(q, None)
    r = d.answer(q, None, mode, judge=True)
    must = ae.QUESTIONS["HERO"][1] if q == "HERO" else None
    r.update({"q": q, "question": question, "index": index, "expected_answer": (g or {}).get("expected_answer", ""), "expected": (g or {}).get("sources", [])})
    return decorate(r, mode, index, question, g, must)


def do_clause(cid):
    cid = (cid or "").strip().upper()
    if not d.CODE_RE.fullmatch(cid):
        raise ValueError("enter a contract id like APX-MSA-2024-0171")
    truth = clause_truth(cid)
    if not truth:
        raise ValueError(f"no convenience clause found for {cid}")
    question = f"What is the termination for convenience notice period in {cid}?"
    out = {}
    for mode in ("naive", "engineered"):
        r = d.answer(question, "apex_contracts", mode, judge=False)
        r.update({"q": cid, "question": question, "index": "apex_contracts", "expected": [cid]})
        out[mode] = decorate(r, mode, "apex_contracts", question, {"sources": [cid]}, None, truth)
    n, e = out["naive"], out["engineered"]
    return {"cid": cid, "question": question, "truth": truth, "naive": n, "engineered": e,
            "delta": {"prompt": round((e["prompt"] / n["prompt"] - 1) * 100) if n["prompt"] else 0, "cost": round((e["cost"] / n["cost"] - 1) * 100) if n["cost"] else 0, "latency": round((e["llm_ms"] / n["llm_ms"] - 1) * 100) if n["llm_ms"] else 0}}


def do_compare(q):
    naive, eng = do_answer(q, "naive"), do_answer(q, "engineered")
    def delta(a, b):
        return round((b / a - 1) * 100) if a else 0
    return {"q": q, "question": naive["question"], "expected_answer": naive["expected_answer"], "naive": naive, "engineered": eng,
            "delta": {"prompt": delta(naive["prompt"], eng["prompt"]), "cost": delta(naive["cost"], eng["cost"]), "latency": delta(naive["llm_ms"], eng["llm_ms"])}}


def agent_why(agent_id, r, missing):
    tools = [t["tool"] for t in r["trace"] if t["type"] == "tool"]
    kinds = len(set(tools))
    if agent_id.endswith("context"):
        first = tools[0] if tools else None
        w = (f"Its first tool call was {first}: one hybrid ES|QL query on the AI index returns the precomputed knowledge indicators (ownership groups, spend share). "
             f"{r['llm_calls']} LLM calls in total.") if first == "apex_context_lookup" else f"It did not start with the AI index (first tool: {first}), so it behaved like the baseline."
    else:
        w = (f"It has no AI index: it searched {kinds} different indices one by one ({len(tools)} tool calls, {r['llm_calls']} LLM calls), each query using the words of the question, "
             "and had to work out the links between suppliers itself from the text.")
    return w + (f" Missing from the answer: {', '.join(missing)}." if missing else " All key facts are in the answer.")


def do_agent(agent_id, q):
    question, must = ae.QUESTIONS[q]
    r = ae.ask(agent_id, question, CONNECTOR)
    chips = [{"term": m, "found": bool(re.search(re.escape(m), r["answer"], re.I))} for m in must]
    tools = {}
    for t in r["tools"]:
        tools[t] = tools.get(t, 0) + 1
    missing = [c["term"] for c in chips if not c["found"]]
    return {"agent": agent_id, "q": q, "question": question, "answer": r["answer"], "llm_calls": r["llm_calls"], "input_tokens": r["in"], "output_tokens": r["out"],
            "seconds": round(r["s"], 1), "tool_calls": len(r["tools"]), "tools": r["tools"], "tool_summary": tools, "chips": chips, "correct": not missing,
            "trace": r["trace"], "why": agent_why(agent_id, r, missing)}


def esql(base, key, query):
    r = requests.post(base + "/_query", headers={"Authorization": f"ApiKey {key}", "Content-Type": "application/json"}, json={"query": query}, timeout=60)
    j = r.json()
    if not r.ok:
        raise RuntimeError(j.get("error", {}).get("reason", r.text)[:200])
    cols = [c["name"] for c in j["columns"]]
    return [dict(zip(cols, row)) for row in j["values"]]


def do_scoreboard():
    obs_kb = stage.OBS.get("OBS_KIBANA_URL", "").rstrip("/")
    obs_es, obs_key = obs_kb.replace(".kb.", ".es."), stage.OBS.get("OBS_API_KEY", "")
    W = SCORE_WINDOW
    out = {"errors": [], "window": W}
    P = "azure.ai_foundry.properties."
    qs = {
        "act2": (f'FROM traces-* | WHERE service.name == "apex-rag-demo" AND attributes.apex.act == "act2" AND attributes.apex.prompt_tokens IS NOT NULL AND @timestamp > NOW() - {W} '
                 '| STATS prompt_tokens = ROUND(AVG(attributes.apex.prompt_tokens)), llm_ms = ROUND(AVG(attributes.apex.llm_latency_ms)), cost_eur = ROUND(AVG(attributes.apex.cost_eur), 5), '
                 'judged = COUNT(attributes.apex.eval.correct), correct_n = COUNT(CASE(attributes.apex.eval.correct == true, 1)), runs = COUNT(*) BY mode = attributes.apex.mode '
                 '| EVAL accuracy_pct = CASE(judged > 0, ROUND(100.0 * correct_n / judged), NULL)'),
        "act1": (f'FROM traces-* | WHERE service.name == "apex-rag-demo" AND attributes.apex.act == "act1" AND attributes.apex.question_id != "Q05" AND @timestamp > NOW() - {W} '
                 '| STATS hit_at_1_pct = ROUND(100 * AVG(CASE(attributes.apex.hit_at_1 == true, 1.0, 0.0))), runs = COUNT(*) BY mode = attributes.apex.mode'),
        "azure": (f'FROM logs-azure_ai_foundry.logs-* | WHERE azure.ai_foundry.category == "RequestResponse" AND @timestamp > NOW() - {W} '
                  f'| {price_eval()} | STATS calls = COUNT(*), avg_ms = ROUND(AVG(azure.ai_foundry.duration_ms)), p95_ms = ROUND(PERCENTILE(azure.ai_foundry.duration_ms, 95)), prompt_tokens = SUM({P}prompt_tokens), completion_tokens = SUM({P}completion_tokens), cost_eur = ROUND(SUM(row_cost), 3)'),
    }
    for k, q in qs.items():
        try:
            out[k] = esql(obs_es, obs_key, q)
        except Exception as e:
            out[k] = []; out["errors"].append(f"{k}: {e}")
    try:
        r = requests.get(obs_kb + "/api/alerting/rules/_find", params={"per_page": 100, "search": "Prompt too large"}, headers=stage.kb_headers("obs"), timeout=20).json()
        rule = next((x for x in r.get("data", []) if x["name"].startswith("[LLM] Prompt too large")), None)
        out["alert"] = {"name": rule["name"], "enabled": rule["enabled"], "outcome": (rule.get("last_run") or {}).get("outcome"), "active": ((rule.get("last_run") or {}).get("alerts_count") or {}).get("active", 0)} if rule else None
    except Exception as e:
        out["alert"] = None; out["errors"].append(f"alert: {e}")
    try:
        out["billing"] = do_billing()
    except Exception as e:
        out["billing"] = {"available": False}; out["errors"].append(f"billing: {e}")
    try:
        base = (f'FROM traces-agent_builder.otel-* | WHERE @timestamp > NOW() - {W} AND (name LIKE "invoke_agent Apex*" OR name LIKE "chat *" OR name LIKE "execute_tool *") '
                '| EVAL agent = CASE(name LIKE "invoke_agent*", attributes.gen_ai.agent.name, NULL), in_tok = attributes.gen_ai.usage.input_tokens, run_ns = CASE(name LIKE "invoke_agent*", duration, NULL), is_tool = CASE(name LIKE "execute_tool*", 1, 0) '
                '| STATS agent = MAX(agent), llm_calls = COUNT(in_tok), input_tokens = SUM(in_tok), tool_calls = SUM(is_tool), run_s = MAX(run_ns) / 1000000000.0 BY trace_id | WHERE agent IS NOT NULL '
                '| STATS runs = COUNT(*), avg_run_s = ROUND(AVG(run_s), 1), avg_llm_calls = ROUND(AVG(llm_calls), 1), avg_tool_calls = ROUND(AVG(tool_calls), 1), avg_input_tokens = ROUND(AVG(input_tokens)) BY agent')
        out["agents"] = esql(d.ES_URL, os.environ["ES_API_KEY"], base)
    except Exception as e:
        out["agents"] = []; out["errors"].append(f"agents: {e}")
    return out



def do_billing():
    """Billed cost (Azure Cost Management, pretax, per day) vs the estimate computed from the diagnostic logs for the same days."""
    obs_kb = stage.OBS.get("OBS_KIBANA_URL", "").rstrip("/"); es_url, key = obs_kb.replace(".kb.", ".es."), stage.OBS.get("OBS_API_KEY", "")
    oa = esql(es_url, key, 'FROM metrics-azure.billing* | WHERE azure.billing.product LIKE "Azure OpenAI*" | STATS cost = SUM(azure.billing.pretax_cost), qty = SUM(azure.billing.quantity), d0 = MIN(azure.billing.usage_date), d1 = MAX(azure.billing.usage_date) BY product = azure.billing.product | SORT cost DESC')
    other = esql(es_url, key, 'FROM metrics-azure.billing* | WHERE NOT azure.billing.product LIKE "Azure OpenAI*" | STATS cost = SUM(azure.billing.pretax_cost), d0 = MIN(azure.billing.usage_date), d1 = MAX(azure.billing.usage_date) BY product = azure.billing.product | SORT cost DESC')
    if not oa:
        return {"available": False}
    d0, d1 = min(x["d0"] for x in oa), max(x["d1"] for x in oa)
    d_end = (datetime.fromisoformat(d1.replace("Z", "+00:00")) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")   # ES|QL has no DATE_ADD
    P = "azure.ai_foundry.properties."
    est = esql(es_url, key, f'FROM logs-azure_ai_foundry.logs-* | WHERE azure.ai_foundry.category == "RequestResponse" AND @timestamp >= "{d0}" AND @timestamp < "{d_end}" '
                            f'| {price_eval()} | STATS calls = COUNT(*), p = SUM({P}prompt_tokens), c = SUM({P}completion_tokens), cost = SUM(row_cost)')[0]
    est_cost = est["cost"] or 0
    # usage after the last invoiced day: not billed yet, so it is an estimate only (the invoice follows the next day)
    nb = esql(es_url, key, f'FROM logs-azure_ai_foundry.logs-* | WHERE azure.ai_foundry.category == "RequestResponse" AND @timestamp >= "{d_end}" '
                           f'| {price_eval()} | STATS calls = COUNT(*), p = SUM({P}prompt_tokens), c = SUM({P}completion_tokens), cost = SUM(row_cost)')[0]
    nb_cost = nb["cost"] or 0
    total = sum(x["cost"] or 0 for x in oa)
    short = lambda s: re.sub(r"^Azure OpenAI - gpt [\d.]+ mini ", "", s).replace(" - DE West Central", "")
    return {"available": True, "currency": "EUR", "period": [min(d0[:10], BILLING_FROM), max(d1[:10], BILLING_TO)], "billed_through": d1[:10], "not_invoiced": {"from": d_end[:10], "calls": nb["calls"], "cost": round(nb_cost, 3)}, "openai_total": round(total, 3), "openai": [{"product": short(x["product"]), "cost": round(x["cost"] or 0, 3)} for x in oa],
            "estimated": {"calls": est["calls"], "prompt_tokens": est["p"], "completion_tokens": est["c"], "cost": round(est_cost, 3)}, "delta_pct": round((est_cost / total - 1) * 100) if total else None,
            "other_total": round(sum(x["cost"] or 0 for x in other), 2), "other_period": [min(x["d0"] for x in other)[:10], max(x["d1"] for x in other)[:10]] if other else None, "other": [{"product": x["product"].replace(" - DE West Central", ""), "cost": round(x["cost"] or 0, 2)} for x in other[:4]]}

# ----------------------------------------------------------------------------- API
class Req(BaseModel):
    q: str = ""
    mode: str = "live"        # live | practice
    llm: str = "naive"        # for /api/answer
    agent: str = ""           # for /api/agent


def serve(key, fn, mode):
    if mode == "practice":
        rec = PRACTICE.get(key)
        if not rec:
            raise HTTPException(404, f"no recording for {key}: run site/record_practice.py")
        return {**rec["data"], "_meta": {"mode": "practice", "recorded_at": rec["recorded_at"]}}
    try:
        t0 = time.time(); data = fn()
    except Exception as e:
        raise HTTPException(502, f"{type(e).__name__}: {str(e)[:300]}")
    return {**data, "_meta": {"mode": "live", "recorded_at": time.strftime("%Y-%m-%d %H:%M:%S"), "seconds": round(time.time() - t0, 1)}}


@app.get("/api/config")
def config():
    qs = lambda ids: [{"id": i, "question": d.GOLDEN[i]["question"], "trap": d.GOLDEN[i].get("trap", ""), "expected_answer": d.GOLDEN[i]["expected_answer"]} for i in ids]
    return {"system_prompt": d.SYSTEM, "clause_ids": CLAUSE_IDS, "admin": admin.ENABLED, "practice_available": sorted(PRACTICE), "deployment": d.DEPLOYMENT, "price_in": d.PRICE_IN, "price_out": d.PRICE_OUT, "connector": CONNECTOR,
            "act1": qs(["Q02", "Q03", "Q04", "Q01", "Q05"]), "act2_compare": qs(["Q06", "Q07", "Q08"]), "hero": qs(["HERO"])[0],
            "agent_questions": {k: {"question": v[0], "must": v[1]} for k, v in ae.QUESTIONS.items()}, "agents": ae.AGENTS}


@app.post("/api/retrieve")
def retrieve(r: Req):
    return serve(f"retrieve:{r.q}", lambda: do_retrieve(r.q), r.mode)


@app.post("/api/compare")
def compare(r: Req):
    return serve(f"compare:{r.q}", lambda: do_compare(r.q), r.mode)


@app.post("/api/answer")
def answer(r: Req):
    return serve(f"answer:{r.q}:{r.llm}", lambda: do_answer(r.q, r.llm), r.mode)


@app.post("/api/agent")
def agent(r: Req):
    return serve(f"agent:{r.agent}:{r.q}", lambda: do_agent(r.agent, r.q), r.mode)


@app.post("/api/clause")
def clause(r: Req):
    if r.mode == "practice":
        return serve(f"clause:{r.q}", None, "practice")
    return serve(f"clause:{r.q}", lambda: do_clause(r.q), "live")


@app.post("/api/scoreboard")
def scoreboard(r: Req):
    return serve("scoreboard", do_scoreboard, r.mode)


_health = {"t": 0, "rows": []}


@app.get("/api/health")
def health(fresh: bool = False):
    if fresh or time.time() - _health["t"] > 60:
        _health["rows"] = [{"name": n, "status": s, "detail": dt} for n, s, dt in stage.preflight_rows()]; _health["t"] = time.time()
    worst = "FAIL" if any(r["status"] == "FAIL" for r in _health["rows"]) else ("WARN" if any(r["status"] == "WARN" for r in _health["rows"]) else "OK")
    return {"overall": worst, "checked_at": time.strftime("%H:%M:%S", time.localtime(_health["t"])), "rows": _health["rows"]}


def do_alert_status():
    """Is the 'prompt too large' alert active, and when did it fire before? (an alert is active ~5 min: the rule looks at the last 5 minutes)"""
    kb_o = stage.kb("obs"); h = stage.kb_headers("obs")
    r = requests.get(kb_o + "/api/alerting/rules/_find", params={"per_page": 100, "search": "Prompt too large"}, headers=h, timeout=20).json()
    rule = next((x for x in r.get("data", []) if x["name"].startswith("[LLM] Prompt too large")), None)
    if not rule:
        return {"found": False}
    a = requests.post(kb_o + "/internal/rac/alerts/find", headers={**h, "Content-Type": "application/json"}, timeout=20,
                      json={"query": {"bool": {"filter": [{"term": {"kibana.alert.rule.uuid": rule["id"]}}]}}, "size": 6, "sort": [{"kibana.alert.start": "desc"}], "rule_type_ids": [".es-query"],
                            "_source": ["kibana.alert.start", "kibana.alert.end", "kibana.alert.status"]}).json()
    rows = [{"status": x["_source"].get("kibana.alert.status"), "start": x["_source"].get("kibana.alert.start"), "end": x["_source"].get("kibana.alert.end")} for x in a.get("hits", {}).get("hits", [])]
    return {"found": True, "rule_id": rule["id"], "enabled": rule["enabled"], "outcome": (rule.get("last_run") or {}).get("outcome"), "active": any(x["status"] == "active" for x in rows), "alerts": rows,
            "alerts_url": kb_o + "/app/observability/alerts?_a=(kuery:'',rangeFrom:now-24h,rangeTo:now,status:all)", "rule_url": f"{kb_o}/app/observability/alerts/rules/{rule['id']}"}


@app.get("/api/alert-status")
def alert_status():
    try:
        return do_alert_status()
    except Exception as e:
        raise HTTPException(502, f"{type(e).__name__}: {str(e)[:200]}")


@app.get("/api/links")
def links():
    out = {}
    for key, (project, title) in stage.DASH.items():
        url, err = stage.resolve_dashboard(key)
        out[key] = {"title": title, "project": project, "url": url, "error": err}
    kb_s, kb_o = stage.kb("search"), stage.kb("obs")
    out["alerts"] = {"title": "Alerts (Observability, all statuses, last 24 h)", "project": "obs", "url": kb_o + "/app/observability/alerts?_a=(kuery:'',rangeFrom:now-24h,rangeTo:now,status:all)" if kb_o else None, "error": None}
    out["agent_builder"] = {"title": "Agent Builder (Search)", "project": "search", "url": kb_s + "/app/agent_builder" if kb_s else None, "error": None}
    return out


class NoCacheStatic(StaticFiles):
    """The console is edited often and used live: never let the browser keep an old style.css or app.js."""
    async def get_response(self, path, scope):
        r = await super().get_response(path, scope)
        r.headers["Cache-Control"] = "no-store"
        return r


app.mount("/static", NoCacheStatic(directory=SITE / "static"), name="static")


@app.get("/")
def index():
    return FileResponse(SITE / "static" / "index.html", headers={"Cache-Control": "no-store"})
