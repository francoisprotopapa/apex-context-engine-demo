#!/usr/bin/env python3
"""
Record the PRACTICE data of the demo console: runs every item once for real and stores the result in site/data/practice.json.

  cd demo && .venv/bin/python ../site/record_practice.py            # everything (~4-5 min, a few cents of Azure OpenAI)
  cd demo && .venv/bin/python ../site/record_practice.py --only retrieve,scoreboard

Run it the day before the talk, so Practice shows today's numbers. Each entry keeps its own timestamp and is labelled in the UI
as "recorded, not a new measurement".
"""
import os, sys
from pathlib import Path as _P
_VENV = _P(__file__).resolve().parent.parent / "demo" / ".venv" / "bin" / "python"
if _VENV.exists() and not sys.prefix.startswith(str(_VENV.parent.parent)):  # started with the system python: re-run with the project venv
    os.execv(str(_VENV), [str(_VENV), *sys.argv])
import argparse, json, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import app  # noqa: E402  (loads demo/.env, connects nothing until used)

def typical_agent(agent, q, n=3):
    """Run the agent n times and keep the run that represents the majority outcome (median time); record how many were fully correct."""
    runs = []
    for i in range(n):
        runs.append(app.do_agent(agent, q))
        if i < n - 1:
            time.sleep(8)
    k = sum(1 for x in runs if x["correct"]); majority = k * 2 >= n
    pick = sorted([x for x in runs if x["correct"] == majority], key=lambda x: x["seconds"])
    chosen = pick[len(pick) // 2]
    return {**chosen, "sample": {"runs": n, "correct": k}}


ITEMS = [
    *[(f"retrieve:{q}", "retrieve", lambda q=q: app.do_retrieve(q)) for q in ("Q01", "Q02", "Q03", "Q04", "Q05")],
    ("answer:HERO:naive", "answer", lambda: app.do_answer("HERO", "naive")),
    *[(f"compare:{q}", "compare", lambda q=q: app.do_compare(q)) for q in ("Q06", "Q07", "Q08")],
    *[(f"agent:{a}:{q}", "agent", lambda a=a, q=q: typical_agent(a, q)) for q in ("HERO", "Q09", "Q10") for a in app.ae.AGENTS],
    *[(f"clause:{c}", "clause", lambda c=c: app.do_clause(c)) for c in app.CLAUSE_IDS],
    ("scoreboard", "scoreboard", app.do_scoreboard),
]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated kinds: retrieve,answer,compare,clause,agent,scoreboard")
    ap.add_argument("--pause", type=int, default=12, help="seconds between agent runs (Azure tokens-per-minute limit)")
    a = ap.parse_args()
    kinds = set(a.only.split(",")) if a.only else None
    store = json.loads(app.PRACTICE_FILE.read_text()) if app.PRACTICE_FILE.exists() else {}
    for key, kind, fn in ITEMS:
        if kinds and kind not in kinds:
            continue
        t0 = time.time()
        try:
            data = fn()
            store[key] = {"recorded_at": time.strftime("%Y-%m-%d %H:%M:%S"), "data": data}
            print(f"  ok   {key:42s} {time.time() - t0:5.1f}s", flush=True)
        except Exception as e:
            print(f"  FAIL {key:42s} {type(e).__name__}: {str(e)[:100]}", flush=True)
        if kind == "agent":
            time.sleep(a.pause)
        app.PRACTICE_FILE.parent.mkdir(exist_ok=True)
        app.PRACTICE_FILE.write_text(json.dumps(store, indent=1, ensure_ascii=False))
    print("recorded:", len(store), "entries ->", app.PRACTICE_FILE)
