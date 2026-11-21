"""
Tender Intake & Rule-Pack Drafting Service.
Coordinates PDF extraction, web scraping, tiered storage persistence, and translating
tender clauses into versioned, human-confirmable RulePack objects.
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.services.scraper import UniversalTenderScraper
from backend.services.storage import TenderStorage
from backend.services.tinyfish import BidEasyScraper
from backend.engine.parser import TenderPDFExtractor
from backend.engine.schema import (
    DocumentType,
    ReferenceDates,
    Rule,
    RulePack,
    RuleSource,
    RuleStatus,
    RuleType,
    TenderPDFExtractionResult,
)


class TenderService:
    def __init__(
        self,
        scraper: Optional[Any] = None,
        storage: Optional[TenderStorage] = None,
        pdf_extractor: Optional[TenderPDFExtractor] = None,
    ):
        self.storage = storage or TenderStorage()
        self.scraper = scraper or UniversalTenderScraper(storage=self.storage)
        self.pdf_extractor = pdf_extractor or TenderPDFExtractor()

    def intake_tender(
        self,
        identifier: str,
        org_id: str = "org_default",
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """
        Main web intake workflow:
        1. Ingests tender from URL or Tender Number via TinyFish / Cache.
        2. Automatically drafts an executable RulePack from extracted criteria.
        3. Persists draft RulePack into storage.
        4. Returns tender details and draft rules for human review.
        """
        scrape_result = self.scraper.fetch_tender(
            identifier=identifier, org_id=org_id, force_refresh=force_refresh
        )
        if not scrape_result.get("success"):
            return scrape_result

        tender_data = scrape_result["tender"]
        tender_number = tender_data.get("tender_number", "UNKNOWN")
        tender_id = f"tnd_{self.storage.compute_sha256(tender_number)[:12]}"

        # Parse submission deadline
        deadline_str = tender_data.get("submission_deadline")
        try:
            deadline = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
        except Exception:
            deadline = datetime.now(timezone.utc)

        # Build proposed Rule list
        rules: List[Rule] = self._draft_rules_from_tender(tender_data)

        # Construct RulePack in DRAFT status
        rule_pack_dict = {
            "tender_id": tender_id,
            "version": 1,
            "status": RuleStatus.DRAFT.value,
            "rules": [r.model_dump() for r in rules],
        }
        rule_pack_hash = self.storage.compute_sha256(json.dumps(rule_pack_dict, sort_keys=True))
        rule_pack_id = f"rp_{rule_pack_hash[:16]}"

        rule_pack = RulePack(
            tender_id=tender_id,
            version=1,
            status=RuleStatus.DRAFT,
            content_hash=rule_pack_hash,
            reference_dates=ReferenceDates(submission_deadline=deadline),
            rules=rules,
        )

        # Persist RulePack in database
        self._save_rule_pack_to_db(rule_pack_id, rule_pack)

        return {
            "success": True,
            "is_cached": scrape_result.get("is_cached", False),
            "tender_id": tender_id,
            "tender_number": tender_number,
            "tender_title": tender_data.get("tender_title"),
            "buyer_name": tender_data.get("buyer_name"),
            "submission_deadline": deadline.isoformat(),
            "estimated_value_inr": tender_data.get("estimated_value_inr"),
            "emd_amount_inr": tender_data.get("emd_amount_inr"),
            "tender_fee_inr": tender_data.get("tender_fee_inr"),
            "processing_fee_inr": tender_data.get("processing_fee_inr"),
            "dealing_officer": tender_data.get("dealing_officer"),
            "org_hierarchy": tender_data.get("org_hierarchy") or [],
            "mandatory_documents": tender_data.get("mandatory_documents") or [],
            "attachments": tender_data.get("attachments") or [],
            "nit_attachment": tender_data.get("nit_attachment"),
            "boq_attachment": tender_data.get("boq_attachment"),
            "rule_pack_id": rule_pack_id,
            "rule_pack": rule_pack.model_dump(),
            "extraction": tender_data,
            "json_schema": TenderPDFExtractionResult.get_json_schema(),
        }

    def intake_tender_pdf(
        self,
        pdf_path: str,
        org_id: str = "org_default",
        tender_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Production Tender PDF Intake:
        Extracts structured procurement parameters, eligibility clauses, and exact
        verbatim quotes with 1-indexed page citations, emitting a validated JSON schema output.
        """
        extraction: TenderPDFExtractionResult = self.pdf_extractor.extract_from_pdf(pdf_path)

        t_num = extraction.tender_number or f"TND-{self.storage.compute_sha256(str(pdf_path))[:8].upper()}"
        t_title = extraction.tender_title
        b_name = extraction.buyer_name or "Procuring Authority"
        deadline_str = extraction.submission_deadline or datetime.now(timezone.utc).isoformat()

        # If tender already exists in storage (e.g. ingested from portal search / eye button),
        # preserve verified title, buyer name, cost, EMD, and document checklist
        existing_tender = self.storage.get_tender(tender_id) if tender_id else None
        if not existing_tender and t_num:
            existing_tender = self.storage.get_tender(t_num)

        if existing_tender:
            if not extraction.tender_number:
                t_num = existing_tender.get("tender_number") or t_num
            if extraction.tender_title in ("Procurement Tender Notice", None, ""):
                t_title = existing_tender.get("title") or t_title
            if not extraction.buyer_name or len(extraction.buyer_name) < 6 or "doesn" in extraction.buyer_name.lower():
                b_name = existing_tender.get("buyer_name") or b_name
            if not extraction.estimated_value_inr and existing_tender.get("estimated_value_inr"):
                extraction.estimated_value_inr = existing_tender["estimated_value_inr"]
            if not extraction.emd_amount_inr and existing_tender.get("emd_amount_inr"):
                extraction.emd_amount_inr = existing_tender["emd_amount_inr"]
            if existing_tender.get("tender_fee_inr") is not None:
                extraction.tender_fee_inr = existing_tender["tender_fee_inr"]
            if existing_tender.get("processing_fee_inr") is not None:
                extraction.processing_fee_inr = existing_tender["processing_fee_inr"]
            if existing_tender.get("dealing_officer"):
                extraction.dealing_officer = existing_tender["dealing_officer"]
            if existing_tender.get("org_hierarchy"):
                extraction.org_hierarchy = existing_tender["org_hierarchy"]
            if existing_tender.get("attachments"):
                extraction.attachments = existing_tender["attachments"]
            if existing_tender.get("nit_attachment"):
                extraction.nit_attachment = existing_tender["nit_attachment"]
            if existing_tender.get("boq_attachment"):
                extraction.boq_attachment = existing_tender["boq_attachment"]
            if existing_tender.get("preview_details"):
                extraction.preview_details = existing_tender["preview_details"]
            if existing_tender.get("mandatory_documents"):
                for doc in existing_tender["mandatory_documents"]:
                    if doc not in extraction.mandatory_documents:
                        extraction.mandatory_documents.append(doc)

        tender_data = extraction.model_dump()

        raw_text_summary = (
            f"Tender Notice PDF: {pdf_path}\n"
            f"Total Pages: {extraction.total_pages}\n"
            f"Digital Text Coverage: {extraction.digital_text_coverage}\n"
        )

        # Commit to tiered storage (SQLite + snapshot json file)
        storage_meta = self.storage.save_tender_and_snapshot(
            org_id=org_id,
            tender_number=t_num,
            tender_title=t_title,
            source_url=f"pdf_upload:{Path(pdf_path).name}",
            buyer_name=b_name,
            submission_deadline=deadline_str,
            estimated_value_inr=extraction.estimated_value_inr,
            extracted_data=tender_data,
            raw_text_payload=raw_text_summary,
            tender_id=tender_id,
            emd_amount_inr=extraction.emd_amount_inr,
            state=existing_tender.get("state") if existing_tender else None,
            category=existing_tender.get("category") if existing_tender else None,
            portal=existing_tender.get("portal") if existing_tender else None,
            tenure_months=existing_tender.get("tenure_months") if existing_tender else None,
        )

        # Draft compliance RulePack from extracted clauses
        tender_id = storage_meta["tender_id"]
        rules = self._draft_rules_from_tender(tender_data)

        rule_pack_dict = {
            "tender_id": tender_id,
            "version": 1,
            "status": RuleStatus.DRAFT.value,
            "rules": [r.model_dump() for r in rules],
        }
        rule_pack_hash = self.storage.compute_sha256(json.dumps(rule_pack_dict, sort_keys=True))
        rule_pack_id = f"rp_{rule_pack_hash[:16]}"

        try:
            deadline_dt = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
        except Exception:
            deadline_dt = datetime.now(timezone.utc)

        rule_pack = RulePack(
            tender_id=tender_id,
            version=1,
            status=RuleStatus.DRAFT,
            content_hash=rule_pack_hash,
            reference_dates=ReferenceDates(submission_deadline=deadline_dt),
            rules=rules,
        )
        self._save_rule_pack_to_db(rule_pack_id, rule_pack)

        return {
            "success": True,
            "is_cached": False,
            "tender_id": tender_id,
            "tender_number": t_num,
            "tender_title": t_title,
            "buyer_name": b_name,
            "submission_deadline": deadline_str,
            "estimated_value_inr": extraction.estimated_value_inr,
            "emd_amount_inr": extraction.emd_amount_inr,
            "tender_fee_inr": extraction.tender_fee_inr,
            "processing_fee_inr": extraction.processing_fee_inr,
            "dealing_officer": extraction.dealing_officer,
            "org_hierarchy": extraction.org_hierarchy,
            "mandatory_documents": extraction.mandatory_documents,
            "attachments": extraction.attachments,
            "nit_attachment": extraction.nit_attachment,
            "boq_attachment": extraction.boq_attachment,
            "contract_period": extraction.contract_period,
            "portal_website": extraction.portal_website,
            "rule_pack_id": rule_pack_id,
            "rule_pack": rule_pack.model_dump(),
            "extraction": extraction.model_dump(),
            "json_schema": extraction.get_json_schema(),
            "storage": storage_meta,
        }

    def _draft_rules_from_tender(self, tender_data: Dict[str, Any]) -> List[Rule]:
        """Translates scraped criteria and clauses into deterministic Rule models."""
        rules: List[Rule] = []
        clauses = tender_data.get("verbatim_clauses", [])
        eligibility = tender_data.get("eligibility_rules", {})
        mandatory_docs = tender_data.get("mandatory_documents", [])

        # Helper to find quote for clause type
        def find_quote(clause_type: str, default: str) -> RuleSource:
            for c in clauses:
                if c.get("clause_type") == clause_type:
                    return RuleSource(page=c.get("page", 1), quote=c.get("quote", default))
            return RuleSource(page=1, quote=default)

        # 1. Statutory Document Rules (Udyam & CA Certificate)
        rules.append(
            Rule(
                rule_id="R-DOC-UDYAM",
                document_type=DocumentType.UDYAM_CERTIFICATE,
                rule_type=RuleType.DOCUMENT_REQUIRED,
                description="Valid Udyam Registration Certificate required for MSE eligibility / exemption.",
                source=find_quote("mse_exemption", "Udyam Registration Certificate required for MSE eligibility / exemption."),
                field="status",
                operator="eq",
                value="ACTIVE",
            )
        )

        rules.append(
            Rule(
                rule_id="R-DOC-CA",
                document_type=DocumentType.CA_TURNOVER_CERTIFICATE,
                rule_type=RuleType.DOCUMENT_REQUIRED,
                description="Chartered Accountant certified turnover balance sheet required.",
                source=find_quote("turnover_requirement", "CA Turnover Certificate mandatory."),
                field="status",
                operator="eq",
                value="SUBMITTED",
            )
        )

        # 2. Turnover Numeric Threshold Rule (T1)
        turnover_val = eligibility.get("min_annual_turnover_inr")
        if not turnover_val and tender_data.get("estimated_value_inr"):
            turnover_val = round(float(tender_data["estimated_value_inr"]) * 0.30, 2)

        if turnover_val:
            years = eligibility.get("turnover_years", 3)
            rules.append(
                Rule(
                    rule_id="R-TURNOVER-AVG3",
                    document_type=DocumentType.CA_TURNOVER_CERTIFICATE,
                    rule_type=RuleType.NUMERIC_THRESHOLD,
                    description=f"Average annual turnover over last {years} years must exceed ₹{turnover_val:,.2f}.",
                    source=find_quote("turnover_requirement", f"Minimum average turnover: INR {turnover_val}"),
                    field="average_turnover_inr",
                    operator="gte",
                    value=turnover_val,
                )
            )

        # 3. UDIN Mandatory Rule (ICAI compliance)
        rules.append(
            Rule(
                rule_id="R-UDIN",
                document_type=DocumentType.CA_TURNOVER_CERTIFICATE,
                rule_type=RuleType.IDENTIFIER_PRESENT,
                description="Chartered Accountant Unique Document Identification Number (UDIN) is mandatory.",
                source=find_quote("udin_requirement", "UDIN must be mentioned on CA certificates."),
                field="udin",
                operator="present",
                value=True,
            )
        )

        # 4. GST Registration Rule
        rules.append(
            Rule(
                rule_id="R-DOC-GST",
                document_type=DocumentType.GST_CERTIFICATE,
                rule_type=RuleType.DOCUMENT_REQUIRED,
                description="Valid Goods and Services Tax (GST) Registration Certificate required.",
                source=find_quote("gst_certificate", "Valid GST registration certificate required."),
                field="gstin",
                operator="present",
                value=True,
            )
        )

        # 4. Liquidity Numeric Threshold Rule (T2)
        liquidity_val = eligibility.get("min_liquidity_inr")
        if liquidity_val:
            rules.append(
                Rule(
                    rule_id="R-LIQUIDITY",
                    document_type=DocumentType.BANKING_REFERENCE,
                    rule_type=RuleType.NUMERIC_THRESHOLD,
                    description=f"Working capital / liquidity facility must exceed ₹{liquidity_val:,.2f}.",
                    source=find_quote("liquidity_requirement", f"Minimum liquidity requirement: INR {liquidity_val}"),
                    field="available_credit_facility_inr",
                    operator="gte",
                    value=liquidity_val,
                )
            )

        # 5. Single Work Experience Contract Rule
        work_exp_val = eligibility.get("min_work_experience_inr")
        if work_exp_val:
            rules.append(
                Rule(
                    rule_id="R-WORK-EXP",
                    document_type=DocumentType.WORK_EXPERIENCE,
                    rule_type=RuleType.NUMERIC_THRESHOLD,
                    description=f"Single qualifying completed contract value must exceed ₹{work_exp_val:,.2f}.",
                    source=find_quote("work_experience_requirement", f"Single work experience: INR {work_exp_val}"),
                    field="contract_value_inr",
                    operator="gte",
                    value=work_exp_val,
                )
            )

        # 6. Truthfulness Undertaking (Annexure-I)
        rules.append(
            Rule(
                rule_id="R-DOC-ANNEXURE-I",
                document_type=DocumentType.TRUTHFULNESS_UNDERTAKING,
                rule_type=RuleType.DOCUMENT_REQUIRED,
                description="Signed Truthfulness & Non-Debarment Undertaking on letterhead (Annexure-I).",
                source=find_quote("truthfulness_undertaking", "Undertaking for truthfulness of documents."),
                field="signed",
                operator="eq",
                value=True,
            )
        )

        # 7. Entity Type Restriction (e.g. Railway PSUs)
        eligible_entities = eligibility.get("eligible_entity_types", [])
        if eligible_entities:
            rules.append(
                Rule(
                    rule_id="R-ENTITY-ELIGIBILITY",
                    document_type=DocumentType.UDYAM_CERTIFICATE,
                    rule_type=RuleType.FIELD_IN_SET,
                    description=f"Bidder entity type must belong to approved types: {', '.join(eligible_entities)}.",
                    source=find_quote("entity_eligibility_restriction", f"Eligible entities: {eligible_entities}"),
                    field="entity_type",
                    operator="in",
                    value=eligible_entities,
                )
            )

        # 8. Rules for Mandatory Documents (extracted from Eye button or PDF checklist)
        existing_doc_rule_ids = {r.rule_id for r in rules}
        for d in mandatory_docs:
            d_lower = d.lower()
            if "pan" in d_lower and "R-DOC-PAN" not in existing_doc_rule_ids:
                rules.append(
                    Rule(
                        rule_id="R-DOC-PAN",
                        document_type=DocumentType.PAN_CARD,
                        rule_type=RuleType.DOCUMENT_REQUIRED,
                        description="Permanent Account Number (PAN) Card copy required.",
                        source=find_quote("pan_card", d),
                        field="pan",
                        operator="present",
                        value=True,
                    )
                )
                existing_doc_rule_ids.add("R-DOC-PAN")
            elif "gst" in d_lower and "R-DOC-GST" not in existing_doc_rule_ids:
                rules.append(
                    Rule(
                        rule_id="R-DOC-GST",
                        document_type=DocumentType.GST_CERTIFICATE,
                        rule_type=RuleType.DOCUMENT_REQUIRED,
                        description="Valid Goods and Services Tax (GST) Registration Certificate required.",
                        source=find_quote("gst_certificate", d),
                        field="gstin",
                        operator="present",
                        value=True,
                    )
                )
                existing_doc_rule_ids.add("R-DOC-GST")
            elif "itr" in d_lower and "R-DOC-ITR" not in existing_doc_rule_ids:
                rules.append(
                    Rule(
                        rule_id="R-DOC-ITR",
                        document_type=DocumentType.OTHER,
                        rule_type=RuleType.DOCUMENT_REQUIRED,
                        description="Income Tax Returns (ITR) copies for the last 3 financial years.",
                        source=find_quote("itr_requirement", d),
                        field="submitted",
                        operator="eq",
                        value=True,
                    )
                )
                existing_doc_rule_ids.add("R-DOC-ITR")
            elif ("emd" in d_lower or "tender fee" in d_lower or "processing fee" in d_lower) and "R-DOC-FEE-RECEIPT" not in existing_doc_rule_ids:
                rules.append(
                    Rule(
                        rule_id="R-DOC-FEE-RECEIPT",
                        document_type=DocumentType.OTHER,
                        rule_type=RuleType.DOCUMENT_REQUIRED,
                        description="EMD, Tender Fee, and Tender Processing Fee payment receipt / challan copy.",
                        source=find_quote("fee_payment", d),
                        field="paid",
                        operator="eq",
                        value=True,
                    )
                )
                existing_doc_rule_ids.add("R-DOC-FEE-RECEIPT")
            elif "character" in d_lower and "R-DOC-CHARACTER" not in existing_doc_rule_ids:
                rules.append(
                    Rule(
                        rule_id="R-DOC-CHARACTER",
                        document_type=DocumentType.OTHER,
                        rule_type=RuleType.DOCUMENT_REQUIRED,
                        description="Character Certificate issued within the last six months as per NIT.",
                        source=find_quote("character_certificate", d),
                        field="valid",
                        operator="eq",
                        value=True,
                    )
                )
                existing_doc_rule_ids.add("R-DOC-CHARACTER")
            elif ("registrtaion" in d_lower or "registration" in d_lower) and ("contractor" in d_lower or "registrtaion certifica" in d_lower):
                if "R-DOC-CONTRACTOR-REG" not in existing_doc_rule_ids:
                    rules.append(
                        Rule(
                            rule_id="R-DOC-CONTRACTOR-REG",
                            document_type=DocumentType.OTHER,
                            rule_type=RuleType.DOCUMENT_REQUIRED,
                            description="Contractor Registration Certificate with appropriate class / department.",
                            source=find_quote("contractor_registration", d),
                            field="active",
                            operator="eq",
                            value=True,
                        )
                    )
                    existing_doc_rule_ids.add("R-DOC-CONTRACTOR-REG")

        # 9. Rules from Government Verified Clauses
        for c in clauses:
            c_type = c.get("clause_type")
            if c_type == "joint_venture_restriction_clause" and "R-CLAUSE-NO-JV" not in existing_doc_rule_ids:
                rules.append(
                    Rule(
                        rule_id="R-CLAUSE-NO-JV",
                        document_type=DocumentType.OTHER,
                        rule_type=RuleType.DOCUMENT_REQUIRED,
                        description="Joint venture participation is strictly excluded; sole bidding only.",
                        source=RuleSource(page=c.get("page", 1), quote=c.get("quote", "")),
                        field="is_joint_venture",
                        operator="eq",
                        value=False,
                    )
                )
                existing_doc_rule_ids.add("R-CLAUSE-NO-JV")
            elif c_type == "bid_validity_emd_forfeiture_clause" and "R-CLAUSE-BID-VALIDITY" not in existing_doc_rule_ids:
                rules.append(
                    Rule(
                        rule_id="R-CLAUSE-BID-VALIDITY",
                        document_type=DocumentType.OTHER,
                        rule_type=RuleType.DOCUMENT_REQUIRED,
                        description="Bid validity commitment: EMD forfeiture acknowledged upon bid withdrawal.",
                        source=RuleSource(page=c.get("page", 1), quote=c.get("quote", "")),
                        field="bid_validity_accepted",
                        operator="eq",
                        value=True,
                    )
                )
                existing_doc_rule_ids.add("R-CLAUSE-BID-VALIDITY")

        return rules

    def _save_rule_pack_to_db(self, rule_pack_id: str, rule_pack: RulePack):
        """Persists the rule pack state in SQLite/PostgreSQL."""
        with sqlite3.connect(self.storage.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO rule_packs (
                    rule_pack_id, tender_id, version, status, content_hash, rules_json
                ) VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    rule_pack_id,
                    rule_pack.tender_id,
                    rule_pack.version,
                    rule_pack.status.value,
                    rule_pack.content_hash,
                    json.dumps([r.model_dump() for r in rule_pack.rules]),
                ),
            )
            conn.commit()

    def confirm_rule_pack(self, rule_pack_id: str, confirmed_by: str = "compliance_lead") -> Dict[str, Any]:
        """
        Transitions a RulePack from DRAFT to FROZEN.
        Calculates cryptographic hash and locks rules for assessment.
        """
        with sqlite3.connect(self.storage.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM rule_packs WHERE rule_pack_id = ?", (rule_pack_id,))
            row = cursor.fetchone()
            if not row:
                return {"success": False, "error": f"RulePack '{rule_pack_id}' not found."}

            if row["status"] == RuleStatus.FROZEN.value:
                return {
                    "success": True,
                    "message": "RulePack already frozen.",
                    "rule_pack_id": rule_pack_id,
                    "status": RuleStatus.FROZEN.value,
                }

            rules = json.loads(row["rules_json"])
            now = datetime.now(timezone.utc).isoformat()

            # Hash the frozen rules payload
            frozen_content = {
                "rule_pack_id": rule_pack_id,
                "tender_id": row["tender_id"],
                "version": row["version"],
                "confirmed_by": confirmed_by,
                "confirmed_at": now,
                "rules": rules,
            }
            frozen_hash = self.storage.compute_sha256(json.dumps(frozen_content, sort_keys=True))

            cursor.execute(
                """
                UPDATE rule_packs SET
                    status = ?,
                    content_hash = ?,
                    confirmed_by = ?,
                    confirmed_at = ?
                WHERE rule_pack_id = ?
            """,
                (RuleStatus.FROZEN.value, frozen_hash, confirmed_by, now, rule_pack_id),
            )
            conn.commit()

            return {
                "success": True,
                "rule_pack_id": rule_pack_id,
                "tender_id": row["tender_id"],
                "status": RuleStatus.FROZEN.value,
                "content_hash": frozen_hash,
                "confirmed_by": confirmed_by,
                "confirmed_at": now,
                "rule_count": len(rules),
            }

    def get_rule_pack(self, rule_pack_id: str) -> Optional[RulePack]:
        """Retrieves and deserializes a RulePack by ID."""
        with sqlite3.connect(self.storage.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM rule_packs WHERE rule_pack_id = ?", (rule_pack_id,))
            row = cursor.fetchone()
            if not row:
                return None

            rules_data = json.loads(row["rules_json"])
            rules = [Rule(**r) for r in rules_data]

            cursor.execute("SELECT submission_deadline FROM tenders WHERE tender_id = ?", (row["tender_id"],))
            t_row = cursor.fetchone()
            try:
                deadline = datetime.fromisoformat(t_row["submission_deadline"]) if t_row else datetime.now(timezone.utc)
            except Exception:
                deadline = datetime.now(timezone.utc)

            return RulePack(
                tender_id=row["tender_id"],
                version=row["version"],
                status=RuleStatus(row["status"]),
                content_hash=row["content_hash"],
                reference_dates=ReferenceDates(submission_deadline=deadline),
                rules=rules,
            )

    def get_rule_pack_by_tender_id(self, tender_id: str) -> Optional[RulePack]:
        """Retrieves and deserializes the active/draft RulePack for a tender."""
        with sqlite3.connect(self.storage.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT external_id FROM tenders WHERE tender_id = ?", (tender_id,))
            t_row = cursor.fetchone()
            ext_id = t_row["external_id"] if t_row else None
            alt_id = f"tnd_{self.storage.compute_sha256(ext_id)[:12]}" if ext_id else None

            cursor.execute(
                """SELECT rule_pack_id FROM rule_packs 
                   WHERE tender_id = ? OR (tender_id = ? AND ? IS NOT NULL)
                   ORDER BY version DESC LIMIT 1""",
                (tender_id, alt_id, alt_id),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self.get_rule_pack(row["rule_pack_id"])

    def get_tender(self, identifier: str, mode: str = "skim") -> Optional[Dict[str, Any]]:
        """
        Retrieves tender details supporting both viewing modes:
        - 'skim': Fast summary of metadata (title, buyer, estimated value, EMD, tenure, deadline)
        - 'detailed': Parses the full PDF notice, extracts all verbatim clauses with page numbers, and returns draft rules.
        """
        from backend.apps.tenders.search import TenderSearchService
        return TenderSearchService(storage=self.storage).get_tender(identifier, mode=mode)

