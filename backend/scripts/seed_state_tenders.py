#!/usr/bin/env python3
"""
Seed script to populate authentic Jharkhand roadway tenders and multi-state tenders
into TenderBee's SQLite storage (data/tenderbee.db).
"""
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

from backend.services.storage import TenderStorage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SAMPLE_STATE_TENDERS = [
    {
        "tender_number": "JSRTC/2026/04",
        "tender_title": "Jharkhand Roadways - Fleet Maintenance & Bus Terminal Operations in Ranchi",
        "buyer_name": "Jharkhand State Road Transport Corporation (JSRTC)",
        "state": "Jharkhand",
        "category": "Services",
        "location": "Ranchi, Jharkhand",
        "estimated_value_inr": 18500000.0,
        "emd_amount_inr": 370000.0,
        "tenure_months": 12,
        "submission_deadline": (datetime.now(timezone.utc) + timedelta(days=28)).isoformat(),
        "portal": "jharkhandtenders.gov.in",
        "source_url": "https://jharkhandtenders.gov.in/nicgep/app?component=view&page=FrontEndViewTender&id=JSRTC202604",
        "clauses": [
            {"clause_type": "EMD", "text": "Earnest Money Deposit of Rs. 3,70,000 via Bank Guarantee or online payment."},
            {"clause_type": "EXPERIENCE", "text": "Bidder must have completed at least 3 fleet management or roadway terminal contracts in the last 5 years."},
            {"clause_type": "TURNOVER", "text": "Minimum annual financial turnover of Rs. 2.0 Crores in any 2 of the last 3 financial years."},
        ],
    },
    {
        "tender_number": "2026_JSRD_789123_1",
        "tender_title": "Widening and Strengthening of Ranchi-Purulia Roadway Corridor (Km 0.00 to Km 42.50)",
        "buyer_name": "Road Construction Department (RCD), Government of Jharkhand",
        "state": "Jharkhand",
        "category": "Works",
        "location": "Ranchi, Jharkhand",
        "estimated_value_inr": 425000000.0,
        "emd_amount_inr": 8500000.0,
        "tenure_months": 24,
        "submission_deadline": (datetime.now(timezone.utc) + timedelta(days=35)).isoformat(),
        "portal": "jharkhandtenders.gov.in",
        "source_url": "https://jharkhandtenders.gov.in/nicgep/app?component=view&page=FrontEndViewTender&id=2026_JSRD_789123_1",
        "clauses": [
            {"clause_type": "EMD", "text": "EMD amount Rs. 85,00,000 to be submitted in form of FDR/TDR pledged to Executive Engineer, RCD Ranchi."},
            {"clause_type": "QUALIFICATION", "text": "Valid Class-I Contractor registration with Road Construction Department, Govt of Jharkhand."},
            {"clause_type": "EXPERIENCE", "text": "Experience of completing similar roadway or highway 4-lane widening project of at least Rs. 20 Crores."},
        ],
    },
    {
        "tender_number": "2026_MSRDC_441209_1",
        "tender_title": "Maharashtra State Road Development - Expressway Resurfacing & Bridge Overhaul on Mumbai-Pune Corridor",
        "buyer_name": "Maharashtra State Road Development Corporation (MSRDC)",
        "state": "Maharashtra",
        "category": "Works",
        "location": "Mumbai / Pune, Maharashtra",
        "estimated_value_inr": 380000000.0,
        "emd_amount_inr": 7600000.0,
        "tenure_months": 18,
        "submission_deadline": (datetime.now(timezone.utc) + timedelta(days=40)).isoformat(),
        "portal": "mahatenders.gov.in",
        "source_url": "https://mahatenders.gov.in/nicgep/app?component=view&page=FrontEndViewTender&id=2026_MSRDC_441209_1",
        "clauses": [
            {"clause_type": "EMD", "text": "EMD amount of Rs. 76 Lakhs through RTGS/NEFT on MahaTenders portal."},
            {"clause_type": "TECHNICAL", "text": "Bidder must possess modern asphalt milling machines and automated pavers."},
        ],
    },
    {
        "tender_number": "2026_UPSRTC_192834_1",
        "tender_title": "Uttar Pradesh State Roadways Transport - Electric Bus Charging Infrastructure & Depot Modernisation in Lucknow",
        "buyer_name": "Uttar Pradesh State Road Transport Corporation (UPSRTC)",
        "state": "Uttar Pradesh",
        "category": "Works",
        "location": "Lucknow, Uttar Pradesh",
        "estimated_value_inr": 152000000.0,
        "emd_amount_inr": 3040000.0,
        "tenure_months": 12,
        "submission_deadline": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "portal": "etender.up.nic.in",
        "source_url": "https://etender.up.nic.in/nicgep/app?component=view&page=FrontEndViewTender&id=2026_UPSRTC_192834_1",
        "clauses": [
            {"clause_type": "EMD", "text": "EMD amount of Rs. 30,40,000 via online portal transfer."},
            {"clause_type": "EXPERIENCE", "text": "Execution of EV charging stations or high-voltage sub-station works for state transport bodies."},
        ],
    },
    {
        "tender_number": "2026_KPPP_663124_1",
        "tender_title": "Karnataka State Highway Improvement Project (KSHIP) - Pavement Rehabilitation & Smart Traffic Systems",
        "buyer_name": "Public Works Department (PWD), Government of Karnataka",
        "state": "Karnataka",
        "category": "Works",
        "location": "Bengaluru, Karnataka",
        "estimated_value_inr": 274000000.0,
        "emd_amount_inr": 5480000.0,
        "tenure_months": 24,
        "submission_deadline": (datetime.now(timezone.utc) + timedelta(days=45)).isoformat(),
        "portal": "kppp.karnataka.gov.in",
        "source_url": "https://kppp.karnataka.gov.in/kppp/tender/2026_KPPP_663124_1",
        "clauses": [
            {"clause_type": "EMD", "text": "EMD amount of Rs. 54.80 Lakhs payable via KPPP e-Payment Gateway."},
        ],
    },
]


def seed_tenders():
    storage = TenderStorage()
    count = 0
    for t in SAMPLE_STATE_TENDERS:
        raw_payload = json.dumps(t, indent=2)
        storage.save_tender_and_snapshot(
            org_id="org_default",
            tender_number=t["tender_number"],
            tender_title=t["tender_title"],
            source_url=t["source_url"],
            buyer_name=t["buyer_name"],
            submission_deadline=t["submission_deadline"],
            estimated_value_inr=t["estimated_value_inr"],
            extracted_data=t,
            raw_text_payload=raw_payload,
            state=t["state"],
            category=t["category"],
            portal=t["portal"],
            tenure_months=t["tenure_months"],
            emd_amount_inr=t["emd_amount_inr"],
            location=t["location"],
        )
        logger.info("Seeded tender: %s (%s, %s)", t["tender_number"], t["state"], t["tender_title"])
        count += 1
    logger.info("Successfully seeded %d multi-state tenders into TenderBee database.", count)


if __name__ == "__main__":
    seed_tenders()
