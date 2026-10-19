#!/usr/bin/env python3
"""
Build the Apex Conglomerate — Context Engine edition dataset.

- Fixes the original core/extra_mile files (fictional names, supplier labels)
- Adds the Third-Party Risk Management policy (v1 2024 + v2 2026)
- Generates the new indices in data/context_engine/
- Writes eval/golden_questions.jsonl

Deterministic: same seed, same output. Run from the repo root:
    python3 tools/build_dataset.py
"""
import json, random, re, datetime as dt
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from world import *          # noqa
from texts import *          # noqa

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
R = random.Random(SEED)


def read_bulk(path):
    out, action = [], None
    for line in open(path, encoding="utf-8"):
        if not line.strip():
            continue
        d = json.loads(line)
        if list(d.keys()) == ["index"]:
            action = d["index"]
            continue
        out.append((action, d))
        action = None
    return out


def write_bulk(path, index, docs, id_field):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps({"index": {"_index": index, "_id": d[id_field]}}, ensure_ascii=False) + "\n")
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    print(f"  wrote {len(docs):5d} docs -> {path.relative_to(ROOT)}")


def rewrite_bulk(path, pairs):
    with open(path, "w", encoding="utf-8") as f:
        for action, d in pairs:
            if action is not None:
                f.write(json.dumps({"index": action}, ensure_ascii=False) + "\n")
            f.write(json.dumps(d, ensure_ascii=False) + "\n")


SUP = {s[0]: s for s in SUPPLIERS}

# ---------------------------------------------------------------- 1. fixes
def fix_original():
    p = DATA / "core/apex_customer_360.ndjson"
    pairs = read_bulk(p)
    for _, d in pairs:
        if d["customer_id"] in CUSTOMER_RENAMES:
            name, mail = CUSTOMER_RENAMES[d["customer_id"]]
            d["name"] = name
            d["email"] = f"{mail}.{int(d['customer_id'][-1])}@apexcorp.com"
    rewrite_bulk(p, pairs)
    print("  fixed customer names in apex_customer_360")

    p = DATA / "extra_mile/apex_knowledge_graph.ndjson"
    pairs = read_bulk(p)
    for _, d in pairs:
        if d.get("node_type") == "Supplier" and d["node_id"] in SUP:
            d["label"] = SUP[d["node_id"]][1]
    rewrite_bulk(p, pairs)
    print("  relabelled suppliers in apex_knowledge_graph")


# ---------------------------------------------------------------- 2. policies
def add_policies():
    p = DATA / "extra_mile/apex_policy_vault.ndjson"
    pairs = [x for x in read_bulk(p) if not x[1]["doc_id"].startswith("POL-TPRM")]

    def chunks(meta, texts, lang, title):
        out = []
        for i, t in enumerate(texts):
            out.append({
                "chunk_id": f"{meta['doc_id']}-{lang.upper()}-CHUNK-{i:03d}",
                "doc_id": meta["doc_id"], "doc_type": "internal_policy",
                "doc_title": title, "language": lang, "topic": "third_party_risk",
                "classification": "INTERNAL", "effective_date": meta["effective"],
                "policy_version": meta["version"], "policy_owner": "Chief Procurement Officer",
                "chunk_index": i, "total_chunks": len(texts), "text": t,
                "word_count": len(t.split()), "char_count": len(t),
                "chunking_strategy": "chapter", "overlap_tokens": 0,
                "@timestamp": meta["effective"] + "T00:00:00Z",
            })
        return out

    new = chunks(TPRM_V1, TPRM_V1_CHUNKS, "en", "Apex Conglomerate — Third-Party Risk Management Policy v1.0")
    new += chunks(TPRM_V2, TPRM_V2_CHUNKS, "en", "Apex Conglomerate — Third-Party Risk Management Policy v2.0")
    new += chunks(TPRM_V2, [TPRM_V2_DE_CHUNK], "de", "Apex Conglomerate — Richtlinie Drittparteienrisiko v2.0 (Auszug)")
    for d in new:
        pairs.append(({"_index": "apex_policy_vault", "_id": d["chunk_id"]}, d))
    rewrite_bulk(p, pairs)
    print(f"  added {len(new)} TPRM policy chunks to apex_policy_vault")


# ---------------------------------------------------------------- 3. suppliers
def build_suppliers():
    contracts_by_sup = {}
    for c, s in KEY_CONTRACTS.items():
        contracts_by_sup.setdefault(s, []).append(c)
    docs = []
    for sid, legal, short, cc, cat, bu, crit, spend, risk in SUPPLIERS:
        desc = (f"{legal} is a {crit} {cat.replace('_', ' ')} supplier to {bu}, based in {cc}. "
                f"Annual spend 2025: EUR {spend:,.0f}. Ultimate parent company: not disclosed in supplier master data.")
        docs.append({
            "supplier_id": sid, "legal_name": legal, "short_name": short, "country": cc,
            "category": cat, "business_unit": bu, "criticality": crit,
            "annual_spend_eur_2025": spend, "risk_score": risk,
            "contract_ids": contracts_by_sup.get(sid, []),
            "onboarding_date": f"{R.choice([2018, 2019, 2020, 2021, 2022, 2023])}-{R.randint(1, 12):02d}-{R.randint(1, 28):02d}",
            "last_review_date": f"2025-{R.randint(1, 12):02d}-{R.randint(1, 28):02d}",
            "parent_company_disclosed": False,
            "description": desc,
            "@timestamp": "2026-01-01T00:00:00Z",
        })
    write_bulk(DATA / "context_engine/apex_suppliers.ndjson", "apex_suppliers", docs, "supplier_id")
    return docs


# ---------------------------------------------------------------- 4. news
COMPANIES_NOISE = ["Aurelis Excipients", "Bergmann Glas & Verpackung", "Nordvik API Manufacturing", "Sorell Sterile Fill",
                   "Cassini Industrial Parts", "Rotterwerk Antriebstechnik", "Alba Data Centre Services", "Fjordline Telecom Hardware",
                   "Telvio Network Engineering", "Nordbyte Systems", "Kairos Cloud Integration", "Marlowe Clinical Couriers",
                   "ApexPharm", "ApexConnect", "ApexPay", "ApexIndustrial"]
NOISE_TEMPL = [
    ("en", "{c} opens new site in {city}", "{c} has opened a new site in {city}, adding around {n} jobs. The company said the investment supports growing demand from customers in {sector} and will be fully operational by {q}."),
    ("en", "{c} appoints new Chief Operating Officer", "{c} has appointed {person} as Chief Operating Officer, effective {q}. {person} previously held leadership roles in {sector} and will focus on operational resilience and supplier quality."),
    ("en", "{c} reports {pct}% revenue growth", "{c} reported revenue growth of {pct}% for the last financial year, driven by {sector} contracts. Management expects margins to remain stable despite higher energy and logistics costs."),
    ("de", "{c} erweitert Kapazitäten in {city}", "{c} investiert in neue Kapazitäten am Standort {city}. Rund {n} neue Arbeitsplätze sollen entstehen. Hintergrund ist die steigende Nachfrage aus dem Bereich {sector}."),
    ("de", "{c} erhält Zertifizierung nach ISO 27001", "{c} hat die Zertifizierung nach ISO/IEC 27001 erhalten. Das Unternehmen sieht darin einen wichtigen Schritt für Kunden aus regulierten Branchen wie {sector}."),
    ("it", "{c} firma accordo pluriennale nel settore {sector}", "{c} ha firmato un accordo pluriennale con un importante cliente del settore {sector}. L'accordo prevede investimenti in automazione e la creazione di circa {n} posti di lavoro a {city}."),
    ("fr", "{c} inaugure un centre logistique à {city}", "{c} a inauguré un nouveau centre à {city}. L'entreprise prévoit {n} recrutements et souhaite renforcer sa présence auprès des clients du secteur {sector}."),
    ("en", "{c} completes GMP inspection without critical findings", "{c} announced that a regulatory GMP inspection at its {city} facility was completed without critical findings. Minor observations related to documentation will be closed by {q}."),
]
CITIES = ["Hamburg", "Lyon", "Bilbao", "Bergen", "Cork", "Turin", "Leipzig", "Gdansk", "Utrecht", "Graz", "Porto", "Brno"]
SECTORS = ["pharmaceuticals", "telecommunications", "industrial automation", "payments", "cloud services", "logistics"]
PEOPLE = ["Dr. Anja Keller", "Marco Bellini", "Sophie Laurent", "Jonas Berg", "Elena Moretti", "Lukas Novak", "Clara Ruiz"]


def build_news():
    docs = []
    for k in KEY_NEWS:
        d = dict(k); d["key_document"] = True
        blob = k["title"] + " " + k["text"]
        d["companies_mentioned"] = [c for c in [HOLDING, INTERMEDIATE] + [s[1] for s in SUPPLIERS]
                                    if re.search(r"\b" + re.escape(c.split(" ")[0]) + r"\b", blob)]
        d["@timestamp"] = k["date"] + "T08:00:00Z"
        docs.append(d)
    start = dt.date(2024, 1, 10)
    for i in range(88):
        lang, tt, tx = R.choice(NOISE_TEMPL)
        c = R.choice(COMPANIES_NOISE)
        day = start + dt.timedelta(days=R.randint(0, 990))
        f = dict(c=c, city=R.choice(CITIES), n=R.choice([40, 60, 85, 120, 150, 210]), sector=R.choice(SECTORS),
                 q=R.choice(["Q1", "Q2", "Q3", "Q4"]) + f" {day.year + 1}", person=R.choice(PEOPLE), pct=R.choice([4, 6, 9, 12, 15]))
        docs.append({
            "news_id": f"NEWS-{day:%Y-%m%d}-{100 + i}", "date": day.isoformat(), "language": lang,
            "source": R.choice(["Europe Industry Brief (synthetic)", "Supply Chain Monitor (synthetic)", "PharmaTech Daily (synthetic)", "Wirtschaft Kompakt (synthetic)"]),
            "doc_type": "news_article", "title": tt.format(**f), "text": tx.format(**f),
            "companies_mentioned": [c], "key_document": False, "@timestamp": day.isoformat() + "T08:00:00Z",
        })
    docs.sort(key=lambda d: d["date"])
    write_bulk(DATA / "context_engine/apex_corporate_news.ndjson", "apex_corporate_news", docs, "news_id")
    return docs


# ---------------------------------------------------------------- 5. contracts
def para(*options):
    return R.choice(options)


BOILER = {
 "definitions": lambda s: "\n".join([
   f"1.{i+1} \"{t}\" means {d}" for i, (t, d) in enumerate(R.sample([
     ("Affiliate", "any entity that directly or indirectly controls, is controlled by, or is under common control with a party."),
     ("Business Day", "any day other than a Saturday, Sunday or public holiday in the place of performance."),
     ("Confidential Information", "all non-public information disclosed by one party to the other, in any form, including technical, commercial and regulatory data."),
     ("Deliverables", "all goods, materials, reports and results provided by the Supplier under this Agreement or any Statement of Work."),
     ("Good Manufacturing Practice", "the principles and guidelines laid down in EU Directive 2003/94/EC and EudraLex Volume 4, as amended."),
     ("Key Performance Indicators", "the measurable service levels set out in Schedule 2."),
     ("Personal Data", "personal data as defined in Regulation (EU) 2016/679 (GDPR)."),
     ("Quality Agreement", "the separate agreement defining the GMP responsibilities of each party."),
     ("Services", "the services described in the applicable Statement of Work."),
     ("Statement of Work", "a document agreed in writing describing specific Services, Deliverables, timelines and fees."),
     ("Term", "the period described in the clause headed Term and Termination."),
     ("Control", "the ownership of more than 50% of the voting rights or the power to direct the management of an entity."),
   ], 9))]),
 "scope": lambda s: " ".join([para(
   f"The Supplier shall provide the Services to {s[5]} and its Affiliates in accordance with this Agreement, each Statement of Work and all applicable laws.",
   f"This Agreement governs the supply of Services and Deliverables by {s[1]} to Apex Conglomerate and its Affiliates.",
 ), para(
   "The Supplier shall perform the Services with the skill, care and diligence expected of a leading provider in the pharmaceutical industry.",
   "Services shall be performed by appropriately qualified and trained personnel, whose qualification records shall be made available upon request.",
 ), para(
   "Any change to the scope of the Services shall be agreed through the change control procedure described in Schedule 4.",
   "No Statement of Work shall take effect until signed by authorised representatives of both parties.",
 )] * 3),
 "pricing": lambda s: (f"{para('Fees are set out in Schedule 3 and are fixed for the first twelve months.', 'All prices are stated in EUR and exclude VAT.')} "
   f"Invoices are payable within {R.choice([30, 45, 60])} days of receipt. Price adjustments after the first contract year shall not exceed the "
   f"Eurostat HICP index for the euro area plus {R.choice([0.5, 1.0, 1.5])} percentage points. "
   "Late payment interest shall accrue at the statutory rate. The Supplier shall provide a monthly consumption report itemising volumes, unit prices and credits. "
   "Disputed invoice items shall be notified within 20 Business Days and the undisputed portion shall be paid when due. ") * 2,
 "service_levels": lambda s: "\n".join([
   f"{k}: target {v}." for k, v in R.sample([
     ("On-time delivery", "98.5% of orders per calendar month"), ("Batch documentation completeness", "100%"),
     ("Deviation notification", "within 24 hours of detection"), ("Temperature excursion reporting", "within 2 hours"),
     ("Certificate of Analysis turnaround", "5 Business Days"), ("Incident response (critical)", "4 hours"),
     ("Corrective and preventive action closure", "60 days"), ("Change notification", "90 days before implementation"),
   ], 6)]) + "\n" + ("Service credits of 2% of the monthly fees apply for each KPI missed in two consecutive months, capped at 15% of the monthly fees. "
   "Persistent failure (three or more KPIs missed in any quarter) constitutes a material breach. ") * 2,
 "quality": lambda s: ("The parties shall comply with the Quality Agreement, which prevails over this Agreement in respect of GMP matters. "
   "The Supplier shall maintain a pharmaceutical quality system, notify ApexPharm of any regulatory inspection within 2 Business Days, "
   "and shall not change materials, processes, equipment or manufacturing sites without prior written approval. "
   "Batch records shall be retained for at least one year after the expiry date of the batch and in any case not less than five years. ") * 3,
 "confidentiality": lambda s: ("Each party shall keep the other party's Confidential Information strictly confidential, use it only for the purposes of this Agreement, "
   "and disclose it only to employees and advisers who need to know it and are bound by equivalent obligations. These obligations survive termination for "
   f"{R.choice([5, 7, 10])} years. ") * 3,
 "data_protection": lambda s: ("Where the Supplier processes Personal Data on behalf of Apex, the parties shall enter into a data processing agreement compliant with Article 28 GDPR. "
   "The Supplier shall not transfer Personal Data outside the European Economic Area without prior written consent and appropriate safeguards. "
   "Personal data breaches shall be notified to Apex without undue delay and in any event within 24 hours. ") * 2,
 "audit": lambda s, extra="": (f"9.1 Apex, its auditors and regulators may audit the Supplier's facilities, records and systems relevant to the Services upon {R.choice([10, 15, 30])} Business Days' notice, "
   "and without notice in case of a suspected critical quality or compliance issue.\n"
   "9.2 The Supplier shall ensure equivalent audit rights towards its subcontractors.\n"
   "9.3 The Supplier shall remedy audit findings in accordance with an agreed corrective action plan." + extra),
 "liability": lambda s: (f"Each party's aggregate liability under this Agreement shall not exceed {R.choice([100, 150, 200])}% of the fees paid or payable in the twelve months preceding the claim. "
   "This limitation shall not apply to breaches of confidentiality, data protection obligations, wilful misconduct, gross negligence, or liability for death or personal injury. "
   "Neither party shall be liable for indirect or consequential loss. The Supplier shall maintain product liability insurance of at least EUR 10 million per occurrence. ") * 2,
 "force_majeure": lambda s: ("Neither party shall be liable for delay or failure caused by events beyond its reasonable control, provided it notifies the other party promptly and uses reasonable efforts to mitigate. "
   "If a force majeure event continues for more than 90 days, either party may terminate the affected Statement of Work by written notice. "
   "Supply shortages of the Supplier's own vendors do not constitute force majeure unless caused by a force majeure event. "),
 "law": lambda s: f"This Agreement is governed by the laws of {R.choice(['Germany', 'Switzerland', 'the Netherlands', 'Ireland'])}. The courts of {R.choice(['Frankfurt am Main', 'Zurich', 'Amsterdam', 'Dublin'])} have exclusive jurisdiction, without prejudice to interim relief.",
}


def termination_clause(kind, s):
    base = (f"15.1 This Agreement commences on the Effective Date and continues for an initial term of {R.choice([3, 4, 5])} years, renewing automatically for successive periods of 12 months "
            "unless either party gives notice of non-renewal at least 6 months before the end of the then-current term.\n")
    if kind == "coc_termination":
        return base + ("15.2 Either party may terminate this Agreement with immediate effect if the other party commits a material breach that is not remedied within 30 days of written notice.\n"
                       "15.3 Apex may terminate this Agreement for convenience on 120 days' written notice.\n")
    if kind == "breach_only_180":
        return base + ("15.2 Either party may terminate this Agreement if the other party commits a material breach that is not remedied within 30 days of written notice. "
                       "For the avoidance of doubt, a breach of clause 9.4 (Disclosure of ownership changes) constitutes a material breach.\n"
                       "15.3 Apex may terminate this Agreement for convenience on 180 days' written notice.\n")
    return base + (f"15.2 Either party may terminate this Agreement for material breach not remedied within 30 days of written notice.\n"
                   f"15.3 Apex may terminate this Agreement for convenience on {R.choice([90, 120, 180])} days' written notice.\n")


def build_contracts():
    docs = []

    def make(cid, sid, ctype, signed, title_extra="", special=None, length=1, parent=None):
        s = SUP[sid]
        special = special or {}
        sec = []
        sec.append(("1. DEFINITIONS", BOILER["definitions"](s)))
        sec.append(("2. SCOPE OF SERVICES", BOILER["scope"](s)))
        sec.append(("3. FEES AND PAYMENT", BOILER["pricing"](s)))
        sec.append(("4. SERVICE LEVELS", BOILER["service_levels"](s)))
        if s[4].startswith("pharma"):
            sec.append(("5. QUALITY AND GMP", BOILER["quality"](s)))
        sec.append(("6. CONFIDENTIALITY", BOILER["confidentiality"](s)))
        sec.append(("7. DATA PROTECTION", BOILER["data_protection"](s)))
        sec.append(("9. AUDIT AND INSPECTION", BOILER["audit"](s, special.get("audit_extra", ""))))
        sec.append(("10. LIABILITY AND INSURANCE", BOILER["liability"](s)))
        sec.append(("11. FORCE MAJEURE", BOILER["force_majeure"](s)))
        if "assignment" in special:
            sec.append(("12. ASSIGNMENT AND CHANGE OF CONTROL", special["assignment"]))
        else:
            sec.append(("12. ASSIGNMENT", "Neither party may assign this Agreement without the prior written consent of the other party, not to be unreasonably withheld, except to an Affiliate."))
        if "coc" in special:
            sec.append(("14. CHANGE OF CONTROL", special["coc"]))
        sec.append(("15. TERM AND TERMINATION", termination_clause(special.get("termination", "standard"), s)))
        sec.append(("16. GOVERNING LAW AND JURISDICTION", BOILER["law"](s)))
        # schedules for length
        for k in range(length):
            sec.append((f"SCHEDULE {k + 2}", BOILER["service_levels"](s) + "\n" + BOILER["pricing"](s)))
        body = "\n\n".join(f"{h}\n{t}" for h, t in sec)
        header = (f"{ {'MSA': 'MASTER SERVICES AGREEMENT', 'SLA': 'SERVICE LEVEL AGREEMENT', 'SOW': 'STATEMENT OF WORK', 'NDA': 'MUTUAL NON-DISCLOSURE AGREEMENT', 'DPA': 'DATA PROCESSING AGREEMENT'}[ctype] }\n"
                  f"Contract No. {cid}{title_extra}\nBetween Apex Conglomerate (acting for {s[5]}) and {s[1]} (\"Supplier\")\nSigned on {signed}\n"
                  + (f"This Statement of Work is issued under Master Services Agreement {parent}.\n" if parent else ""))
        content = header + "\n" + body
        docs.append({
            "contract_id": cid, "contract_type": ctype, "supplier_id": sid, "supplier_name": s[1],
            "business_unit": s[5], "signed_date": signed, "parent_contract_id": parent,
            "title": f"{ctype} {cid} — {s[1]}", "language": "en",
            "has_change_of_control_clause": "coc" in special or "assignment" in special,
            "content": content, "char_count": len(content), "word_count": len(content.split()),
            "classification": "CONFIDENTIAL", "@timestamp": signed + "T00:00:00Z",
        })

    # --- key contracts (long, so the naive prompt hurts)
    make("APX-MSA-2024-0117", "SUPP-000002", "MSA", "2024-11-04", length=12, special={
        "coc": "14.1 The Supplier shall notify Apex in writing of any Change of Control within 30 days of its occurrence.\n"
               "14.2 \"Change of Control\" means any event by which a person or group of persons acting in concert acquires Control of the Supplier or of any entity that Controls the Supplier.\n"
               "14.3 Following a Change of Control, Apex may terminate this Agreement, in whole or in part, by giving not less than 60 days' written notice, provided such notice is given within 12 months of Apex becoming aware of the Change of Control. No termination fee shall be payable.\n"
               "14.4 During the notice period the Supplier shall continue to perform the Services and shall cooperate in the orderly transfer of the Services to Apex or a replacement supplier.",
        "termination": "coc_termination"})
    make("APX-MSA-2024-0171", "SUPP-000016", "MSA", "2024-07-15", length=11, special={"termination": "standard"})
    make("APX-SLA-2023-0042", "SUPP-000010", "SLA", "2023-05-02", length=11, special={
        "audit_extra": "\n9.4 Disclosure of ownership changes. The Supplier shall disclose to Apex any change in its direct or indirect shareholders holding more than 25% of its capital within 30 days of such change, including the identity of the ultimate parent company.",
        "termination": "breach_only_180"})
    make("APX-MSA-2023-0089", "SUPP-000014", "MSA", "2023-09-19", length=10, special={
        "assignment": "12.1 Neither party may assign this Agreement without the prior written consent of the other party.\n"
                      "12.6 Any Change of Control of the Supplier requires the prior written consent of Apex. If the Supplier undergoes a Change of Control without such consent, Apex may terminate this Agreement and any Statement of Work with immediate effect by written notice.",
        "termination": "standard"})
    make("APX-SOW-2025-0311", "SUPP-000014", "SOW", "2025-02-03", parent="APX-MSA-2023-0089", length=2)
    make("APX-SOW-2025-0313", "SUPP-000015", "SOW", "2025-02-05", parent="APX-MSA-2022-0045", length=2)

    # --- volume contracts across all suppliers
    used = set(KEY_CONTRACTS)
    types = ["MSA", "SLA", "SOW", "NDA", "DPA"]
    while len(docs) < 72:
        sid = R.choice([s[0] for s in SUPPLIERS])
        ctype = R.choice(types)
        year = R.choice([2021, 2022, 2023, 2024, 2025, 2026])
        cid = f"APX-{ctype}-{year}-{R.randint(10, 400):04d}"
        if cid in used:
            continue
        used.add(cid)
        signed = f"{year}-{R.randint(1, 12):02d}-{R.randint(1, 28):02d}"
        make(cid, sid, ctype, signed, length=R.randint(0, 4), special={"termination": "standard"})
    write_bulk(DATA / "context_engine/apex_contracts.ndjson", "apex_contracts", docs, "contract_id")
    return docs


# ---------------------------------------------------------------- 6. service tickets
def build_tickets():
    tel = [d for _, d in read_bulk(DATA / "core/apex_operational_telemetry.ndjson")]
    anomalies = [d for d in tel if d.get("is_anomaly_reading")]
    R.shuffle(anomalies)
    parts_for = {"pump_unit": "RCX-4410-A", "heat_exchanger": "RCX-4410-B", "factory_motor": "RTW-2207-M",
                 "compressor": "RTW-2207-N", "conveyor_belt": "PLB-0930-S", "hvac_unit": "PLB-0930-H"}
    tmpl_en = ["Anomaly on {a} ({t}) at {loc}: {fm} suspected. Vibration {v} mm/s, temperature {temp} °C. Replaced part {p}. Root cause: {rc}.",
               "Preventive work order for {a} at {loc}. Predicted failure mode {fm}. Ordered spare {p} from {sup}. Technician notes: {rc}.",
               "Unplanned stop of {a} ({t}). Operator reported noise and heat. Part {p} installed; asset returned to service after {h} hours. {rc}."]
    tmpl_de = ["Störung an {a} ({t}) in {loc}: Verdacht auf {fm}. Vibration {v} mm/s, Temperatur {temp} °C. Ersatzteil {p} getauscht. Ursache: {rc}.",
               "Wartungsauftrag für {a} in {loc}. Prognostizierter Ausfallmodus {fm}. Ersatzteil {p} bei {sup} bestellt. Hinweis: {rc}."]
    rcs = ["seal wear due to dry running", "lubricant degradation after extended interval", "bearing misalignment after last overhaul",
           "wrong seal kit installed (RCX-4410-B instead of RCX-4410-A)", "contaminated oil batch", "loose coupling", "sensor drift, no mechanical fault"]
    sup_for = {"RCX": "Cassini Industrial Parts S.p.A.", "RTW": "Rotterwerk Antriebstechnik GmbH", "PLB": "Petrov Lubricants OÜ"}
    docs = []
    for i, d in enumerate(anomalies[:560]):
        p = parts_for.get(d["asset_type"], R.choice(list(PART_CODES)))
        lang = "de" if R.random() < 0.3 else "en"
        tx = R.choice(tmpl_de if lang == "de" else tmpl_en).format(
            a=d["asset_id"], t=d["asset_type"], loc=d["location"], fm=d.get("predicted_failure_mode", "unknown"),
            v=round(d.get("vibration_mm_s", 0), 1), temp=round(d.get("temperature_celsius", 0), 1), p=p,
            sup=sup_for[p[:3]], rc=R.choice(rcs), h=R.randint(2, 30))
        docs.append({"ticket_id": f"INC-{2026}{i:05d}", "source_system": "ServiceNow", "category": "maintenance",
                     "asset_id": d["asset_id"], "asset_type": d["asset_type"], "location": d["location"],
                     "related_reading_id": d["reading_id"], "part_code": p, "supplier_name": sup_for[p[:3]],
                     "priority": R.choice(["P2", "P3", "P3", "P4"]), "status": R.choice(["closed", "closed", "resolved", "open"]),
                     "language": lang, "text": tx, "@timestamp": d["@timestamp"]})
    # Kestrel cold-chain excursions after the (undisclosed) acquisition
    for j in range(14):
        day = dt.date(2025, 10, 1) + dt.timedelta(days=R.randint(0, 330))
        dur = R.randint(25, 190)
        docs.append({"ticket_id": f"QA-{day:%Y%m%d}-{j:03d}", "source_system": "ApexPharm QMS", "category": "temperature_excursion",
                     "asset_id": None, "asset_type": "cold_chain_shipment", "location": R.choice(["Plant-Basel-1", "Facility-Milan-QA2", "Facility-Lyon-QA3"]),
                     "related_reading_id": None, "part_code": None, "supplier_name": "Kestrel Cold Chain S.r.l.",
                     "priority": "P2", "status": R.choice(["closed", "open"]), "language": "en",
                     "text": f"Temperature excursion during inbound shipment KCC-{day:%Y}-{R.randint(100, 999)} (carrier: Kestrel Cold Chain). "
                             f"Logger recorded {R.choice([9.1, 10.4, 11.8, 12.6])} °C for {dur} minutes (limit 2–8 °C). Batch quarantined pending QA assessment.",
                     "@timestamp": day.isoformat() + "T10:00:00Z"})
    # Spare-parts catalogue entries (no random draws -> the rest of the dataset stays byte-identical).
    # They are the only place where the part codes are described; Q05 depends on them.
    catalogue = [
        ("CAT-RCX-4410-A-DE", "de", "RCX-4410-A", "pump_unit",
         "Ersatzteilkatalog: RCX-4410-A — Gleitringdichtung (Kit) für Pumpen (Asset-Typ pump_unit), Hersteller Cassini Industrial Parts S.p.A. "
         "Nicht austauschbar mit RCX-4410-B, das für Wärmetauscher vorgesehen ist."),
        ("CAT-RCX-4410-B-DE", "de", "RCX-4410-B", "heat_exchanger",
         "Ersatzteilkatalog: RCX-4410-B — Gleitringdichtung (Kit) für Wärmetauscher (Asset-Typ heat_exchanger), Hersteller Cassini Industrial Parts S.p.A. "
         "Nicht austauschbar mit RCX-4410-A, das für Pumpen vorgesehen ist."),
        ("CAT-RCX-4410-A-EN", "en", "RCX-4410-A", "pump_unit",
         "Spare parts catalogue: RCX-4410-A — mechanical seal kit for pumps (asset type pump_unit), manufacturer Cassini Industrial Parts S.p.A. "
         "Not interchangeable with RCX-4410-B, which is for heat exchangers."),
        ("CAT-RCX-4410-B-EN", "en", "RCX-4410-B", "heat_exchanger",
         "Spare parts catalogue: RCX-4410-B — mechanical seal kit for heat exchangers (asset type heat_exchanger), manufacturer Cassini Industrial Parts S.p.A. "
         "Not interchangeable with RCX-4410-A, which is for pumps."),
    ]
    for cid, lang, code, atype, text in catalogue:
        docs.append({"ticket_id": cid, "source_system": "SAP PM spare parts catalogue", "category": "spare_parts_catalogue",
                     "asset_id": None, "asset_type": atype, "location": None, "related_reading_id": None, "part_code": code,
                     "supplier_name": "Cassini Industrial Parts S.p.A.", "priority": None, "status": "active", "language": lang,
                     "text": text, "@timestamp": "2025-01-01T00:00:00Z"})
    write_bulk(DATA / "context_engine/apex_service_tickets.ndjson", "apex_service_tickets", docs, "ticket_id")
    return docs


# ---------------------------------------------------------------- 7. golden questions
def build_golden():
    grp, total, share = group_share()
    Q = [
     # Act 1 — wrong context (exact identifiers, decoys, stale policy)
     ("Q01", "act1", "Can we terminate contract APX-MSA-2024-0117 if the supplier changes owner?",
      "Yes. APX-MSA-2024-0117 (Rheinchem Pharma Services) clause 14.3 allows Apex to terminate on 60 days' written notice within 12 months of becoming aware of a change of control, with no termination fee.",
      ["APX-MSA-2024-0117"], "near-duplicate code APX-MSA-2024-0171 (Halden) has no such clause"),
     ("Q02", "act1", "What is the termination for convenience notice period in APX-MSA-2024-0171?",
      "APX-MSA-2024-0171 is the Halden Biologics MSA; it has no change-of-control clause and only standard termination (material breach or convenience notice per clause 15.3).",
      ["APX-MSA-2024-0171"], "vector search tends to return APX-MSA-2024-0117"),
     ("Q03", "act1", "What is the current concentration threshold that triggers enhanced due diligence for supplier groups?",
      f"30% of a business unit's critical supplier spend, assessed at ultimate parent level (TPRM policy v2.0, effective 2026-02-01). The 40% per-entity threshold of v1.0 is superseded.",
      ["POL-TPRM-EN-002"], "v1.0 (40%) is a stale-policy trap"),
     ("Q04", "act1", "Who owns Veltran Logistik?",
      "Veltran Logistik GmbH is family-owned (Veltran family since 1987) and is unrelated to Veltrano Holding.",
      ["NEWS-2026-0311-006"], "name similarity with Veltrano Holding"),
     ("Q05", "act1", "Welche Ersatzteilnummer ist für die Gleitringdichtung der Pumpen vorgesehen?",
      "RCX-4410-A (mechanical seal kit for pump_unit). RCX-4410-B is for heat exchangers and is not interchangeable.",
      ["CAT-RCX-4410-A-DE", "CAT-RCX-4410-A-EN"], "near-duplicate part codes (-A pumps / -B heat exchangers), German query"),
     # Act 2 — too much context (long contracts)
     ("Q06", "act2", "Summarise the change-of-control obligations in the Rheinchem master services agreement.",
      "Supplier must notify within 30 days (14.1); Apex may terminate on not less than 60 days' notice within 12 months of awareness, no fee (14.3); supplier must cooperate on transfer (14.4).",
      ["APX-MSA-2024-0117"], "naive prompt sends whole 40k-char contract"),
     ("Q07", "act2", "Does Kestrel Cold Chain have to tell us about new shareholders, and what happens if it doesn't?",
      "Yes: clause 9.4 of APX-SLA-2023-0042 requires disclosure of shareholder changes above 25% within 30 days incl. ultimate parent; breach of 9.4 is a material breach (15.2), terminable if not remedied within 30 days.",
      ["APX-SLA-2023-0042"], ""),
     ("Q08", "act2", "Can Lumen Analytics change owner without our approval?",
      "No. Clause 12.6 of APX-MSA-2023-0089 requires Apex's prior written consent; otherwise Apex may terminate the MSA and any SOW (e.g. APX-SOW-2025-0311) with immediate effect.",
      ["APX-MSA-2023-0089"], ""),
     # Context Engine — relate / map / precompute
     ("Q09", "context_engine", "Which of our ApexPharm suppliers belong to the same corporate group?",
      "Rheinchem Pharma Services (via Orvia, acquired 2025-03-18), Lumen Analytics Lab (via Orvia, registry 2025-05-06) and Kestrel Cold Chain (directly, 2025-09-22) all belong to Veltrano Holding S.A.; Orvia is 100% owned by Veltrano since 2024-11-12.",
      ["NEWS-2024-1112-001", "NEWS-2025-0318-004", "NEWS-2025-0506-002", "NEWS-2025-0922-003"], "requires joining 4 documents in 3 languages"),
     ("Q10", "context_engine", "What share of ApexPharm critical supplier spend sits with a single corporate group?",
      f"Veltrano Holding group: EUR {grp:,.0f} of EUR {total:,.0f} = {share*100:.1f}%.",
      ["apex_suppliers", "NEWS-2024-1112-001", "NEWS-2025-0318-004", "NEWS-2025-0506-002", "NEWS-2025-0922-003"], ""),
     ("HERO", "context_engine", "Which of our suppliers could expose ApexPharm to compliance risk, and what do our contracts let us do about it?",
      f"Veltrano Holding controls Rheinchem, Lumen Analytics and Kestrel ({share*100:.1f}% of ApexPharm critical spend > 30% threshold of TPRM v2.0 → EDD within 30 days). Veltrano is under review by the Luxembourg regulator (2026-08-27) → EDD trigger by itself (3.2). Contracts: Rheinchem APX-MSA-2024-0117 cl.14.3 termination on 60 days' notice; Lumen APX-MSA-2023-0089 cl.12.6 consent required, immediate termination possible; Kestrel APX-SLA-2023-0042 cl.9.4 disclosure duty, breach = material (15.2), plus repeated temperature excursions since Oct 2025.",
      ["POL-TPRM-EN-002", "APX-MSA-2024-0117", "APX-MSA-2023-0089", "APX-SLA-2023-0042", "NEWS-2026-0827-001"], "the demo's guiding question"),
     ("Q11", "context_engine", "Has Kestrel Cold Chain had quality incidents recently?",
      "Yes, 14 temperature excursions on inbound shipments recorded in the ApexPharm QMS between Oct 2025 and Aug 2026 (limit 2–8 °C).",
      ["apex_service_tickets"], ""),
     ("Q12", "context_engine", "Which indices should I query to answer a question about supplier ownership?",
      "apex_corporate_news (press releases, registry extracts) joined with apex_suppliers (master data, spend) — supplier master data does not disclose parent companies.",
      ["apex_suppliers", "apex_corporate_news"], "semantic-metadata KI"),
    ]
    out = ROOT / "eval/golden_questions.jsonl"
    out.parent.mkdir(exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for qid, act, q, a, src, note in Q:
            f.write(json.dumps({"id": qid, "act": act, "question": q, "expected_answer": a, "sources": src, "trap": note}, ensure_ascii=False) + "\n")
    print(f"  wrote {len(Q)} golden questions -> eval/golden_questions.jsonl  (group share {share*100:.1f}%)")


if __name__ == "__main__":
    print("Building Apex Conglomerate — Context Engine edition")
    fix_original()
    add_policies()
    build_suppliers()
    build_news()
    c = build_contracts()
    print(f"  contracts: avg {sum(d['char_count'] for d in c)//len(c):,} chars, max {max(d['char_count'] for d in c):,}")
    build_tickets()
    build_golden()
    print("done.")
