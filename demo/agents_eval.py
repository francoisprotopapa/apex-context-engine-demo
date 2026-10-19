#!/usr/bin/env python3
"""Baseline vs Context Engine agents — repeated runs through the Agent Builder converse API.

  python agents_eval.py [--runs 3] [--connector azure-openai-gpt-5-4-mini]

Needs KIBANA_URL in demo/.env (Kibana base URL of the Search project) and ES_API_KEY.
Correctness is a keyword rubric (all must appear in the answer), not an LLM judge.
"""
import os, sys
from pathlib import Path as _P
_VENV = _P(__file__).resolve().parent / ".venv" / "bin" / "python"
if _VENV.exists() and not sys.prefix.startswith(str(_VENV.parent.parent)):  # started with the system python: re-run with the project venv
    os.execv(str(_VENV), [str(_VENV), *sys.argv])
import argparse, json, os, re, statistics, time
from pathlib import Path

import requests
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")
KIBANA = os.environ["KIBANA_URL"].rstrip("/")
H = {"Authorization": f"ApiKey {os.environ['ES_API_KEY']}", "kbn-xsrf": "true",
     "Content-Type": "application/json", "x-elastic-internal-origin": "kibana"}

QUESTIONS = {
    "HERO": ("Which of our suppliers could expose ApexPharm to compliance risk, and what do our contracts let us do about it?",
             ["Veltrano", "32.5", "14.3", "12.6", "9.4"]),
    "Q09": ("Which of our ApexPharm suppliers belong to the same corporate group?",
            ["Veltrano", "Orvia", "Rheinchem", "Lumen", "Kestrel"]),
    "Q10": ("What share of ApexPharm critical supplier spend sits with a single corporate group?",
            ["32.5", "Veltrano"]),
}
AGENTS = ["apex-analyst-baseline", "apex-analyst-context"]


def ask(agent, question, connector):
    r = requests.post(f"{KIBANA}/api/agent_builder/converse", headers=H, timeout=290,
                      json={"agent_id": agent, "input": question, "connector_id": connector})
    r.raise_for_status()
    d = r.json()
    u = d.get("model_usage", {})
    return {"llm_calls": u.get("llm_calls", 0), "in": u.get("input_tokens", 0), "out": u.get("output_tokens", 0),
            "s": d.get("time_to_last_token", 0) / 1000,
            "tools": [s.get("tool_id") for s in d.get("steps", []) if s.get("type") == "tool_call"],
            "answer": d.get("response", {}).get("message", ""), "trace": trace(d.get("steps", []))}


def trace(steps):
    """What the agent did, in order: its reasoning, each tool call with its parameters, the ES|QL it ran, and how much came back."""
    out = []
    for st in steps:
        if st.get("type") == "reasoning":
            out.append({"type": "reasoning", "text": (st.get("reasoning") or "")[:400]})
        elif st.get("type") == "tool_call":
            item = {"type": "tool", "tool": st.get("tool_id"), "params": json.dumps(st.get("params", {}), ensure_ascii=False)[:600], "esql": None, "rows": None, "found": None}
            for x in st.get("results") or []:
                dd = x.get("data", {}) or {}
                if x.get("type") == "query" and dd.get("esql"):
                    item["esql"] = dd["esql"][:2500]
                elif x.get("type") == "esql_results":
                    item["rows"] = len(dd.get("values", []))
                    item["esql"] = item["esql"] or (dd.get("query") or "")[:2500]
                elif x.get("type") == "resource_list":
                    res = dd.get("resources", []) or []
                    item["found"] = len(res)
                elif x.get("type") in ("other", "search") or "results" in dd:
                    item["found"] = len(dd.get("results", []) or [])
            out.append(item)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--connector", default="azure-openai-gpt-5-4-mini")
    ap.add_argument("--pause", type=int, default=20, help="seconds between calls (Azure TPM limit)")
    a = ap.parse_args()
    rows = []
    for qid, (q, must) in QUESTIONS.items():
        for agent in AGENTS:
            for i in range(a.runs):
                try:
                    r = ask(agent, q, a.connector)
                except Exception as ex:  # keep going: a 429 is data too
                    r = {"llm_calls": 0, "in": 0, "out": 0, "s": 0, "tools": [], "answer": f"ERROR {ex}"}
                missing = [m for m in must if not re.search(re.escape(m), r["answer"], re.I)]
                r.update(q=qid, agent=agent, ok=not missing, missing=missing,
                         ce_calls=sum(t.startswith("platform.context_engine.query") for t in r["tools"]))
                rows.append(r)
                print(f"{qid} {agent:24s} run{i+1} ok={r['ok']!s:5} llm={r['llm_calls']:2d} in={r['in']:7,d} "
                      f"{r['s']:4.0f}s tools={len(r['tools']):2d} ce_queries={r['ce_calls']} missing={r['missing']}", flush=True)
                time.sleep(a.pause)
    (HERE / "agents_eval_results.json").write_text(json.dumps(rows, indent=1))
    print("\nSUMMARY (mean over runs)")
    for qid in QUESTIONS:
        for agent in AGENTS:
            rr = [r for r in rows if r["q"] == qid and r["agent"] == agent]
            print(f"{qid:5s} {agent:24s} correct {sum(r['ok'] for r in rr)}/{len(rr)}  llm_calls {statistics.mean(r['llm_calls'] for r in rr):4.1f}  "
                  f"in_tokens {statistics.mean(r['in'] for r in rr):9,.0f}  latency {statistics.mean(r['s'] for r in rr):4.0f}s  "
                  f"tool_calls {statistics.mean(len(r['tools']) for r in rr):4.1f}")
