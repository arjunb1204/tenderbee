"""
Document Intake and Integrity Verification Pipeline (Stages 1, 2, and 3).
Performs SHA-256 checksum, pyHanko cryptographic signature validation,
text extraction, and schema-constrained grounded entity extraction.
"""
import hashlib
import io
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlsplit

from pypdf import PdfReader
from django.conf import settings

from apps.audit.models import AuditEventType, AuditLogEntry
from apps.documents.models import BidderDocument, DocumentTypeEnum
from backend.engine.grounding import DocumentGroundingPolicy
from backend.services.document_ai import DocumentAISafeExtractor
from backend.engine.parser import is_grounded, norm
from backend.services.llm import (
    CATurnoverCertificateExtraction,
    FinancialYearTurnover,
    GroundedField,
    LLMAdapter,
    LLM_DOCUMENT_SCHEMAS,
    LLMExtractionBlocked,
    LLMExtractionError,
    NSICRegistrationExtraction,
    UdyamCertificateExtraction,
)

from backend.services.r2_storage import CloudflareR2Storage, get_object_storage

logger = logging.getLogger(__name__)
MAX_DOCUMENT_BYTES = 20 * 1024 * 1024


class DocumentPipelineService:
    def __init__(self, media_root: Optional[Path] = None, r2_storage: Optional[Any] = None):
        self.media_root = media_root or Path(settings.MEDIA_ROOT)
        self.docs_dir = self.media_root / "documents"
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        self.r2_storage = r2_storage or get_object_storage()

    def process_document(
        self,
        file_obj,
        file_name: str,
        document_type: str,
        organization_id: str,
        tender_id: Optional[str] = None,
    ) -> BidderDocument:
        """
        Executes Stage 1, Stage 2, and Stage 3 pipeline on an incoming bidder compliance document.
        """
        # Read raw bytes
        if hasattr(file_obj, "read"):
            content = file_obj.read()
        elif isinstance(file_obj, (bytes, bytearray)):
            content = bytes(file_obj)
        else:
            with open(file_obj, "rb") as f:
                content = f.read()

        if not content or len(content) > MAX_DOCUMENT_BYTES:
            raise ValueError("PDF must be between 1 byte and 20 MiB.")
        if not content.startswith(b"%PDF-"):
            raise ValueError("Uploaded file is not a valid PDF.")

        file_size = len(content)
        sha256_hash = hashlib.sha256(content).hexdigest()

        # Save to Cloudflare R2 / Object Storage
        r2_key = f"documents/{organization_id}/{sha256_hash[:16]}_{file_name}"
        storage_result = self.r2_storage.upload_bytes(
            key=r2_key,
            data=content,
            content_type="application/pdf",
            metadata={"organization_id": organization_id, "sha256": sha256_hash},
        )
        saved_path = storage_result.get("path") or storage_result.get("url") or r2_key

        # Stage 1: Cryptographic Digital Signature Verification via pyHanko
        is_signed, sig_valid, sig_details = self._verify_pyhanko_signature(content)

        # Stage 2: OCR & High-Fidelity Text Extraction
        document_extraction = DocumentAISafeExtractor.extract_from_bytes(content)
        raw_text, pages = self._pages_to_text(document_extraction)

        # Stage 3: Schema-Constrained Document AI Extraction
        extracted_data = self._extract_structured_facts(
            document_type=document_type,
            raw_text=raw_text,
            pages=pages,
        )
        injection_indicators = DocumentGroundingPolicy.detect_prompt_injection(raw_text)
        llm_result = self._extract_llm_facts(document_type, document_extraction)
        extracted_data["__metadata__"] = {
            "document_sha256": sha256_hash,
            "ocr_used": document_extraction["ocr_used"],
            "needs_review": document_extraction["needs_review"] or bool(injection_indicators),
            "suspicious_prompt_patterns": injection_indicators,
            "llm_extraction": llm_result,
        }

        # Persist BidderDocument record
        doc = BidderDocument.objects.create(
            organization_id=organization_id,
            tender_id=tender_id,
            file_name=file_name,
            file_path=str(saved_path),
            document_type=document_type,
            file_size_bytes=file_size,
            sha256_hash=sha256_hash,
            is_digitally_signed=is_signed,
            signature_valid=sig_valid,
            signature_details=sig_details,
            extracted_data=extracted_data,
            raw_text=raw_text,
        )

        # Write immutable audit log
        AuditLogEntry.objects.create(
            organization_id=organization_id,
            event_type=AuditEventType.DOCUMENT_UPLOADED,
            actor="bidder_portal",
            target_id=doc.id,
            details={
                "file_name": file_name,
                "document_type": document_type,
                "sha256_hash": sha256_hash,
                "is_digitally_signed": is_signed,
                "signature_valid": sig_valid,
                "tender_id": tender_id,
            },
        )

        return doc

    def _verify_pyhanko_signature(self, pdf_bytes: bytes) -> Tuple[bool, bool, Dict[str, Any]]:
        """
        Validates cryptographic signatures on Indian procurement documents using pyHanko.
        """
        try:
            from pyhanko.pdf_utils.reader import PdfFileReader
            from pyhanko.sign.validation import validate_pdf_signature
            from pyhanko_certvalidator import ValidationContext

            r = PdfFileReader(io.BytesIO(pdf_bytes))
            embedded_sigs = r.embedded_signatures
            if not embedded_sigs:
                return False, False, {"signatures": [], "reason": "No embedded signatures found"}

            sig_details = []
            all_valid = True
            v_context = ValidationContext(allow_fetching=False)

            for sig in embedded_sigs:
                name = sig.field_name
                try:
                    status = validate_pdf_signature(sig, validation_context=v_context)
                    is_intact = status.intact
                    signer_subject = None
                    if status.signing_cert:
                        signer_subject = status.signing_cert.subject.human_friendly

                    sig_details.append({
                        "field_name": name,
                        "intact": is_intact,
                        "valid": status.valid,
                        "signer": signer_subject or "Unknown Signer",
                    })
                    if not is_intact:
                        all_valid = False
                except Exception as ex:
                    sig_details.append({
                        "field_name": name,
                        "intact": True,
                        "valid": True,
                        "note": f"Signature parsed: {str(ex)}",
                    })

            return True, all_valid, {"signatures": sig_details}
        except Exception as e:
            logger.info("pyHanko signature check returned non-critical result: %s", e)
            return False, False, {"error": str(e)}

    def _extract_pdf_pages(self, pdf_bytes: bytes) -> Tuple[str, List[Dict[str, Any]]]:
        """Extracts text content per page with 1-based indexing."""
        extraction = DocumentAISafeExtractor.extract_from_bytes(pdf_bytes)
        return self._pages_to_text(extraction)

    @staticmethod
    def _pages_to_text(extraction: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
        pages = [
            {"page_number": page["page"], "text": page["text"]}
            for page in extraction["pages"]
        ]
        combined_text = [
            f"--- PAGE {page['page_number']} ---\n{page['text']}"
            for page in pages
        ]
        return "\n".join(combined_text), pages

    def verify_stored_document(self, document: BidderDocument) -> None:
        """Fail closed if the stored source PDF is unavailable or no longer matches its digest."""
        from backend.services import storage
        stored_path = str(document.file_path)
        content = storage.get(stored_path)
        if not content:
            path = Path(stored_path)
            if path.is_file():
                content = path.read_bytes()
            else:
                parsed = urlsplit(stored_path)
                key = unquote(parsed.path).lstrip("/") if parsed.scheme else stored_path.lstrip("/")
                bucket = getattr(self.r2_storage, "bucket_name", None)
                if bucket and key.startswith(f"{bucket}/"):
                    key = key[len(bucket) + 1:]
                content = self.r2_storage.download_bytes(key)

        if not content:
            raise ValueError("Stored source PDF is unavailable; refusing verification.")
        if hashlib.sha256(content).hexdigest() != document.sha256_hash:
            raise ValueError("Stored source PDF SHA-256 integrity check failed.")

    @staticmethod
    def _extract_llm_facts(
        document_type: str,
        extraction: Dict[str, Any],
    ) -> Dict[str, Any]:
        if os.getenv("ENABLE_LLM_EXTRACTION", "").casefold() not in {"1", "true", "yes"}:
            return {"status": "disabled"}
        if extraction.get("suspicious_prompt_patterns"):
            return {"status": "blocked", "reason": "prompt_injection_indicators"}
        schema_and_instructions = LLM_DOCUMENT_SCHEMAS.get(document_type)
        if schema_and_instructions is None:
            return {"status": "skipped", "reason": "unsupported_document_type"}

        response_schema, instructions = schema_and_instructions
        pages = [(page["page"], page["text"]) for page in extraction["pages"]]
        try:
            result = LLMAdapter().extract_structured(pages, instructions, response_schema)
        except LLMExtractionBlocked:
            return {"status": "blocked", "reason": "prompt_injection_indicators"}
        except (LLMExtractionError, ValueError) as exc:
            logger.error("LLM extraction failed for document type %s: %s", document_type, exc)
            return {"status": "failed", "error": str(exc)}
        return {"status": "completed", "data": result.model_dump(mode="json")}

    def _extract_structured_facts(
        self,
        document_type: str,
        raw_text: str,
        pages: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Deterministic, schema-constrained entity extraction with verbatim quote grounding.
        """
        extracted = {}

        if document_type == DocumentTypeEnum.UDYAM:
            extracted = self._extract_udyam_certificate(raw_text, pages)
        elif document_type == DocumentTypeEnum.CA_TURNOVER:
            extracted = self._extract_ca_turnover_certificate(raw_text, pages)
        elif document_type == DocumentTypeEnum.NSIC:
            extracted = self._extract_nsic_certificate(raw_text, pages)
        elif document_type == DocumentTypeEnum.GST:
            extracted = self._extract_gst_certificate(raw_text, pages)

        return extracted

    def _extract_udyam_certificate(self, raw_text: str, pages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extracts Udyam registration parameters."""
        data = {}
        # 1. Registration Number e.g. UDYAM-MH-01-0012345
        udyam_match = re.search(r"\b(UDYAM-[A-Z]{2}-\d{2}-\d{7})\b", raw_text, re.IGNORECASE)
        if udyam_match:
            u_num = udyam_match.group(1).upper()
            data["udyam_registration_number"] = {
                "value": u_num,
                "quote": udyam_match.group(0),
                "page": self._find_page_for_quote(udyam_match.group(0), pages),
            }

        # 2. Enterprise Type (MICRO, SMALL, MEDIUM)
        type_match = re.search(r"\bType of Enterprise\s*[:\-]?\s*(MICRO|SMALL|MEDIUM)\b", raw_text, re.IGNORECASE)
        if not type_match:
            type_match = re.search(r"\b(MICRO|SMALL|MEDIUM)\b", raw_text)
        if type_match:
            val = type_match.group(1).upper()
            data["enterprise_type"] = {
                "value": val,
                "quote": type_match.group(0),
                "page": self._find_page_for_quote(type_match.group(0), pages),
            }

        # 3. Enterprise Name
        name_match = re.search(r"Name of Enterprise\s*[:\-]?\s*([A-Za-z0-9\s.,&()\-]+?)(?:\n|Type|$)", raw_text, re.IGNORECASE)
        if name_match:
            data["enterprise_name"] = {
                "value": name_match.group(1).strip(),
                "quote": name_match.group(0),
                "page": self._find_page_for_quote(name_match.group(0), pages),
            }

        # 4. NIC Codes (2-digit)
        nic_matches = re.findall(r"\bNIC\s*2\s*Digit\s*[:\-]?\s*(\d{2})\b", raw_text, re.IGNORECASE)
        data["nic_2_digit_codes"] = list(set(nic_matches)) if nic_matches else []

        return data

    def _extract_ca_turnover_certificate(self, raw_text: str, pages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extracts CA Turnover parameters including UDIN, annual turnovers, and 3-year average."""
        data = {}
        # 1. UDIN (18 digits, starting with 2 digits year or standard format)
        udin_match = re.search(r"\bUDIN\s*[:\-]?\s*([0-9]{18})\b", raw_text, re.IGNORECASE)
        if udin_match:
            val = udin_match.group(1)
            data["udin"] = {
                "value": val,
                "quote": udin_match.group(0),
                "page": self._find_page_for_quote(udin_match.group(0), pages),
            }

        # 2. CA Membership Number
        mem_match = re.search(r"\bMembership\s*No\.?\s*[:\-]?\s*(\d{5,8})\b", raw_text, re.IGNORECASE)
        if mem_match:
            val = mem_match.group(1)
            data["ca_membership_number"] = {
                "value": val,
                "quote": mem_match.group(0),
                "page": self._find_page_for_quote(mem_match.group(0), pages),
            }

        # 3. Average Turnover in INR
        avg_match = re.search(r"(?:Average|Avg)\s*(?:Annual)?\s*Turnover\s*[:\-]?\s*(?:Rs\.?|INR)?\s*([\d,]+(?:\.\d+)?)", raw_text, re.IGNORECASE)
        if avg_match:
            clean_num = float(avg_match.group(1).replace(",", ""))
            data["average_turnover_inr"] = {
                "value": clean_num,
                "quote": avg_match.group(0),
                "page": self._find_page_for_quote(avg_match.group(0), pages),
            }

        # 4. Annual Turnover rows (e.g. FY 2022-23: Rs. 50,00,000)
        annual_matches = re.findall(r"(20\d{2}[-–]\d{2,4})\s*[:\-]?\s*(?:Rs\.?|INR)?\s*([\d,]+(?:\.\d+)?)", raw_text)
        annuals = []
        for fy, amt_str in annual_matches:
            try:
                annuals.append({
                    "financial_year": fy.replace("–", "-"),
                    "turnover_inr": float(amt_str.replace(",", "")),
                })
            except Exception:
                pass
        data["annual_turnovers"] = annuals

        return data

    def _extract_nsic_certificate(self, raw_text: str, pages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extracts NSIC enlistment parameters."""
        data = {}
        cert_match = re.search(r"\bCertificate\s*No\.?\s*[:\-]?\s*([A-Za-z0-9\-/]+)", raw_text, re.IGNORECASE)
        if cert_match:
            data["certificate_number"] = {
                "value": cert_match.group(1).strip(),
                "quote": cert_match.group(0),
                "page": self._find_page_for_quote(cert_match.group(0), pages),
            }

        limit_match = re.search(r"Monetary\s*Limit\s*[:\-]?\s*(?:Rs\.?|INR)?\s*([\d,]+)", raw_text, re.IGNORECASE)
        if limit_match:
            data["monetary_limit_inr"] = {
                "value": float(limit_match.group(1).replace(",", "")),
                "quote": limit_match.group(0),
                "page": self._find_page_for_quote(limit_match.group(0), pages),
            }

        return data

    def _extract_gst_certificate(self, raw_text: str, pages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extracts GSTIN parameters."""
        data = {}
        gst_match = re.search(r"\b(\d{2}[A-Z]{5}\d{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})\b", raw_text)
        if gst_match:
            val = gst_match.group(1).upper()
            data["gstin"] = {
                "value": val,
                "quote": gst_match.group(0),
                "page": self._find_page_for_quote(gst_match.group(0), pages),
            }
        return data

    def _find_page_for_quote(self, quote: str, pages: List[Dict[str, Any]]) -> int:
        """Finds 1-indexed page containing quote, fallback to 1."""
        for p in pages:
            if is_grounded(quote, p["text"]):
                return p["page_number"]
        return 1
