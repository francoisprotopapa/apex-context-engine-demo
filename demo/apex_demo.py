#!/usr/bin/env python3
"""
Apex demo CLI — "RAG is broken" live demo, instrumented with OpenTelemetry.

  python apex_demo.py retrieve Q01            # Act 1: BM25 vs semantic vs hybrid (vs rerank)
  python apex_demo.py answer Q06 --mode naive # Act 2: whole documents in the prompt
  python apex_demo.py answer Q06 --mode engineered
  python apex_demo.py compare Q06             # naive vs engineered side by side (+ judge)
  python apex_demo.py eval --act act2         # batch over golden questions -> accuracy
  python apex_demo.py ask "free text question" --index apex_contracts

Run it under EDOT (Elastic Distribution of OpenTelemetry) so every Azure OpenAI call
becomes a span with token usage, and every step carries apex.* attributes:
  opentelemetry-instrument python apex_demo.py compare Q06
See README.md in this folder.
"""
import os, sys
from pathlib import Path as _P
_VENV = _P(__file__).resolve().parent / ".venv" / "bin" / "python"
if _VENV.exists() and not sys.prefix.startswith(str(_VENV.parent.parent)):  # started with the system python: re-run with the project venv
    os.execv(str(_VENV), [str(_VENV), *sys.argv])
import argparse, json, os, re, sys, time
from pathlib import Path

import requests
from dotenv import load_dotenv
from openai import AzureOpenAI
from rich.console import Console
from rich.table import Table

try:
    from opentelemetry import trace
    tracer = trace.get_tracer("apex-demo")
except ImportError:  # works without OTel, just no traces
    import contextlib
    class _S:
        def set_attribute(self, *a): pass
    class _T:
        @contextlib.contextmanager
        def start_as_current_span(self, *a, **k): yield _S()
    tracer = _T()

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")
con = Console()

ES_URL = os.environ["ES_URL"].rstrip("/")
ES_H = {"Authorization": f"ApiKey {os.environ['ES_API_KEY']}", "Content-Type": "application/json"}
RERANK_ID = os.getenv("RERANK_INFERENCE_ID") or None
DEPLOYMENT = os.environ["AZURE_OPENAI_DEPLOYMENT"]
PRICE_IN = float(os.getenv("PRICE_IN_PER_1M") or 0)    # fill from your Azure price sheet; 0 = don't show cost
PRICE_OUT = float(os.getenv("PRICE_OUT_PER_1M") or 0)
aoai = AzureOpenAI(api_key=os.environ["AZURE_OPENAI_API_KEY"], azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
                   api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"))

# which field to search per index (BM25 field; semantic field is <field>_semantic)
FIELDS = {"apex_contracts": "content", "apex_policy_vault": "text", "apex_corporate_news": "text",
          "apex_service_tickets": "text", "apex_suppliers": "description", "apex_unstructured_vault": "text",
          "apex_it_knowledge_base": "text", "apex_customer_interactions": "text"}
ID_FIELD = {"apex_contracts": "contract_id", "apex_policy_vault": "doc_id", "apex_corporate_news": "news_id",
            "apex_service_tickets": "ticket_id", "apex_suppliers": "supplier_id"}
DEFAULT_INDEX = {"Q01": "apex_contracts", "Q02": "apex_contracts", "Q03": "apex_policy_vault", "Q04": "apex_corporate_news",
                 "Q05": "apex_service_tickets", "Q06": "apex_contracts", "Q07": "apex_contracts", "Q08": "apex_contracts",
                 "Q11": "apex_service_tickets"}

GOLDEN = {q["id"]: q for q in (json.loads(l) for l in open(HERE.parent / "eval/golden_questions.jsonl", encoding="utf-8"))}


def resolve(q, index):
    if q in GOLDEN:
        g = GOLDEN[q]
        return g["question"], index or DEFAULT_INDEX.get(q, "apex_contracts"), g
    return q, index or "apex_contracts", None


def es(path, body):
    r = requests.post(f"{ES_URL}{path}", headers=ES_H, json=body, timeout=60)
    r.raise_for_status()
    return r.json()


CODE_FIELDS = {"apex_contracts", "apex_service_tickets"}            # have a <field>.codes subfield
CODE_RE = re.compile(r"\b[A-Z]{2,4}(?:-[A-Z0-9]{1,5}){1,3}\b")      # APX-MSA-2024-0171, RCX-4410-A, ...


def retriever(mode, index, q):
    f = FIELDS[index]
    fields = [f, f"{f}.codes^3"] if index in CODE_FIELDS else [f]
    bm25 = {"standard": {"query": {"multi_match": {"query": q, "fields": fields}}}}
    sem = {"standard": {"query": {"semantic": {"field": f"{f}_semantic", "query": q}}}}
    if mode == "bm25":
        return bm25
    if mode == "semantic":
        return sem
    legs = [bm25, sem]
    codes = [c.lower() for c in CODE_RE.findall(q)]
    if codes and index in CODE_FIELDS:
        # context engineering: identifiers are facts, not similarities -> dedicated exact-match leg
        legs.append({"standard": {"query": {"terms": {f"{f}.codes": codes}}}})
    hybrid = {"rrf": {"retrievers": legs, "rank_window_size": 50}}
    if mode == "rerank" and RERANK_ID:
        return {"text_similarity_reranker": {"retriever": hybrid, "field": f, "inference_id": RERANK_ID,
                                             "inference_text": q, "rank_window_size": 20}}
    return hybrid


def search(mode, index, q, size=5, highlight=False, fragments=3):
    body = {"retriever": retriever(mode, index, q), "size": size,
            "_source": {"excludes": ["*_semantic", "content", "text"] if not highlight else ["*_semantic"]}}
    if highlight:
        body["highlight"] = {"fields": {f"{FIELDS[index]}_semantic": {"type": "semantic", "number_of_fragments": fragments, "order": "score"}}}
    t0 = time.time()
    res = es(f"/{index}/_search", body)
    return res["hits"]["hits"], (time.time() - t0) * 1000


def doc_id(h, index):
    return h["_source"].get(ID_FIELD.get(index, ""), h["_id"])


# ------------------------------------------------------------------ Act 1
def cmd_retrieve(q, index):
    question, index, g = resolve(q, index)
    expected = set(g["sources"]) if g else set()
    con.rule(f"[bold]Act 1 · retrieval[/] — {question}")
    t = Table("mode", "#1", "#2", "#3", "hit@1", "ms")
    modes = ["bm25", "semantic", "hybrid"] + (["rerank"] if RERANK_ID else [])
    for m in modes:
        with tracer.start_as_current_span(f"apex.retrieve.{m}") as sp:
            hits, ms = search(m, index, question, size=3)
            ids = [doc_id(h, index) for h in hits]
            hit = bool(ids) and (ids[0] in expected or not expected)
            for k, v in {"apex.act": "act1", "apex.mode": m, "apex.question_id": q if g else "adhoc",
                         "apex.index": index, "apex.hit_at_1": hit, "apex.latency_ms": ms}.items():
                sp.set_attribute(k, v)
        t.add_row(m, *(ids + ["", "", ""])[:3], "[green]yes[/]" if hit else "[red]no[/]", f"{ms:.0f}")
    con.print(t)
    if g and g.get("trap"):
        con.print(f"[dim]trap: {g['trap']}[/]")


# ------------------------------------------------------------------ Act 2
SYSTEM = "You are a procurement and compliance analyst at Apex Conglomerate. Answer only from the provided context. Cite contract or document IDs."


TOP_FRAGS, TAIL_FRAGS = 8, 3


def build_context(mode, index, question):
    if mode == "naive":
        hits, ms = search("semantic", index, question, size=3, highlight=False)
        # naive RAG: fetch whole documents and paste them in
        ids = [h["_id"] for h in hits]
        docs = es(f"/{index}/_search", {"query": {"ids": {"values": ids}}, "size": 3,
                                        "_source": {"excludes": ["*_semantic"]}})["hits"]["hits"]
        ctx = "\n\n---\n\n".join(d["_source"].get(FIELDS[index], "") for d in docs)
        return ctx, [doc_id(d, index) for d in docs], ms
    # more fragments for the top documents, fewer for the tail: depth where it matters, still far below whole documents
    hits, ms = search("rerank" if RERANK_ID else "hybrid", index, question, size=5, highlight=True, fragments=TOP_FRAGS)
    parts = []
    for rank, h in enumerate(hits):
        frags = h.get("highlight", {}).get(f"{FIELDS[index]}_semantic", [])[:TOP_FRAGS if rank < 2 else TAIL_FRAGS]
        if frags:
            parts.append(f"[{doc_id(h, index)}]\n" + "\n…\n".join(frags))
    return "\n\n".join(parts), [doc_id(h, index) for h in hits], ms


def answer(q, index, mode, judge=False):
    question, index, g = resolve(q, index)
    with tracer.start_as_current_span(f"apex.answer.{mode}") as sp:
        ctx, ids, rms = build_context(mode, index, question)
        t0 = time.time()
        r = aoai.chat.completions.create(model=DEPLOYMENT, temperature=0,
                                         messages=[{"role": "system", "content": SYSTEM},
                                                   {"role": "user", "content": f"Context:\n{ctx}\n\nQuestion: {question}"}])
        lat = (time.time() - t0) * 1000
        u = r.usage
        cost = (u.prompt_tokens * PRICE_IN + u.completion_tokens * PRICE_OUT) / 1e6
        text = r.choices[0].message.content
        correct, reason = judge_answer_full(question, text, g["expected_answer"]) if (judge and g) else (None, "")
        for k, v in {"apex.act": "act2", "apex.mode": mode, "apex.question_id": q if g else "adhoc", "apex.index": index,
                     "apex.prompt_tokens": u.prompt_tokens, "apex.completion_tokens": u.completion_tokens,
                     "apex.llm_latency_ms": lat, "apex.retrieval_latency_ms": rms, "apex.context_chars": len(ctx),
                     "apex.cost_eur": cost}.items():
            sp.set_attribute(k, v)
        if correct is not None:
            sp.set_attribute("apex.eval.correct", correct)
    return {"mode": mode, "answer": text, "prompt": u.prompt_tokens, "completion": u.completion_tokens,
            "llm_ms": lat, "ret_ms": rms, "cost": cost, "docs": ids, "correct": correct,
            "judge_reason": reason, "context_chars": len(ctx), "prompt_text": f"Context:\n{ctx}\n\nQuestion: {question}"}


def judge_answer(question, answer_text, expected):
    return judge_answer_full(question, answer_text, expected)[0]


def judge_answer_full(question, answer_text, expected):
    with tracer.start_as_current_span("apex.eval.judge"):
        r = aoai.chat.completions.create(model=DEPLOYMENT, temperature=0, response_format={"type": "json_object"},
            messages=[{"role": "system", "content": "You grade answers. Reply JSON {\"correct\": true|false, \"reason\": \"...\"}. "
                                                    "An answer is correct if it contains the key facts of the reference and does not contradict it. Extra details or additional clauses that do not contradict the reference are fine: do not mark an answer wrong only because it says more than the reference."},
                      {"role": "user", "content": f"Question: {question}\nReference: {expected}\nAnswer: {answer_text}"}])
        try:
            j = json.loads(r.choices[0].message.content)
            return bool(j.get("correct")), str(j.get("reason", ""))
        except Exception:
            return None, ""


def show(results, title):
    t = Table(title=title)
    for c in ["mode", "prompt tok", "compl. tok", "LLM ms", "retrieval ms"] + (["cost €"] if PRICE_IN else []) + ["correct", "sources"]:
        t.add_column(c)
    for r in results:
        ok = {True: "[green]yes[/]", False: "[red]no[/]", None: "–"}[r["correct"]]
        t.add_row(r["mode"], f"{r['prompt']:,}", f"{r['completion']:,}", f"{r['llm_ms']:.0f}", f"{r['ret_ms']:.0f}",
                  *([f"{r['cost']:.4f}"] if PRICE_IN else []), ok, ", ".join(r["docs"][:3]))
    con.print(t)


def cmd_answer(q, index, mode, judge):
    r = answer(q, index, mode, judge)
    con.rule(f"[bold]{mode}[/]")
    con.print(r["answer"])
    show([r], "")


def cmd_compare(q, index):
    question, _, _ = resolve(q, index)
    con.rule(f"[bold]Act 2 · naive vs engineered[/] — {question}")
    res = [answer(q, index, "naive", judge=True), answer(q, index, "engineered", judge=True)]
    show(res, "Same question · same model · same data")
    a, b = res
    def delta(x, y):
        """engineered (y) vs naive (x): '−43%' when lower, '+12%' when higher."""
        pct = (y / x - 1) * 100
        return f"{'−' if pct < 0 else '+'}{abs(pct):.0f}%"

    if a["prompt"]:
        line = f"[bold cyan]Prompt tokens {delta(a['prompt'], b['prompt'])}[/]  ·  LLM latency {delta(a['llm_ms'], b['llm_ms'])}"
        if PRICE_IN and a["cost"]:
            line += f"  ·  cost {delta(a['cost'], b['cost'])}"
        con.print(line)


def cmd_eval(act):
    qs = [g for g in GOLDEN.values() if g["act"] == act and g["id"] in DEFAULT_INDEX]
    res = []
    for g in qs:
        for mode in ("naive", "engineered"):
            r = answer(g["id"], None, mode, judge=True); r["mode"] = f"{g['id']} {mode}"; res.append(r)
    show(res, f"Eval · {act}")
    for mode in ("naive", "engineered"):
        rr = [r for r in res if r["mode"].endswith(mode) and r["correct"] is not None]
        if rr:
            con.print(f"{mode:11s} accuracy {sum(r['correct'] for r in rr)}/{len(rr)} · prompt tokens {sum(r['prompt'] for r in rr):,}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("retrieve"); p.add_argument("q"); p.add_argument("--index")
    p = sub.add_parser("answer"); p.add_argument("q"); p.add_argument("--index"); p.add_argument("--mode", choices=["naive", "engineered"], default="engineered"); p.add_argument("--judge", action="store_true")
    p = sub.add_parser("compare"); p.add_argument("q"); p.add_argument("--index")
    p = sub.add_parser("eval"); p.add_argument("--act", default="act2")
    p = sub.add_parser("ask"); p.add_argument("q"); p.add_argument("--index", default="apex_contracts"); p.add_argument("--mode", choices=["naive", "engineered"], default="engineered")
    a = ap.parse_args()
    with tracer.start_as_current_span(f"apex.cli.{a.cmd}"):
        if a.cmd == "retrieve":
            cmd_retrieve(a.q, a.index)
        elif a.cmd == "answer":
            cmd_answer(a.q, a.index, a.mode, a.judge)
        elif a.cmd == "compare":
            cmd_compare(a.q, a.index)
        elif a.cmd == "eval":
            cmd_eval(a.act)
        elif a.cmd == "ask":
            cmd_answer(a.q, a.index, a.mode, False)
