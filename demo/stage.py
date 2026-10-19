#!/usr/bin/env python3
"""
Stage driver for the 45-minute talk "RAG is Broken" (AI Dev Night, Köln).

  .venv/bin/python stage.py list                 # the running order, with minutes
  .venv/bin/python stage.py preflight            # go / no-go checks (run 30 and 5 minutes before)
  .venv/bin/python stage.py warmup [--agents]    # one quiet pass so connections, caches and the scoreboard are warm
  .venv/bin/python stage.py show                 # interactive: cue card + command per step (Enter = run)
  .venv/bin/python stage.py run act2-compare     # one step; --dry-run prints what it would do
  .venv/bin/python stage.py replay act2-compare  # re-play the last recorded output (offline fallback)

Every live run is recorded in demo/stage_cache/ (git-ignored). `replay` prints the last recorded output with a "replayed" tag,
so the show goes on if the network or Azure fail. Narration cues are in English; the numbers are the measured ones in docs/RESULTS.md.
Needs demo/.env (and demo/.env.obs for the Observability checks / dashboard links). Nothing here prints secrets.
"""
import os, sys
from pathlib import Path as _P
_VENV = _P(__file__).resolve().parent / ".venv" / "bin" / "python"
if _VENV.exists() and not sys.prefix.startswith(str(_VENV.parent.parent)):  # started with the system python: re-run with the project venv
    os.execv(str(_VENV), [str(_VENV), *sys.argv])
import argparse, json, os, re, socket, subprocess, sys, time, webbrowser
from pathlib import Path
from urllib.parse import quote, urlparse

import requests
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

HERE = Path(__file__).resolve().parent
CACHE = HERE / "stage_cache"
con = Console()


def load_env(name):
    p = HERE / name
    if not p.exists():
        return {}
    out = {}
    for line in p.read_text().splitlines():
        m = re.match(r"^([A-Z0-9_]+)=(.*)$", line.strip())
        if m:
            out[m.group(1)] = m.group(2).strip().strip('"')
    return out


ENV, OBS = load_env(".env"), load_env(".env.obs")
HERO = "Which of our suppliers could expose ApexPharm to compliance risk, and what do our contracts let us do about it?"

DASH = {  # exact titles -> resolved to ids at run time (stable across project migrations)
    "scoreboard": ("obs", "Scoreboard — RAG is Broken"),
    "azure": ("obs", "[LLM Observability] Azure OpenAI — usage, latency and cost (from Azure logs)"),
    "foundry": ("obs", "[LLM Observability] Azure Foundry — Overview (dedicated data view)"),
    "billing": ("obs", "[LLM Observability] Azure billing: cost by product (dedicated data view)"),
    "agents": ("search", "Agents — baseline vs Context Engine (from Agent Builder traces)"),
    "agent_overview": ("search", "[Elastic] Agent Builder Overview"),
}

# ----------------------------------------------------------------------------- running order
STEPS = [
    dict(id="bet", act="OPEN", min=3, title="Bridge from Mike + the bet (slides 1-2)",
         say=["Mike made the agents safe. Now: what do they cost, and how do you know they're right?",
              "THE BET: how many tokens does a naive RAG send to Azure OpenAI to answer ONE question? Collect 2-3 guesses (name + number).",
              "Do not reveal anything yet: 'We'll find out in a minute', in the console. Keep the console tab closed or out of sight."],
         expect="Slides 1-2. No command. Script: docs/TALK_SCRIPT.md, Opening."),
    dict(id="bet-reveal", act="OPEN", min=3, title="The reveal: naive RAG on the HERO question, live in the console",
         say=["Switch to the console, Act 2, Naive RAG on the HERO question (Live). Run it, ask who is closest while it works (8-10 s). Three whole contracts go into the prompt. Look at the prompt tokens: THAT is the bet (measured: 7,591 tokens, about 0.011 EUR). Name the winner.",
              "It cost about one cent and it is wrong: none of the five key facts is in the prompt, the answer never mentions Veltrano. Cheap and confident is the worst combination.",
              "Under the hood: three whole contracts, none of the ones we need. The hidden risk is in news and registry extracts in other languages. Then back to the deck: slide 3, 'What you just saw'."],
         cmd=["./run.sh", "answer", "HERO", "--mode", "naive"],
         expect="If it fails: M for the recorded run. Prompt tokens 7,591 (re-check at rehearsal: write the number on the bet card). The answer lists suppliers and generic clauses, no Veltrano."),
    dict(id="context", act="OPEN", min=4, title="What you just saw, Apex, the question, three acts, what is running (slides 3-7)",
         say=["Slide 3: RAG isn't dead, naive RAG is broken, and you just saw it. The fix isn't a bigger model, it's better retrieval.",
              "Apex Conglomerate: synthetic but messy on purpose (15 indices, 9,264 documents, five languages).",
              "The question: " + HERO,
              "Three ways RAG breaks: the wrong context, too much context, context you can't see. Slide 6 is the empty table: 'we fill it in at the end'. Slide 7: what is running tonight. Leave slide 7 on screen, then switch to the console."],
         expect="Slides 3-7. No command."),
    dict(id="act1-q02", act="ACT 1", min=4, title="Wrong context: the vector cannot tell 0117 from 0171 (the main example)",
         say=["Q02 asks for contract APX-MSA-2024-0171. Semantic search returns 0125 first with scores 0.773, 0.767, 0.759: to an embedding the identifiers are almost the same string.",
              "BM25 with a code-aware field and hybrid (exact-identifier leg) return 0171 first. Identifiers are facts, not similarities.",
              "In the console open Under the hood (D): the third leg of the hybrid query."],
         cmd=["./run.sh", "retrieve", "Q02"],
         expect="Table: semantic -> APX-MSA-2024-0125 (hit no); bm25 and hybrid -> APX-MSA-2024-0171 (hit yes)."),
    dict(id="act1-q01", act="ACT 1", min=2, title="Q01, right for the wrong reason (the twist: keywords fail here)",
         say=["The opposite case: BM25 fails even with the identifier in the question. The rare word 'changes' scores 6.82, the exact identifier 5.04.",
              "The vector is first by 0.004: right, but by luck. No single mode wins: that is why we fuse them and keep an exact leg."],
         cmd=["./run.sh", "retrieve", "Q01"],
         expect="bm25 -> APX-SLA-2023-0042 (hit no); semantic and hybrid -> APX-MSA-2024-0117 (hit yes)."),
    dict(id="act1-q03", act="ACT 1", min=1, title="Two policy versions: relevant is not the same as valid",
         say=["Q03: the concentration threshold. v1.0 (2024) says 40% per entity, v2.0 (2026) says 30% at ultimate-parent level.",
              "Everyone returns v2.0 first, but v1.0 (superseded) is second. A RAG that mixes them concludes 'no action needed'. Metadata (lifecycle status) is what search lacks."],
         cmd=["./run.sh", "retrieve", "Q03"],
         expect="POL-TPRM-EN-002 first, POL-TPRM-EN-001 second in every mode: the stale policy is one rank away."),
    dict(id="act1-q04", act="ACT 1", min=1, title="Veltran vs Veltrano",
         say=["Q04: Who owns Veltran Logistik? A family company with almost the same name as the holding we meet next.",
              "Names are not meaning: the right document is first, the neighbours are other companies. Keep it short: this sets up Act 2. (Q05, the German control, only if asked.)",
              "Close Act 1: hit at one, keywords 75, vector 75, hybrid 100. Nobody wins alone."],
         cmd=["./run.sh", "retrieve", "Q04"],
         expect="NEWS-2026-0311-006 first in every mode."),
    dict(id="act2-compare", act="ACT 2", min=3, title="Engineered prompt: the relevant fragments only (Q06)",
         say=["20-second recap: 'Remember the bet? One question, 7,591 tokens, cheap and wrong.' Now a question where the size of the prompt really hurts.",
              "A question on long contracts (Q06: change-of-control obligations in the Rheinchem MSA). Same model, same data. Only the context changes.",
              "Prompt tokens -43%, cost -36% (about 110 vs 70 EUR per 10,000 questions). Both correct. Do NOT run compare on HERO: its contracts are short, the saving is only 3%.",
              "Be honest about latency: for a single call it is about the same; the answer length dominates. The win is tokens and cost."],
         cmd=["./run.sh", "compare", "Q06"],
         expect="naive ~13,650 tokens / 0.011 EUR; engineered ~7,800 / 0.007 EUR; last line: Prompt tokens -43% ... cost -36%."),
    dict(id="act2-lab", act="ACT 2", min=3, title="Wrong context lab: ask for any contract (console only)",
         say=["Ask the room for a contract id (or use APX-MSA-2022-0388). The truth is read from clause 15.3 of the contract itself.",
              "Naive RAG gets 1 of 8 right (the control, 0117, is right by luck): it pulls the same near-duplicates whatever you ask and answers with another contract's number.",
              "Engineered: 8 of 8. A confident answer about the wrong contract is worse than no answer."],
         expect="Console: Try the demo > Act 2 > Wrong context lab. No terminal command."),
    dict(id="act2-agents", act="ACT 2", min=6, title="Agents: baseline vs Context Engine (console or Kibana, Search project)",
         say=["Same model, same tools, same instructions. One agent has the Context Engine AI index. Click Run both (10-40 s); talk while they run.",
              "Under the hood: the baseline searches contracts supplier by supplier (around ten tool calls) and never finds Veltrano; the other makes one call, a hybrid query on the index of knowledge indicators.",
              "5 runs: HERO baseline 1/5, Context Engine 5/5; medians 141k to 25k tokens, 20 to 4 s, 14 to 2 LLM calls. Q10 (spend share): 4/5 against 5/5, 170k to 24k tokens.",
              "Say it plainly: works in most runs, not all; the agent uses a tool of ours on top of the AI index; Context Engine is a private preview."],
         clip=HERO, urls=[("search", "/app/agent_builder")], dash=["agents"],
         expect="Question copied to the clipboard. Baseline: no Veltrano group. Context: Veltrano group, 32.5% > 30%, clauses 14.3 / 12.6 / 9.4. If it fails: R to run again, M for the recorded run."),
    dict(id="act3-fire-alert", act="ACT 3", min=1, title="Trigger the alert first (one naive call)",
         say=["'I just sent one deliberately fat prompt to Azure. Keep it in mind, we'll come back to it.' (> 10,000 prompt tokens in one call; the alert goes active in 1-2 min.)",
              "In the console: Dashboards and the alert > Fire the alert now. Or the terminal command below.",
              "Show slide 8 (where every number comes from) while the alert warms up: one minute."],
         cmd=["./run.sh", "compare", "Q06"], expect="Same table as before. The alert goes active within 1-2 minutes and lasts about 5."),
    dict(id="act3-dashboards", act="ACT 3", min=7, title="Invisible context made visible: six beats (Observability + Search)",
         say=["1 Scoreboard (2.5 min): tokens and cost per mode, cost per 10,000 questions, hit@1 bars, accuracy with 'x of y judged'. 'Measured by OpenTelemetry in our own app.'",
              "2 Azure usage and cost (1 min): Azure's own logs; average about 1.5 s, p95 about 3x: the agent calls.  3 Foundry overview (30 s): metrics, 5-10 min behind.",
              "4 Agents (1.5 min): baseline about 14 LLM calls, 20 s, 140k tokens; Context Engine 2, 4 s, 25k. Then the [Elastic] Agent Builder Overview, out of the box.",
              "5 Billing (45 s): Azure billed ~3.9 EUR, my estimate ~5.9 (the estimate is an upper bound, it cannot see the cache discount; say the live numbers); the monitoring plumbing costs more than the model.",
              "6 Alert (45 s): Alerts on All statuses, the rule's ES|QL: 'The alert comes before the bill, not after.'  Close: 'Choose it, measure it, alert on it.'"],
         dash=["scoreboard", "azure", "foundry", "agents", "agent_overview", "billing"], urls=[("obs", "/app/observability/alerts?_a=(kuery:'',rangeFrom:now-24h,rangeTo:now,status:all)")],
         expect="Tabs open in this order: Scoreboard, Azure usage and cost, Foundry Overview, Agents, Agent Builder Overview, Billing, Alerts. Script: docs/TALK_SCRIPT.md, Act 3."),
    dict(id="close", act="CLOSE", min=3, title="Close (slide 9, scoreboard filled in)",
         say=["Three messages: right context beats more context; tokens and cost are measurable on your own data; you can see it, so you can fix it.",
              "The repo is yours after the event (it contains the answers)."],
         expect="Slide 9 (filled scoreboard). No command."),
    dict(id="qa", act="Q&A", min=4, title="Questions (cheat sheet)",
         say=["Context Engine: private preview, so say 'experimental'; the agent result uses our lookup tool on top of the AI index.",
              "Latency: single call about the same (answer length dominates); the agents get faster because they make fewer calls.",
              "Cost: live number is an estimate from tokens x the public price list (EUR 0.726 / 4.356 per 1M for gpt-5.4-mini, Data Zone); the invoice arrives the next day and is lower than the estimate when caching kicks in (agents).",
              "Data: synthetic; deployment is Data Zone EU (not 'stays in Germany'). The repo goes public after the event."],
         expect="Slide 10 (Q&A) as backdrop, or 7-8 for the architecture map. When done: slide 11 (thank you). No command."),
]
BY_ID = {s["id"]: s for s in STEPS}


# ----------------------------------------------------------------------------- helpers
def kb(project):
    return (ENV.get("KIBANA_URL") if project == "search" else OBS.get("OBS_KIBANA_URL", "")).rstrip("/")


def kb_headers(project):
    key = ENV.get("ES_API_KEY") if project == "search" else OBS.get("OBS_API_KEY")
    return {"Authorization": f"ApiKey {key}", "kbn-xsrf": "true", "x-elastic-internal-origin": "kibana", "Elastic-Api-Version": "2023-10-31"}


def resolve_dashboard(key):
    project, title = DASH[key]
    base = kb(project)
    if not base:
        return None, f"no Kibana URL for the {project} project (set {'KIBANA_URL in .env' if project == 'search' else 'OBS_KIBANA_URL in .env.obs'})"
    try:
        r = requests.get(f"{base}/api/saved_objects/_find", params={"type": "dashboard", "search_fields": "title", "search": title.split(" — ")[0].split("]")[-1].strip().split(" ")[0] + "*", "per_page": 100},
                         headers=kb_headers(project), timeout=20)
        for d in r.json().get("saved_objects", []):
            if d["attributes"]["title"] == title:
                rng = "from:'2026-10-13T00:00:00.000Z',to:'2026-10-23T00:00:00.000Z'" if key == "billing" else "from:now-1h,to:now"   # the invoice lags: show the whole period
                return f"{base}/app/dashboards#/view/{d['id']}?_g=(filters:!(),refreshInterval:(pause:!t,value:60000),time:({rng}))", None
        return None, f"dashboard not found: {title}"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def open_urls(step, dry):
    for key in step.get("dash", []):
        url, err = resolve_dashboard(key)
        con.print(f"  [cyan]open[/] {DASH[key][1]}" + (f"  [red]({err})[/]" if err else ""))
        if url and not dry:
            webbrowser.open(url); time.sleep(0.6)
    for project, path in step.get("urls", []):
        base = kb(project)
        con.print(f"  [cyan]open[/] {project}: {path}" + ("" if base else "  [red](no Kibana URL configured)[/]"))
        if base and not dry:
            webbrowser.open(base + path); time.sleep(0.6)


def copy_clip(text, dry):
    con.print(f"  [cyan]clipboard[/] {text[:80]}...")
    if not dry:
        subprocess.run(["pbcopy"], input=text.encode(), check=False)


def cue_card(step):
    body = "\n".join(f"• {s}" for s in step["say"])
    con.print(Panel(body + (f"\n\n[dim]expect: {step['expect']}[/]" if step.get("expect") else ""), title=f"[bold]{step['act']} · {step['title']}[/]  [dim]~{step['min']} min · {step['id']}[/]", border_style="blue"))


def run_cmd(step, dry):
    cmd = step.get("cmd")
    if not cmd:
        return 0
    env = dict(os.environ); env["PATH"] = f"{HERE / '.venv' / 'bin'}:{env['PATH']}"
    con.print(f"  [green]$ {' '.join(cmd)}[/]")
    if dry:
        return 0
    CACHE.mkdir(exist_ok=True)
    t0, lines = time.time(), []
    p = subprocess.Popen(cmd, cwd=HERE, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    for line in p.stdout:
        if re.match(r"^(ERROR|WARNING):opentelemetry", line):   # exporter noise: never show it on stage
            continue
        sys.stdout.write(line); sys.stdout.flush(); lines.append(line)
    rc = p.wait()
    (CACHE / f"{step['id']}.txt").write_text("".join(lines))
    (CACHE / f"{step['id']}.json").write_text(json.dumps({"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "cmd": cmd, "seconds": round(time.time() - t0, 1), "rc": rc}))
    return rc


def replay(step_id, delay=0.02):
    f = CACHE / f"{step_id}.txt"
    if not f.exists():
        con.print(f"[red]no recording for {step_id}[/] (run it live once, or run warmup)"); return 1
    meta = json.loads((CACHE / f"{step_id}.json").read_text())
    con.print(f"[dim]replayed from {meta['ts']} (recorded run, {meta['seconds']} s)[/]")
    for line in f.read_text().splitlines(True):
        sys.stdout.write(line); sys.stdout.flush(); time.sleep(delay)
    return 0


def do_step(step, dry=False, live=True):
    cue_card(step)
    if step.get("clip"):
        copy_clip(step["clip"], dry)
    open_urls(step, dry)
    if step.get("cmd"):
        if live:
            rc = run_cmd(step, dry)
            if rc != 0 and not dry:
                con.print(f"[red]command failed (rc={rc})[/] — press r to replay the last recording")
            return rc
        return replay(step["id"])
    return 0


# ----------------------------------------------------------------------------- commands
def cmd_list(_a):
    t = Table(title="Running order (45 min, 19:30-20:15)"); [t.add_column(c) for c in ("#", "step", "act", "min", "what")]
    tot = 0
    for i, s in enumerate(STEPS, 1):
        tot += s["min"]; t.add_row(str(i), s["id"], s["act"], str(s["min"]), s["title"])
    t.caption = f"{tot} min in total"
    con.print(t)


def cmd_show(a):
    for s in STEPS:
        cue_card(s)
        while True:
            ans = con.input("[bold][Enter][/] run   [s] skip   [r] replay   [o] open links only   [q] quit > ").strip().lower()
            if ans == "q":
                return
            if ans == "s":
                break
            if ans == "r":
                replay(s["id"]); continue
            if ans == "o":
                open_urls(s, a.dry_run); continue
            if s.get("clip"):
                copy_clip(s["clip"], a.dry_run)
            open_urls(s, a.dry_run)
            if s.get("cmd"):
                run_cmd(s, a.dry_run)
            break


def cmd_run(a):
    s = BY_ID.get(a.step)
    if not s:
        sys.exit(f"unknown step {a.step}; try: {', '.join(BY_ID)}")
    sys.exit(do_step(s, dry=a.dry_run))


def cmd_replay(a):
    ids = [s["id"] for s in STEPS if s.get("cmd")] if a.step == "all" else [a.step]
    for i in ids:
        con.rule(i); replay(i)


def cmd_warmup(a):
    con.print("[bold]warmup[/]: quiet pass (connections, caches, a few spans on the scoreboard)")
    for sid in ("act1-q02", "act1-q01", "act1-q03", "act1-q04", "bet-reveal", "act2-compare"):
        s = BY_ID[sid]; con.print(f"  [dim]{sid}[/]", end=" ")
        t0 = time.time(); env = dict(os.environ); env["PATH"] = f"{HERE / '.venv' / 'bin'}:{env['PATH']}"
        if a.dry_run:
            con.print(" ".join(s["cmd"])); continue
        CACHE.mkdir(exist_ok=True)
        p = subprocess.run(s["cmd"], cwd=HERE, env=env, capture_output=True, text=True)
        out = "".join(l for l in (p.stdout + p.stderr).splitlines(True) if not re.match(r"^(ERROR|WARNING):opentelemetry", l))
        (CACHE / f"{sid}.txt").write_text(out)
        (CACHE / f"{sid}.json").write_text(json.dumps({"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "cmd": s["cmd"], "seconds": round(time.time() - t0, 1), "rc": p.returncode}))
        con.print(f"rc={p.returncode} {time.time() - t0:.0f}s")
    if a.agents:
        con.print("  agents (1 run each, ~1-2 min)")
        if not a.dry_run:
            subprocess.run([str(HERE / ".venv/bin/python"), "agents_eval.py", "--runs", "1", "--pause", "5"], cwd=HERE)


def check(name, fn):
    try:
        status, detail = fn()
    except Exception as e:
        status, detail = "FAIL", f"{type(e).__name__}: {str(e)[:100]}"
    return name, status, detail


def preflight_rows():
    """Run all go/no-go checks; returns [(name, status, detail)]. Used by `preflight` and by the site's Service status page."""
    es = ENV.get("ES_URL", "").rstrip("/"); hes = {"Authorization": f"ApiKey {ENV.get('ES_API_KEY', '')}", "Content-Type": "application/json"}
    placeholder = lambda v: (not v) or "<" in v
    checks = []

    def env_ok():
        need = ["ES_URL", "ES_API_KEY", "KIBANA_URL", "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_DEPLOYMENT", "OTEL_EXPORTER_OTLP_ENDPOINT", "OTEL_EXPORTER_OTLP_HEADERS"]
        miss = [k for k in need if placeholder(ENV.get(k))]
        return ("FAIL", "missing/placeholder: " + ", ".join(miss)) if miss else ("OK", "all set in .env")
    checks.append(("env (.env)", env_ok))

    def search_up():
        r = requests.get(es + "/", headers=hes, timeout=15); v = r.json().get("version", {})
        return ("OK", f"{v.get('build_flavor')} {v.get('number')}") if r.ok else ("FAIL", f"HTTP {r.status_code}")
    checks.append(("Search project reachable", search_up))

    def counts():
        exp = {"apex_contracts": 72, "apex_service_tickets": 578, "apex_suppliers": 24, "apex_corporate_news": 95}; bad = []
        for idx, n in exp.items():
            c = requests.post(f"{es}/{idx}/_count", headers=hes, timeout=15).json().get("count")
            if c != n: bad.append(f"{idx}={c} (expected {n})")
        return ("FAIL", "; ".join(bad)) if bad else ("OK", "contracts 72 · tickets 578 · suppliers 24 · news 95")
    checks.append(("data imported", counts))

    def inference():
        r = requests.get(es + "/_inference/_all", headers=hes, timeout=20).json().get("endpoints", []); ids = {e.get("inference_id") for e in r}
        miss = [i for i in (".jina-embeddings-v5-text-small", "azure-openai-gpt-5-4-mini") if i not in ids]
        return ("FAIL", "missing: " + ", ".join(miss)) if miss else ("OK", "Jina v5 + azure-openai-gpt-5-4-mini")
    checks.append(("inference endpoints", inference))

    def kis():
        r = requests.post(es + "/_query", headers=hes, json={"query": "FROM ai-index-idx-apex-supplier-intelligence | STATS n = COUNT(*)"}, timeout=20)
        n = r.json().get("values", [[None]])[0][0] if r.ok else None
        return ("OK", f"{n} KIs (expected 11)") if n == 11 else ("WARN", f"KIs={n} (expected 11; the key may lack access to the AI index: check in Kibana)")
    checks.append(("Context Engine KIs", kis))

    def agents():
        out = []
        for a in ("apex-analyst-baseline", "apex-analyst-context"):
            r = requests.get(f"{kb('search')}/api/agent_builder/agents/{a}", headers=kb_headers("search"), timeout=20)
            out.append(f"{a}:{r.status_code}")
            if a.endswith("context") and r.ok and "apex_context_lookup" not in json.dumps(r.json()["configuration"]["tools"]):
                return "FAIL", "context agent lacks tool apex_context_lookup"
        return ("OK", ", ".join(out)) if all(o.endswith("200") for o in out) else ("FAIL", ", ".join(out))
    checks.append(("agents + tool", agents))

    def azure():
        ep = ENV["AZURE_OPENAI_ENDPOINT"].rstrip("/"); dep = ENV["AZURE_OPENAI_DEPLOYMENT"]
        r = requests.post(f"{ep}/openai/deployments/{dep}/chat/completions?api-version={ENV.get('AZURE_OPENAI_API_VERSION', '2024-10-21')}",
                          headers={"api-key": ENV["AZURE_OPENAI_API_KEY"]}, json={"messages": [{"role": "user", "content": "OK?"}], "max_completion_tokens": 16}, timeout=30)
        lim, rem = r.headers.get("x-ratelimit-limit-tokens"), r.headers.get("x-ratelimit-remaining-tokens")
        if r.status_code == 429: return "FAIL", f"429 rate limited (limit {lim} tokens/min): wait a minute"
        if not r.ok: return "FAIL", f"HTTP {r.status_code}"
        return ("OK" if int(lim or 0) >= 200000 else "WARN"), f"{dep}: {r.elapsed.total_seconds():.1f}s · limit {lim} tokens/min, remaining {rem}"
    checks.append(("Azure OpenAI", azure))

    def otlp():
        host = urlparse(ENV["OTEL_EXPORTER_OTLP_ENDPOINT"]).hostname
        ip = socket.gethostbyname(host)
        proto = ENV.get("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")
        return ("OK" if proto == "http/protobuf" else "WARN"), f"{host} -> {ip} · protocol {proto}" + ("" if proto == "http/protobuf" else " (use http/protobuf behind proxies/VPN)")
    checks.append(("OTLP endpoint", otlp))

    if OBS.get("OBS_KIBANA_URL"):
        oes = OBS["OBS_KIBANA_URL"].replace(".kb.", ".es.").rstrip("/"); hob = {"Authorization": f"ApiKey {OBS.get('OBS_API_KEY', '')}", "Content-Type": "application/json"}

        def spans():
            r = requests.post(oes + "/_query", headers=hob, json={"query": 'FROM traces-* | WHERE service.name == "apex-rag-demo" AND @timestamp > NOW() - 15 minutes | STATS n = COUNT(*)'}, timeout=20)
            n = r.json().get("values", [[0]])[0][0] if r.ok else None
            return ("OK", f"{n} spans in the last 15 min") if n else ("WARN", f"no CLI spans in the last 15 min (n={n}): run `stage.py warmup`")
        checks.append(("CLI traces in Observability", spans))

        def alert():
            r = requests.get(OBS["OBS_KIBANA_URL"].rstrip("/") + "/api/alerting/rules/_find", params={"per_page": 100, "search": "Prompt too large"}, headers=kb_headers("obs"), timeout=20)
            rules = [x for x in r.json().get("data", []) if x["name"].startswith("[LLM] Prompt too large")]
            return ("OK", f"rule {'enabled' if rules[0]['enabled'] else 'DISABLED'}, last run {(rules[0].get('last_run') or {}).get('outcome')}") if rules else ("FAIL", "alert rule not found")
        checks.append(("alert rule", alert))
    else:
        checks.append(("Observability checks", lambda: ("WARN", "demo/.env.obs missing: spans, alert and dashboard links not checked")))

    def dashboards():
        miss = [k for k in DASH if resolve_dashboard(k)[0] is None]
        return ("OK", f"{len(DASH)} dashboards found") if not miss else ("WARN", "not found / not configured: " + ", ".join(miss))
    checks.append(("dashboards", dashboards))

    return [check(name, fn) for name, fn in checks]


def cmd_preflight(_a):
    rows = preflight_rows()
    t = Table(title="Preflight"); [t.add_column(c) for c in ("check", "", "detail")]
    worst = "OK"
    for n, s, d in rows:
        worst = "FAIL" if s == "FAIL" else ("WARN" if s == "WARN" and worst == "OK" else worst)
        t.add_row(n, {"OK": "[green]OK[/]", "WARN": "[yellow]WARN[/]", "FAIL": "[red]FAIL[/]"}[s], d)
    con.print(t)
    con.print({"OK": "[bold green]GO[/]", "WARN": "[bold yellow]GO with warnings[/]", "FAIL": "[bold red]NO-GO[/]"}[worst])
    sys.exit(1 if worst == "FAIL" else 0)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--dry-run", action="store_true", help="print commands and links without running/opening them")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", parents=[common]); sub.add_parser("show", parents=[common]); sub.add_parser("preflight", parents=[common])
    p = sub.add_parser("warmup", parents=[common]); p.add_argument("--agents", action="store_true")
    p = sub.add_parser("run", parents=[common]); p.add_argument("step")
    p = sub.add_parser("replay", parents=[common]); p.add_argument("step", nargs="?", default="all")
    a = ap.parse_args()
    {"list": cmd_list, "show": cmd_show, "preflight": cmd_preflight, "warmup": cmd_warmup, "run": cmd_run, "replay": cmd_replay}[a.cmd](a)
