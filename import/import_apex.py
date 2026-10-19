#!/usr/bin/env python3
"""
Apex Conglomerate — Context Engine edition · import for Elastic Cloud Serverless
================================================================================
Usage:
    cp config.example.py config.py      # fill in ES_URL + ES_API_KEY
    pip install -r requirements.txt
    python3 import_apex.py              # create missing indices + import
    python3 import_apex.py --recreate   # drop and recreate every index first
    python3 import_apex.py --only apex_contracts apex_corporate_news
    python3 import_apex.py --with-multimodal

Works with plain REST calls (requests), so there is no client-version coupling.
Serverless notes: no shard/replica settings are sent; semantic_text embeddings are
computed at ingest by the inference endpoint configured in config.py.
"""
import argparse, json, sys, time
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("Missing dependency: pip install -r requirements.txt")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / "data"

def _load_config():
    """config.py by default; `--config path/to/config_new.py` (or APEX_CONFIG) targets another cluster."""
    import importlib.util, os
    path = os.environ.get("APEX_CONFIG")
    if "--config" in sys.argv:
        i = sys.argv.index("--config"); path = sys.argv[i + 1]; del sys.argv[i:i + 2]
    path = Path(path).expanduser() if path else HERE / "config.py"
    if not path.exists():
        sys.exit(f"{path} not found — copy config.example.py to config.py and fill it in.")
    spec = importlib.util.spec_from_file_location("apex_config", path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


config = _load_config()

ES_URL = config.ES_URL.rstrip("/")
H = {"Authorization": f"ApiKey {config.ES_API_KEY}", "Content-Type": "application/json"}
TEXT_INF = getattr(config, "TEXT_INFERENCE_ID", ".jina-embeddings-v5-text-small")
MM_INF = getattr(config, "MULTIMODAL_INFERENCE_ID", None) or TEXT_INF

# file -> order of import (dependencies don't matter, but small/key indices first is nicer for demos)
FILES = [
    "context_engine/apex_suppliers.ndjson",
    "context_engine/apex_corporate_news.ndjson",
    "context_engine/apex_contracts.ndjson",
    "context_engine/apex_service_tickets.ndjson",
    "extra_mile/apex_policy_vault.ndjson",
    "extra_mile/apex_unstructured_vault.ndjson",
    "extra_mile/apex_technical_docs.ndjson",
    "extra_mile/apex_it_knowledge_base.ndjson",
    "extra_mile/apex_knowledge_graph.ndjson",
    "extra_mile/apex_security_acls.ndjson",
    "core/apex_customer_360.ndjson",
    "core/apex_customer_interactions.ndjson",
    "core/apex_financial_transactions.ndjson",
    "core/apex_operational_telemetry.ndjson",
    "core/apex_pharma_batches.ndjson",
]
MM_FILES = ["multimodal/apex_multimodal_assets.ndjson", "multimodal/apex_technical_diagrams.ndjson",
            "multimodal/apex_it_diagrams.ndjson"]


def call(method, path, body=None, data=None, ok=(200, 201), retries=6):
    for attempt in range(retries):
        r = requests.request(method, ES_URL + path, headers=H if data is None else {**H, "Content-Type": "application/x-ndjson"},
                             json=body, data=data, timeout=300)
        if r.status_code in (429, 502, 503, 504):
            wait = 2 ** attempt
            print(f"    {r.status_code} — retrying in {wait}s", flush=True)
            time.sleep(wait)
            continue
        return r
    return r


def check_cluster():
    r = call("GET", "/")
    if r.status_code != 200:
        sys.exit(f"Cannot reach cluster ({r.status_code}): {r.text[:300]}")
    info = r.json()
    flavor = info.get("version", {}).get("build_flavor", "?")
    print(f"Connected to {info.get('name', '?')} · build_flavor={flavor}")
    if flavor != "serverless":
        print("  ! Not a Serverless project. Context Engine needs Serverless or Stack 9.6+ with an Enterprise license.")


def check_inference(inf_id):
    r = call("GET", f"/_inference/{inf_id}")
    if r.status_code == 200:
        print(f"Inference endpoint OK: {inf_id}")
        return
    print(f"Inference endpoint '{inf_id}' not found ({r.status_code}). Available embedding endpoints:")
    r = call("GET", "/_inference/_all")
    if r.status_code == 200:
        for e in r.json().get("endpoints", []):
            if e.get("task_type") in ("text_embedding", "sparse_embedding", "embedding"):
                print(f"   - {e['inference_id']}  ({e['task_type']}, {e.get('service')})")
    sys.exit("Set TEXT_INFERENCE_ID in config.py to one of the endpoints above and re-run.")


def load_mappings():
    raw = (HERE / "mappings.json").read_text(encoding="utf-8")
    raw = raw.replace("{{TEXT_INFERENCE_ID}}", TEXT_INF).replace("{{MULTIMODAL_INFERENCE_ID}}", MM_INF)
    m = json.loads(raw)
    m.pop("_note", None)
    return m


def ensure_index(name, mappings, recreate):
    exists = call("HEAD", f"/{name}").status_code == 200
    if exists and recreate:
        call("DELETE", f"/{name}")
        exists = False
        print(f"  dropped {name}")
    if not exists:
        body = mappings.get(name, {"mappings": {"dynamic": True}})
        r = call("PUT", f"/{name}", body=body)
        if r.status_code not in (200, 201):
            sys.exit(f"  could not create {name}: {r.text[:500]}")
        print(f"  created {name}")


def read_pairs(path):
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    pairs, i = [], 0
    while i < len(lines):
        a = json.loads(lines[i])
        if list(a.keys()) == ["index"]:
            pairs.append((lines[i], lines[i + 1]))
            i += 2
        else:
            raise ValueError(f"{path}: expected bulk action line at {i + 1}")
    return pairs


def bulk(path, mappings_semantic):
    pairs = read_pairs(path)
    index = json.loads(pairs[0][0])["index"]["_index"]
    batch = 15 if index in mappings_semantic else 500
    ok = err = 0
    first_err = None
    t0 = time.time()
    for i in range(0, len(pairs), batch):
        chunk = pairs[i:i + batch]
        payload = "\n".join(f"{a}\n{d}" for a, d in chunk) + "\n"
        r = call("POST", "/_bulk", data=payload.encode("utf-8"))
        if r.status_code != 200:
            err += len(chunk); first_err = first_err or r.text[:300]
            continue
        res = r.json()
        for it in res.get("items", []):
            st = it["index"]
            if st.get("status", 500) < 300:
                ok += 1
            else:
                err += 1; first_err = first_err or json.dumps(st.get("error"))[:300]
        print(f"\r  {index:32s} {ok:6d} ok  {err:4d} errors", end="", flush=True)
    print(f"   ({time.time() - t0:.0f}s)")
    if first_err:
        print(f"    first error: {first_err}")
    return index, ok, err


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recreate", action="store_true", help="drop and recreate indices before import")
    ap.add_argument("--only", nargs="*", help="only these index names")
    ap.add_argument("--with-multimodal", action="store_true", help="also import multimodal assets (optional for this use case)")
    args = ap.parse_args()

    check_cluster()
    check_inference(TEXT_INF)
    mappings = load_mappings()
    semantic = {k for k, v in mappings.items() if "semantic_text" in json.dumps(v)}

    files = FILES + (MM_FILES if args.with_multimodal else [])
    plan = []
    for f in files:
        p = DATA / f
        idx = json.loads(p.open(encoding="utf-8").readline())["index"]["_index"]
        if args.only and idx not in args.only:
            continue
        plan.append((idx, p))

    print("\nIndices")
    done = set()
    for idx, _ in plan:
        if idx not in done:
            ensure_index(idx, mappings, args.recreate)
            done.add(idx)

    print("\nImport (semantic indices are slower: embeddings are computed at ingest)")
    summary = {}
    for idx, p in plan:
        _, ok, err = bulk(p, semantic)
        s = summary.setdefault(idx, [0, 0]); s[0] += ok; s[1] += err

    call("POST", "/" + ",".join(summary) + "/_refresh")
    print("\nSummary")
    for idx, (ok, err) in summary.items():
        r = call("GET", f"/{idx}/_count")
        cnt = r.json().get("count", "?") if r.status_code == 200 else "?"
        print(f"  {idx:32s} imported {ok:6d}  errors {err:4d}  count {cnt}")
    print("\nNext: context_engine/SETUP.md  ·  agents/SETUP.md  ·  observability/README.md")


if __name__ == "__main__":
    main()
