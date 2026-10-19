#!/usr/bin/env python3
"""
Provision the OBSERVABILITY Serverless project (LLM observability layer).

  python3 tools/provision_obs.py --env demo/.env.obs check
  python3 tools/provision_obs.py --env demo/.env.obs --azure-env demo/.env.azure-monitor integrations
  python3 tools/provision_obs.py --env demo/.env.obs dashboards
  python3 tools/provision_obs.py --env demo/.env.obs alert

--env        file with OBS_KIBANA_URL and OBS_API_KEY (a Kibana API key of the Observability project)
--azure-env  file written by azure/setup_monitoring.sh (service principal, Event Hub, storage account)

What it creates
  integrations  Azure AI Foundry (metrics, agentless) + Azure Billing (agentless) + a standard agent policy for the Event Hub logs
                (the logs input is NOT supported agentless: an Elastic Agent must run somewhere, see azure/setup_monitoring.sh)
  dashboards    the dashboards in observability/dashboards/*.ndjson (the Agents one belongs to the SEARCH project: tools/provision.py)
  alert         "[LLM] Prompt too large": ES|QL rule, > 10,000 prompt tokens in one call (naive RAG ~11-15k, engineered < 8k)

Nothing here prints secrets. Idempotent where the API allows it; every call prints its HTTP status.
"""
import argparse, json, re, sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OBS = ROOT / "observability"
FOUNDRY, BILLING = ("azure_ai_foundry", "0.13.0"), ("azure_billing", "1.13.0")   # versions verified on 9.6 serverless, 14 Oct 2026


def load_env(path):
    return {m.group(1): m.group(2).strip().strip('"') for m in (re.match(r"^([A-Z0-9_]+)=(.*)$", l.strip()) for l in Path(path).read_text().splitlines()) if m}


class Obs:
    def __init__(self, env):
        self.k = env["OBS_KIBANA_URL"].rstrip("/")
        self.es = self.k.replace(".kb.", ".es.")
        self.h = {"Authorization": f"ApiKey {env['OBS_API_KEY']}", "kbn-xsrf": "true", "x-elastic-internal-origin": "kibana",
                  "Elastic-Api-Version": "2023-10-31", "Content-Type": "application/json"}


def show(label, r):
    print(f"  [{'OK  ' if r.ok else 'FAIL'}] {label}: {r.status_code}" + ("" if r.ok else f"  {r.text[:300]}"))
    return r.ok


def check(c, _az):
    show("Kibana status", requests.get(c.k + "/api/status", headers=c.h, timeout=30))
    r = requests.get(c.k + "/api/fleet/epm/packages?prerelease=true", headers=c.h, timeout=60)
    if show("Fleet packages", r):
        have = {i["name"]: i["version"] for i in r.json().get("items", [])}
        for n, v in (FOUNDRY, BILLING):
            print(f"        {n}: catalog {have.get(n)} (script pins {v})")


def integrations(c, az):
    if not az:
        sys.exit("--azure-env is required for this step")
    for n, v in (FOUNDRY, BILLING):
        show(f"install package {n} {v}", requests.post(f"{c.k}/api/fleet/epm/packages/{n}/{v}", headers=c.h, json={"force": False}, timeout=300))
    sp = {"client_id": az["AZURE_CLIENT_ID"], "client_secret": az["AZURE_CLIENT_SECRET"], "tenant_id": az["AZURE_TENANT_ID"], "subscription_id": az["AZURE_SUBSCRIPTION_ID"]}
    # 1) Foundry metrics: agentless "managed integration" (the classic package_policies API refuses agentless)
    body = {"name": "azure-ai-foundry-apex-demo", "namespace": "default", "package": {"name": FOUNDRY[0], "version": FOUNDRY[1]},
            "inputs": {"azure_ai_foundry-azure/metrics": {"enabled": True, "streams": {"azure.ai_foundry": {"enabled": True, "vars": {**sp, "resource_groups": [az.get("RESOURCE_GROUP", "rg-apex-demo")], "period": "300s"}}}}}}
    show("managed integration: Foundry metrics (agentless)", requests.post(c.k + "/api/fleet/managed_integrations", headers=c.h, json=body, timeout=180))
    # 2) Billing (agentless): credentials are integration-level vars
    body = {"name": "azure-billing-apex-demo", "namespace": "default", "package": {"name": BILLING[0], "version": BILLING[1]}, "vars": sp,
            "inputs": {"billing-azure/metrics": {"enabled": True, "streams": {"azure.billing": {"enabled": True, "vars": {"period": "24h", "billing_usage_lookback": "24h", "billing_forecast_window": "720h"}}}}}}
    show("managed integration: Billing (agentless)", requests.post(c.k + "/api/fleet/managed_integrations", headers=c.h, json=body, timeout=180))
    # 3) Logs: standard agent policy + package policy (the agentless API leaves azure-eventhub disabled)
    r = requests.post(c.k + "/api/fleet/agent_policies", headers=c.h, json={"name": "azure-logs-collector", "namespace": "default", "monitoring_enabled": ["logs", "metrics"]}, timeout=60)
    if show("agent policy azure-logs-collector", r):
        pid = r.json()["item"]["id"]
        body = {"name": "azure-ai-foundry-logs-aci", "namespace": "default", "policy_ids": [pid], "package": {"name": FOUNDRY[0], "version": FOUNDRY[1]},
                "inputs": {"azure_ai_foundry-azure-eventhub": {"enabled": True, "streams": {"azure_ai_foundry.logs": {"enabled": True, "vars": {
                    "eventhub": az["EVENTHUB_NAME"], "consumer_group": "$Default", "auth_type": "connection_string", "connection_string": az["EVENTHUB_CONNECTION_STRING"],
                    "storage_account": az["STORAGE_ACCOUNT"], "storage_account_key": az["STORAGE_ACCOUNT_KEY"], "storage_account_container": az["STORAGE_CONTAINER"]}}}},
                           "azure_ai_foundry-azure/metrics": {"enabled": False, "streams": {"azure.ai_foundry": {"enabled": False}}}}}
        show("package policy: Foundry logs (Event Hub)", requests.post(c.k + "/api/fleet/package_policies?format=simplified", headers=c.h, json=body, timeout=120))
        t = requests.get(f"{c.k}/api/fleet/enrollment_api_keys?kuery=policy_id:{pid}", headers=c.h, timeout=60).json().get("items", [])
        h = requests.get(c.k + "/api/fleet/fleet_server_hosts", headers=c.h, timeout=60).json().get("items", [])
        if t and h:
            print("  -> start the Elastic Agent (azure/setup_monitoring.sh does it in ACI). Fleet URL:", next((x["host_urls"][0] for x in h if x.get("is_default")), h[0]["host_urls"][0]))
            print("     enrollment token written to ./.enrollment_token (git-ignored); never commit it")
            Path(".enrollment_token").write_text(t[0]["api_key"])


def dashboards(c, _az):
    for f in sorted((OBS / "dashboards").glob("*.ndjson")):
        if "SEARCH-project" in f.name:
            print(f"  [skip] {f.name}: belongs to the SEARCH project (tools/provision.py dashboards)")
            continue
        h = {k: v for k, v in c.h.items() if k != "Content-Type"}
        r = requests.post(c.k + "/api/saved_objects/_import?overwrite=true", headers=h, files={"file": (f.name, f.read_bytes())}, timeout=120)
        ok = show(f"import {f.name}", r)
        if ok and r.json().get("errors"):
            print("        import errors:", json.dumps(r.json()["errors"])[:300])


def alert(c, _az):
    rule = json.loads((OBS / "alert-prompt-too-large.json").read_text())
    existing = requests.get(c.k + "/api/alerting/rules/_find?per_page=100&search=Prompt+too+large", headers=c.h, timeout=60).json().get("data", [])
    for x in existing:
        if x["name"] == rule["name"]:
            requests.delete(f"{c.k}/api/alerting/rule/{x['id']}", headers=c.h, timeout=60); print("  replaced existing rule", x["id"])
    show("alert rule", requests.post(c.k + "/api/alerting/rule", headers=c.h, json=rule, timeout=60))


STEPS = {"check": check, "integrations": integrations, "dashboards": dashboards, "alert": alert}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", required=True)
    ap.add_argument("--azure-env")
    ap.add_argument("step", choices=[*STEPS, "all"])
    a = ap.parse_args()
    c, az = Obs(load_env(a.env)), (load_env(a.azure_env) if a.azure_env else None)
    for name in (["check", "integrations", "dashboards", "alert"] if a.step == "all" else [a.step]):
        print(f"== {name}")
        STEPS[name](c, az)
