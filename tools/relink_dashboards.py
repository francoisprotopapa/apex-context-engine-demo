#!/usr/bin/env python3
"""
Put the same navigation bar (a Links panel) at the top of the four Observability dashboards of the demo, so that clicking never lands on the
managed (old) copies. Each link keeps the target's own time range (useCurrentDateRange=false): billing needs days, logs need minutes.

  python3 tools/relink_dashboards.py --env demo/.env.obs [--star]

--star tries to mark the four dashboards as favourites (stars). Favourites are per user, so it only works if the key maps to a user;
otherwise click the star on each dashboard (the script says so).
"""
import argparse, json, sys, uuid
from pathlib import Path
import requests
sys.path.insert(0, str(Path(__file__).resolve().parent))
from provision_obs import load_env, Obs  # noqa: E402

NAV = [  # (dashboard id, label), in the order of the talk
    ("101a42e7-d4d9-4fbe-be53-97c68d0ad3f4", "1 Scoreboard"),
    ("d0141eb1-ad85-4e17-a62d-0fcb293b80e3", "2 Azure OpenAI: usage and cost"),
    ("ed16be31-500e-4c96-8f6d-2ec90b9e1c3e", "3 Foundry overview"),
    ("cf85d9af-d98b-5052-a2b2-5e9e9668b961", "4 Azure billing"),
]
PANEL = "7a1e0000-0000-4000-8000-00000000nav1"
NAVH = 2


def relink(c, dash_id):
    r = requests.get(f"{c.k}/api/saved_objects/dashboard/{dash_id}", headers=c.h, timeout=60); r.raise_for_status()
    o = r.json(); a = o["attributes"]; refs = o.get("references", [])
    panels = json.loads(a["panelsJSON"])
    old = {p["panelIndex"] for p in panels if p.get("type") == "links"}
    panels = [p for p in panels if p.get("type") != "links"]
    refs = [x for x in refs if not (x["type"] == "dashboard" and x["name"].split(":")[0] in old)]
    for p in panels:
        p["gridData"]["y"] += NAVH
    pid = str(uuid.uuid5(uuid.NAMESPACE_URL, "apex-nav-" + dash_id))
    links = []
    for i, (tid, label) in enumerate(NAV):
        ref = f"link_{tid}_dashboard"
        links.append({"destinationRefName": ref, "id": tid, "label": label, "order": i, "type": "dashboardLink",
                      "options": {"openInNewTab": False, "useCurrentDateRange": False, "useCurrentFilters": False}})
        refs.append({"id": tid, "name": f"{pid}:{ref}", "type": "dashboard"})
    panels.insert(0, {"type": "links", "panelIndex": pid, "gridData": {"x": 0, "y": 0, "w": 48, "h": NAVH, "i": pid},
                      "embeddableConfig": {"enhancements": {}, "layout": "horizontal", "links": links}})
    a["panelsJSON"] = json.dumps(panels)
    r = requests.put(f"{c.k}/api/saved_objects/dashboard/{dash_id}", headers=c.h, json={"attributes": a, "references": refs}, timeout=60)
    print(f"  {a['title'][:70]:70s} {r.status_code}")
    r.raise_for_status()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--env", required=True); ap.add_argument("--star", action="store_true")
    a = ap.parse_args(); c = Obs(load_env(a.env))
    for tid, _ in NAV:
        relink(c, tid)
    if a.star:
        for tid, label in NAV:
            r = requests.post(f"{c.k}/internal/content_management/favorites/dashboard/{tid}/favorite", headers=c.h, timeout=30)
            print("  star", label, r.status_code, r.text[:120])
