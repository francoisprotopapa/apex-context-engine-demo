#!/usr/bin/env python3
"""
Provision a NEW Elastic Serverless project with the Kibana-side pieces of the demo.
Data/indices are imported separately with import/import_apex.py --config import/config_new.py.

  python3 tools/provision.py --env demo/.env.new check
  python3 tools/provision.py --env demo/.env.new azure          # Azure OpenAI inference endpoint (chat_completion)
  python3 tools/provision.py --env demo/.env.new agents         # 5 index_search tools + the 2 agents
  python3 tools/provision.py --env demo/.env.new workflows      # apex-targeted-kis (+ metadata) -- needs the AI index first
  python3 tools/provision.py --env demo/.env.new dashboards      # Agents dashboard (Agent Builder traces)
  python3 tools/provision.py --env demo/.env.new all

The env file needs ES_URL, ES_API_KEY and KIBANA_URL (and, for `azure`, AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_API_KEY).
Nothing here prints keys. Idempotent: existing objects are updated, not duplicated.
Status of each call is printed; anything that fails is reported, not hidden.
"""
import argparse, json, re, sys
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
EXPORT = ROOT / "kibana_export"
AZ_ENDPOINT_ID = "azure-openai-gpt-5-4-mini"


def load_env(path):
    env = {}
    for line in Path(path).read_text().splitlines():
        m = re.match(r'^([A-Z0-9_]+)=(.*)$', line.strip())
        if m:
            env[m.group(1)] = m.group(2).strip().strip('"')
    return env


class Ctx:
    def __init__(self, env):
        self.es = env["ES_URL"].rstrip("/")
        self.kb = env.get("KIBANA_URL", "").rstrip("/")
        self.env = env
        auth = {"Authorization": f"ApiKey {env['ES_API_KEY']}"}
        self.hes = {**auth, "Content-Type": "application/json"}
        self.hkb = {**auth, "Content-Type": "application/json", "kbn-xsrf": "true", "x-elastic-internal-origin": "kibana"}


def show(label, r):
    ok = "OK  " if r.ok else "FAIL"
    print(f"  [{ok}] {label}: {r.status_code}" + ("" if r.ok else f"  {r.text[:300]}"))
    return r.ok


def check(c):
    r = requests.get(c.es + "/", headers=c.hes, timeout=30)
    if show("cluster", r):
        v = r.json().get("version", {})
        print("        build_flavor:", v.get("build_flavor"), "| number:", v.get("number"))
    r = requests.get(c.es + "/_inference/_all", headers=c.hes, timeout=30)
    if show("inference endpoints", r):
        ids = [e.get("inference_id") for e in r.json().get("endpoints", [])]
        print("        jina embeddings present:", any("jina-embeddings" in (i or "") for i in ids), "| total:", len(ids))
    if c.kb:
        r = requests.get(c.kb + "/api/agent_builder/agents", headers=c.hkb, timeout=30)
        show("Kibana agent builder API", r)
        r = requests.get(c.kb + "/api/workflows/search", headers=c.hkb, timeout=30)  # best-effort probe
        print("        workflows API probe:", r.status_code)
    else:
        print("  KIBANA_URL missing in env file: Kibana steps will be skipped")


def azure(c):
    ep = c.env.get("AZURE_OPENAI_ENDPOINT", ""); key = c.env.get("AZURE_OPENAI_API_KEY", "")
    dep = c.env.get("AZURE_OPENAI_DEPLOYMENT", "gpt-5-4-mini"); ver = c.env.get("AZURE_OPENAI_API_VERSION", "2024-10-21")
    resource = (urlparse(ep).hostname or "").split(".")[0]
    if not (resource and key):
        sys.exit("AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_API_KEY missing in the env file")
    body = {"service": "azureopenai", "service_settings": {"api_key": key, "resource_name": resource, "deployment_id": dep, "api_version": ver}}
    r = requests.put(f"{c.es}/_inference/chat_completion/{AZ_ENDPOINT_ID}", headers=c.hes, json=body, timeout=60)
    show(f"inference endpoint {AZ_ENDPOINT_ID} ({resource}/{dep})", r)


def agents(c):
    if not c.kb:
        sys.exit("KIBANA_URL missing")
    for f in sorted(EXPORT.glob("tool.*.json")):
        t = json.loads(f.read_text())
        r = requests.post(c.kb + "/api/agent_builder/tools", headers=c.hkb, json=t, timeout=60)
        if r.status_code == 409:
            body = {k: v for k, v in t.items() if k in ("description", "tags", "configuration")}
            r = requests.put(f"{c.kb}/api/agent_builder/tools/{t['id']}", headers=c.hkb, json=body, timeout=60)
        show(f"tool {t['id']}", r)
    for f in sorted(EXPORT.glob("agent.*.json")):
        a = json.loads(f.read_text())
        r = requests.post(c.kb + "/api/agent_builder/agents", headers=c.hkb, json=a, timeout=60)
        if r.status_code == 409:
            r = requests.put(f"{c.kb}/api/agent_builder/agents/{a['id']}", headers=c.hkb, json={k: a[k] for k in ("name", "description", "configuration")}, timeout=60)
        show(f"agent {a['id']}", r)


def workflows(c):
    if not c.kb:
        sys.exit("KIBANA_URL missing")
    for name in ["supplier-intelligence-sources", "apex-targeted-kis"]:
        y = (EXPORT / f"workflow.{name}.yaml").read_text()
        v = requests.post(c.kb + "/api/workflows/validate", headers=c.hkb, json={"yaml": y}, timeout=60)
        show(f"validate {name}", v)
        # create (unverified endpoint shapes: report what the server says)
        r = requests.put(f"{c.kb}/api/workflows/workflow/{name}", headers=c.hkb, json={"yaml": y}, timeout=60)
        if r.status_code in (404, 405):
            r = requests.post(c.kb + "/api/workflows/workflow", headers=c.hkb, json={"yaml": y, "id": name}, timeout=60)
        show(f"save {name}", r)
    print("  Next: attach them to the AI index in the UI (Context -> apex-supplier-intelligence -> Automations), then run them.")


def dashboards(c):
    """Agents dashboard (Agent Builder traces live in THIS project: traces-agent_builder.otel-*)."""
    for f in sorted((ROOT / "observability" / "dashboards").glob("*SEARCH-project*.ndjson")):
        h = {k: v for k, v in c.hkb.items() if k != "Content-Type"}
        r = requests.post(c.kb + "/api/saved_objects/_import?overwrite=true", headers={**h, "Elastic-Api-Version": "2023-10-31"}, files={"file": (f.name, f.read_bytes())}, timeout=120)
        show(f"import {f.name}", r)


STEPS = {"check": check, "azure": azure, "agents": agents, "workflows": workflows, "dashboards": dashboards}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", required=True, help="env file for the NEW project (ES_URL, ES_API_KEY, KIBANA_URL, ...)")
    ap.add_argument("step", choices=[*STEPS, "all"])
    a = ap.parse_args()
    ctx = Ctx(load_env(a.env))
    for name in (["check", "azure", "agents", "workflows", "dashboards"] if a.step == "all" else [a.step]):
        print(f"== {name}")
        STEPS[name](ctx)
