"""
Apex Conglomerate — Context Engine extension: the "story bible".

Everything the demo relies on is defined here once, so data, golden questions
and docs stay consistent. Regenerate all derived files with:
    python3 tools/build_dataset.py
"""

SEED = 2026

# Real public figures in the original dataset are replaced with fictional names.
CUSTOMER_RENAMES = {
    "CUST-000000": ("Lena Brandt", "lena.brandt"),
    "CUST-000001": ("Tomás Ferreira", "tomas.ferreira"),
    "CUST-000002": ("Ingrid Solberg", "ingrid.solberg"),
    "CUST-000003": ("Matteo Valli", "matteo.valli"),
    "CUST-000004": ("Aiko Tanaka", "aiko.tanaka"),
}

# ---------------------------------------------------------------------------
# Suppliers. SUPP-000001..010 already exist in transactions, telemetry, batches
# and the knowledge graph; SUPP-000011..024 are new.
# NOTE: there is deliberately NO parent/holding field. Ownership must be
# inferred from apex_corporate_news (that's the Context Engine "RELATE" moment).
# ---------------------------------------------------------------------------
SUPPLIERS = [
    # id, legal_name, short, country, category, business_unit, criticality, spend_2025_eur, risk
    ("SUPP-000001", "Nordbyte Systems GmbH", "Nordbyte", "DE", "IT_services", "ApexTech", "high", 7_900_000, 0.44),
    ("SUPP-000002", "Rheinchem Pharma Services GmbH", "Rheinchem", "DE", "pharma", "ApexPharm", "critical", 18_400_000, 0.50),
    ("SUPP-000003", "Calloway Payment Solutions Ltd", "Calloway", "GB", "financial", "ApexPay", "high", 6_200_000, 0.31),
    ("SUPP-000004", "Mistral Clearing Services SAS", "Mistral Clearing", "FR", "financial", "ApexPay", "medium", 2_100_000, 0.12),
    ("SUPP-000005", "Ostra FinOps Sp. z o.o.", "Ostra FinOps", "PL", "financial", "ApexPay", "medium", 3_400_000, 0.64),
    ("SUPP-000006", "Telvio Network Engineering SpA", "Telvio", "IT", "IT_services", "ApexConnect", "high", 9_800_000, 0.78),
    ("SUPP-000007", "GlobeShield Reinsurance Brokers AG", "GlobeShield", "CH", "financial", "ApexShield", "high", 5_600_000, 0.57),
    ("SUPP-000008", "Brightwater Collections Ltd", "Brightwater", "IE", "financial", "ApexPay", "medium", 1_900_000, 0.65),
    ("SUPP-000009", "Kairos Cloud Integration B.V.", "Kairos Cloud", "NL", "IT_services", "ApexTech", "medium", 4_300_000, 0.59),
    ("SUPP-000010", "Kestrel Cold Chain S.r.l.", "Kestrel", "IT", "pharma_logistics", "ApexPharm", "critical", 9_600_000, 0.65),
    ("SUPP-000011", "Aurelis Excipients S.A.", "Aurelis", "ES", "pharma", "ApexPharm", "critical", 14_200_000, 0.28),
    ("SUPP-000012", "Bergmann Glas & Verpackung GmbH", "Bergmann", "DE", "pharma_packaging", "ApexPharm", "critical", 11_800_000, 0.22),
    ("SUPP-000013", "Nordvik API Manufacturing AS", "Nordvik", "NO", "pharma", "ApexPharm", "critical", 21_500_000, 0.35),
    ("SUPP-000014", "Lumen Analytics Lab Kft.", "Lumen Analytics", "HU", "pharma_testing", "ApexPharm", "critical", 4_100_000, 0.41),
    ("SUPP-000015", "Sorell Sterile Fill Ltd", "Sorell", "IE", "pharma", "ApexPharm", "critical", 12_900_000, 0.30),
    ("SUPP-000016", "Halden Biologics B.V.", "Halden", "NL", "pharma", "ApexPharm", "critical", 6_300_000, 0.38),
    ("SUPP-000017", "Veltran Logistik GmbH", "Veltran", "DE", "logistics", "ApexIndustrial", "medium", 3_700_000, 0.33),
    ("SUPP-000018", "Cassini Industrial Parts S.p.A.", "Cassini", "IT", "industrial_parts", "ApexIndustrial", "high", 8_800_000, 0.40),
    ("SUPP-000019", "Rotterwerk Antriebstechnik GmbH", "Rotterwerk", "DE", "industrial_parts", "ApexIndustrial", "high", 7_200_000, 0.36),
    ("SUPP-000020", "Petrov Lubricants OÜ", "Petrov", "EE", "industrial_parts", "ApexIndustrial", "medium", 1_600_000, 0.52),
    ("SUPP-000021", "Alba Data Centre Services Ltd", "Alba DC", "GB", "IT_services", "ApexCloud", "high", 10_400_000, 0.27),
    ("SUPP-000022", "Fjordline Telecom Hardware AS", "Fjordline", "NO", "telecom_hardware", "ApexConnect", "high", 9_100_000, 0.31),
    ("SUPP-000023", "Quintal Facility Services SL", "Quintal", "ES", "facility", "ApexIndustrial", "low", 900_000, 0.18),
    ("SUPP-000024", "Marlowe Clinical Couriers Ltd", "Marlowe", "GB", "pharma_logistics", "ApexPharm", "high", 2_700_000, 0.26),
]

# The hidden group. Never stated in a single document.
HOLDING = "Veltrano Holding S.A."          # Luxembourg
INTERMEDIATE = "Orvia Life Sciences B.V."  # Netherlands, 100% owned by Veltrano
GROUP_MEMBERS = {
    "SUPP-000002": "via Orvia Life Sciences (acquired 2025-03-18, news DE)",
    "SUPP-000014": "via Orvia Life Sciences (registry extract 2025-05-06)",
    "SUPP-000010": "directly (acquired 2025-09-22, news IT)",
}
# Decoy: similar name, unrelated company (vector-search trap).
DECOY = "Veltran Logistik GmbH (SUPP-000017) — unrelated to Veltrano Holding"


def apexpharm_critical():
    return [s for s in SUPPLIERS if s[5] == "ApexPharm" and s[6] == "critical"]


def group_share():
    crit = apexpharm_critical()
    total = sum(s[7] for s in crit)
    grp = sum(s[7] for s in crit if s[0] in GROUP_MEMBERS)
    return grp, total, grp / total


# Policy thresholds (the "stale vs current" trap).
TPRM_V1 = {"doc_id": "POL-TPRM-EN-001", "version": "1.0", "effective": "2024-01-01", "threshold_pct": 40}
TPRM_V2 = {"doc_id": "POL-TPRM-EN-002", "version": "2.0", "effective": "2026-02-01", "threshold_pct": 30}

# Contract codes (the near-duplicate trap for pure vector search).
KEY_CONTRACTS = {
    "APX-MSA-2024-0117": "SUPP-000002",  # Rheinchem — HAS change-of-control termination (clause 14.3, 60 days)
    "APX-MSA-2024-0171": "SUPP-000016",  # Halden — decoy, no change-of-control clause
    "APX-SLA-2023-0042": "SUPP-000010",  # Kestrel — no CoC clause; ownership disclosure duty 9.4 (30 days); breach -> 15.2
    "APX-MSA-2023-0089": "SUPP-000014",  # Lumen — CoC requires Apex prior written consent (clause 12.6)
    "APX-SOW-2025-0311": "SUPP-000014",  # Lumen SOW under APX-MSA-2023-0089
    "APX-SOW-2025-0313": "SUPP-000015",  # Sorell — decoy near-duplicate SOW code
}

# Part codes (near-duplicates for tickets).
PART_CODES = {
    "RCX-4410-A": "Mechanical seal kit, pump_unit (Cassini)",
    "RCX-4410-B": "Mechanical seal kit, heat_exchanger (Cassini) — NOT interchangeable with -A",
    "RTW-2207-M": "Drive bearing assembly, factory_motor (Rotterwerk)",
    "RTW-2207-N": "Drive bearing assembly, compressor (Rotterwerk)",
    "PLB-0930-S": "Synthetic gear lubricant ISO VG 320 (Petrov)",
    "PLB-0930-H": "Hydraulic oil ISO VG 46 (Petrov)",
}
