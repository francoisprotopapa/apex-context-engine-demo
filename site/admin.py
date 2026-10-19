"""Admin page of the demo console: runs the preparation commands with a button, one at a time, and streams their output.
Local use only (the server listens on 127.0.0.1). Disabled with APEX_ADMIN=0 (e.g. for the public practice-only version)."""
import os, re, subprocess, sys, threading, time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

SITE = Path(__file__).resolve().parent
DEMO = SITE.parent / "demo"
ENABLED = os.environ.get("APEX_ADMIN", "1") != "0"
PY = sys.executable

JOBS = [
    dict(id="preflight", group="stage", title="Preflight: is everything up?", cmd=["stage.py", "preflight"], minutes="~15 s", cost="none",
         when="T-30 min and T-5 min before the talk, and any time something looks odd.",
         what="Checks the Search project, imported data, the 11 Context Engine indicators, both agents, Azure OpenAI (limit and remaining tokens), the OTLP endpoint, recent CLI spans, the alert rule and the dashboards. Ends with GO or NO-GO.",
         tip="If it says NO-GO, fix that line first (the detail tells you what). A WARN about CLI spans disappears after a warmup."),
    dict(id="warmup", group="stage", title="Warmup (quiet pass)", cmd=["stage.py", "warmup"], minutes="~30 s", cost="a few cents of Azure OpenAI",
         when="T-30 min and T-5 min, right after the preflight.",
         what="Runs Act 1 (Q02, Q03, Q04) and Act 2 (HERO naive, compare Q06) once. Connections and caches get warm and the scoreboard gets recent traces; the outputs are saved for the offline replay.",
         tip="The scoreboard only looks at the last 2 hours and the alert at the last 5 minutes, so do the last warmup shortly before you start."),
    dict(id="warmup_agents", group="stage", title="Warmup with agents", cmd=["stage.py", "warmup", "--agents"], minutes="~2 min", cost="a few cents",
         when="T-30 min (once). Optional at T-5 min.",
         what="Same as the warmup, plus one run of each agent (baseline and Context Engine) on HERO, Q09 and Q10. Warms the Agent Builder side and puts a first run on the Agents dashboard.",
         tip="Agents are not deterministic: one wrong baseline run is normal, it is the point of the demo."),
    dict(id="agents_eval", group="day_before", title="Agent evaluation, 5 runs per question", cmd=["agents_eval.py", "--runs", "5"], minutes="~8-10 min", cost="~€0.10-0.20",
         when="The day before (21 Oct). Not needed again on the day.",
         what="Runs baseline vs Context Engine five times on HERO, Q09 and Q10 and scores the answers with the keyword rubric. This fills the Agents dashboard with a meaningful sample, and gives you the numbers for the slide (check docs/RESULTS.md).",
         tip="If the success rates changed a lot, update slide 8 and docs/RESULTS.md."),
    dict(id="record_practice", group="day_before", title="Record Practice (the fallback data)", cmd=["record_practice.py"], minutes="~5-6 min", cost="~€0.10",
         when="The day before, after the agent evaluation. Re-run it if you change anything in the demo.",
         what="Runs every item of the console once for real (Act 1, Act 2, agents three times each, scoreboard) and stores the results as Practice. If the network or Azure fail on stage, press M and the console shows these runs, labelled as recorded.",
         tip="It records the scoreboard last, so the scoreboard has fresh traffic. Don't start it while another job is running."),
    dict(id="record_scoreboard", group="day_before", title="Record only the scoreboard", cmd=["record_practice.py", "--only", "scoreboard"], minutes="~10 s", cost="none",
         when="After the day-before warmup, or whenever the Practice scoreboard looks empty.",
         what="Re-records just the scoreboard page of Practice (tokens, cost, billed vs estimated). Needs recent traffic: run a warmup first.",
         tip="If Act 2 and Agents are empty in Practice, run Warmup with agents and then this."),
]
BY_ID = {j["id"]: j for j in JOBS}
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
state = {"id": None, "lines": [], "rc": None, "started": None, "ended": None}
lock = threading.Lock()
router = APIRouter(prefix="/api/admin")
on_done = None   # set by app.py: reload Practice data after a recording


class Run(BaseModel):
    id: str


def _meta(j):
    return {k: j[k] for k in ("id", "group", "title", "when", "what", "tip", "minutes", "cost")} | {"cmd": "python3 " + " ".join(j["cmd"])}


def _worker(j):
    env = dict(os.environ, NO_COLOR="1", TERM="dumb", COLUMNS="110", PYTHONUNBUFFERED="1")
    try:
        script = DEMO / j["cmd"][0] if (DEMO / j["cmd"][0]).exists() else SITE / j["cmd"][0]
        p = subprocess.Popen([PY, str(script), *j["cmd"][1:]], cwd=DEMO, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in p.stdout:
            line = ANSI.sub("", line.rstrip("\n"))
            if re.match(r"^(ERROR|WARNING):opentelemetry", line):
                continue
            with lock:
                state["lines"].append(line); state["lines"] = state["lines"][-400:]
        rc = p.wait()
    except Exception as e:
        rc = -1
        with lock:
            state["lines"].append(f"{type(e).__name__}: {e}")
    with lock:
        state.update(rc=rc, ended=time.time())
    if rc == 0 and on_done:
        on_done(j["id"])


@router.get("/jobs")
def jobs():
    if not ENABLED:
        raise HTTPException(404, "admin disabled")
    return [_meta(j) for j in JOBS]


@router.get("/status")
def status():
    if not ENABLED:
        raise HTTPException(404, "admin disabled")
    with lock:
        running = state["id"] is not None and state["ended"] is None
        return {"id": state["id"], "running": running, "rc": state["rc"], "lines": list(state["lines"]),
                "elapsed": round((state["ended"] or time.time()) - state["started"], 1) if state["started"] else None}


@router.post("/run")
def run(r: Run):
    if not ENABLED:
        raise HTTPException(404, "admin disabled")
    j = BY_ID.get(r.id)
    if not j:
        raise HTTPException(404, "unknown job")
    with lock:
        if state["id"] is not None and state["ended"] is None:
            raise HTTPException(409, f"'{state['id']}' is still running")
        state.update(id=j["id"], lines=[], rc=None, started=time.time(), ended=None)
    threading.Thread(target=_worker, args=(j,), daemon=True).start()
    return {"started": j["id"]}
