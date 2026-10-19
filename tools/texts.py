"""Hand-written key documents (policies, key news). Generated noise lives in build_dataset.py."""

TPRM_V1_CHUNKS = [
"""CHAPTER 1 — PURPOSE AND SCOPE

1.1 Purpose
This Third-Party Risk Management Policy (TPRM) defines how Apex Conglomerate identifies, assesses, monitors and mitigates risks arising from suppliers, service providers and other third parties. It applies to ApexPay, ApexShield, ApexConnect, ApexCloud, ApexTech, ApexIndustrial and ApexPharm.

1.2 Scope
The policy covers all third parties with an annual contract value above EUR 250,000 and all third parties classified as "critical" by a business unit, irrespective of contract value.

1.3 Ownership
The policy is owned by the Chief Procurement Officer. Second-line oversight is provided by Group Risk.""",
"""CHAPTER 2 — RISK CLASSIFICATION

2.1 Criticality
A supplier is "critical" if its failure would interrupt a regulated process (e.g. GMP manufacturing, payment clearing) for more than 72 hours.

2.2 Concentration risk
Business units must monitor concentration risk at supplier level. Where a single supplier accounts for more than 40% of a business unit's critical supplier spend, the business unit must perform Enhanced Due Diligence (EDD) and document an exit plan.

2.3 Group view
Concentration is assessed per legal entity named in the contract. Ownership relationships between suppliers are not considered under this version of the policy.""",
"""CHAPTER 3 — DUE DILIGENCE AND MONITORING

3.1 Onboarding
All in-scope suppliers undergo standard due diligence: sanctions screening, financial health check, information-security questionnaire and, for ApexPharm, a GMP quality agreement.

3.2 Periodic review
Critical suppliers are reviewed every 24 months. Adverse media screening is performed at onboarding only.

3.3 Change of control
Suppliers are encouraged to inform Apex of material ownership changes. No contractual notification deadline is mandated by this policy.""",
"""CHAPTER 4 — ESCALATION

4.1 Escalation path
Material findings are escalated to the business unit's Head of Procurement within 60 days.

4.2 Effective date
This policy (version 1.0) is effective from 1 January 2024.""",
]

TPRM_V2_CHUNKS = [
"""CHAPTER 1 — PURPOSE AND SCOPE (VERSION 2.0)

1.1 Purpose
This Third-Party Risk Management Policy version 2.0 replaces version 1.0 (effective 1 January 2024) in its entirety. It reflects the Group's updated risk appetite following the 2025 supply-chain review and regulatory expectations on operational resilience.

1.2 Scope
The policy covers all third parties with an annual contract value above EUR 150,000 and all third parties classified as "critical", irrespective of contract value. It applies to all business units, including ApexPharm.""",
"""CHAPTER 2 — CONCENTRATION AND GROUP RISK

2.1 Group-level concentration
Concentration risk is now assessed at the level of the ULTIMATE PARENT COMPANY, not the individual legal entity. Suppliers that share a direct or indirect parent must be aggregated.

2.2 Threshold
Where suppliers belonging to the same corporate group together account for more than 30% of a business unit's critical supplier spend, the business unit must perform Enhanced Due Diligence (EDD) within 30 days and present an exit and dual-sourcing plan to Group Risk.

2.3 Data sources
Procurement must use corporate registry extracts, press releases and supplier disclosures to maintain an up-to-date ownership map of all critical suppliers.""",
"""CHAPTER 3 — CHANGE OF CONTROL AND ADVERSE MEDIA

3.1 Notification duty
New and renewed contracts must require suppliers to notify Apex of any change of control within 30 days. Failure to notify is a material breach.

3.2 Continuous adverse media screening
Critical suppliers and their parent companies are screened continuously. A regulatory investigation into a supplier's parent company triggers EDD within 30 days, independently of the concentration threshold.

3.3 Contractual remedies
Where a contract grants a termination right on change of control, the business unit must assess whether to exercise it within the contractual notice window.""",
"""CHAPTER 4 — ESCALATION AND EFFECTIVE DATE

4.1 Escalation path
EDD findings are escalated to Group Risk and the business unit CEO within 15 days.

4.2 Effective date
This policy (version 2.0) is effective from 1 February 2026 and supersedes version 1.0.""",
]

TPRM_V2_DE_CHUNK = """KAPITEL 2 — KONZENTRATIONS- UND KONZERNRISIKO (VERSION 2.0, DEUTSCHE FASSUNG)

2.1 Konzernebene
Das Konzentrationsrisiko wird ab Version 2.0 auf Ebene der obersten Muttergesellschaft bewertet. Lieferanten mit gemeinsamer direkter oder indirekter Muttergesellschaft sind zusammenzufassen.

2.2 Schwellenwert
Übersteigt der Anteil einer Unternehmensgruppe 30 % der Ausgaben eines Geschäftsbereichs für kritische Lieferanten, ist innerhalb von 30 Tagen eine verstärkte Sorgfaltsprüfung (EDD) durchzuführen und Group Risk ein Exit- und Dual-Sourcing-Plan vorzulegen."""

# Key news (the hidden ownership chain + adverse media + decoys).
KEY_NEWS = [
    {"news_id": "NEWS-2024-1112-001", "date": "2024-11-12", "language": "en", "source": "Benelux Business Wire (synthetic)",
     "doc_type": "press_release",
     "title": "Veltrano Holding completes integration of Orvia Life Sciences",
     "text": "LUXEMBOURG — Veltrano Holding S.A. today announced that Orvia Life Sciences B.V. is now a wholly owned subsidiary of the group, following the purchase of the remaining minority stake. Orvia, headquartered in Leiden, will serve as Veltrano's platform for contract services to the pharmaceutical industry and is expected to pursue further acquisitions in quality testing and pharmaceutical services across Central Europe. Veltrano Holding is a privately held investment group with interests in logistics, life sciences and industrial services."},
    {"news_id": "NEWS-2025-0318-004", "date": "2025-03-18", "language": "de", "source": "Rhein-Main Wirtschaftsdienst (synthetic)",
     "doc_type": "press_release",
     "title": "Orvia Life Sciences übernimmt Rheinchem Pharma Services",
     "text": "MANNHEIM — Die niederländische Orvia Life Sciences B.V. hat 100 % der Anteile an der Rheinchem Pharma Services GmbH übernommen. Rheinchem ist ein Lohnhersteller für Wirkstoff-Zwischenprodukte und beliefert mehrere europäische Pharmaunternehmen. Über den Kaufpreis wurde Stillschweigen vereinbart. Die Geschäftsführung von Rheinchem bleibt im Amt; Kunden sollen „ohne Unterbrechung“ weiter beliefert werden."},
    {"news_id": "NEWS-2025-0506-002", "date": "2025-05-06", "language": "en", "source": "Hungarian Company Registry (translated extract)",
     "doc_type": "registry_extract",
     "title": "Registry extract — Lumen Analytics Lab Kft. (Cg. 01-09-387214)",
     "text": "Company name: Lumen Analytics Lab Korlátolt Felelősségű Társaság. Registered seat: Budapest. Main activity: technical testing and analysis (pharmaceutical quality control). Registered capital: HUF 120,000,000. Members: Orvia Life Sciences B.V. (Leiden, Netherlands) — 100% of the capital, registered on 2025-05-06; previous member (deregistered 2025-05-06): Lumen Holding Zrt. Managing director: Dr. Eszter Varga."},
    {"news_id": "NEWS-2025-0922-003", "date": "2025-09-22", "language": "it", "source": "Giornale della Catena del Freddo (synthetic)",
     "doc_type": "news_article",
     "title": "Veltrano Holding acquisisce Kestrel Cold Chain",
     "text": "VERONA — Il gruppo lussemburghese Veltrano Holding S.A. ha rilevato il 100% di Kestrel Cold Chain S.r.l., operatore specializzato nella logistica a temperatura controllata per l'industria farmaceutica. L'operazione rafforza la presenza del gruppo nella catena del freddo in Europa meridionale. Kestrel continuerà a operare con il proprio marchio. Non sono stati resi noti i termini economici."},
    {"news_id": "NEWS-2026-0827-001", "date": "2026-08-27", "language": "en", "source": "Luxembourg Business Daily (synthetic)",
     "doc_type": "news_article",
     "title": "Luxembourg regulator opens review of Veltrano Holding ownership disclosures",
     "text": "The Luxembourg financial regulator has opened a review of beneficial-ownership disclosures filed by Veltrano Holding S.A., according to two people familiar with the matter. The review concerns the structure of several holding vehicles used in recent acquisitions. Veltrano said it was cooperating fully and that the review 'does not affect the operations of its portfolio companies'. The group has been an active acquirer in European pharmaceutical services and cold-chain logistics since 2024."},
    # Decoys
    {"news_id": "NEWS-2026-0311-006", "date": "2026-03-11", "language": "de", "source": "Ruhr Logistik Kurier (synthetic)",
     "doc_type": "news_article",
     "title": "Veltran Logistik eröffnet neues Cross-Dock-Hub in Duisburg",
     "text": "DUISBURG — Die familiengeführte Veltran Logistik GmbH hat ein neues Cross-Dock-Hub mit 22.000 Quadratmetern eröffnet. Das Unternehmen ist seit 1987 im Besitz der Familie Veltran und plant keine externe Beteiligung. Der Standort soll vor allem Kunden aus Maschinenbau und Industrie bedienen."},
    {"news_id": "NEWS-2026-0602-002", "date": "2026-06-02", "language": "en", "source": "BioTech Europe Weekly (synthetic)",
     "doc_type": "news_article",
     "title": "Halden Biologics closes EUR 48m Series C",
     "text": "LEIDEN — Halden Biologics B.V. has raised EUR 48 million in a Series C round led by a consortium of European life-science funds. The company remains independent and will use the proceeds to expand its biologics fill-finish capacity. Halden supplies several mid-sized pharmaceutical groups in the Benelux and Germany."},
]
