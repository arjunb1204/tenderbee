"""
Tender Discovery & Multi-Criteria Search Engine for TenderBee.
Supports natural language query parsing (e.g. 'services in bihar above 1 cr for 2 years')
and structured multi-dimensional filtering across geography, category, capital, tenure, and buyer.
"""
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.services.storage import TenderStorage

logger = logging.getLogger(__name__)

INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
    "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
    "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Delhi", "Jammu and Kashmir", "Ladakh"
]

STATE_ALIASES = {
    "up": "Uttar Pradesh",
    "u.p.": "Uttar Pradesh",
    "rj": "Rajasthan",
    "raj": "Rajasthan",
    "rajasthan": "Rajasthan",
    "mh": "Maharashtra",
    "maha": "Maharashtra",
    "wb": "West Bengal",
    "w.b.": "West Bengal",
    "mp": "Madhya Pradesh",
    "m.p.": "Madhya Pradesh",
    "ap": "Andhra Pradesh",
    "a.p.": "Andhra Pradesh",
    "hr": "Haryana",
    "hry": "Haryana",
    "br": "Bihar",
    "bihar": "Bihar",
    "dl": "Delhi",
    "ncr": "Delhi",
    "gj": "Gujarat",
    "tn": "Tamil Nadu",
    "ka": "Karnataka",
    "kl": "Kerala",
    "ts": "Telangana",
    "tg": "Telangana",
    "pb": "Punjab",
    "od": "Odisha",
    "jh": "Jharkhand",
    "uk": "Uttarakhand",
    "ua": "Uttarakhand",
}

CITY_TO_STATE = {
    # Bihar
    "patna": "Bihar", "gaya": "Bihar", "bhagalpur": "Bihar", "muzaffarpur": "Bihar",
    "darbhanga": "Bihar", "purnia": "Bihar", "hajipur": "Bihar", "danapur": "Bihar",
    # Uttar Pradesh
    "lucknow": "Uttar Pradesh", "kanpur": "Uttar Pradesh", "varanasi": "Uttar Pradesh",
    "noida": "Uttar Pradesh", "greater noida": "Uttar Pradesh", "agra": "Uttar Pradesh",
    "prayagraj": "Uttar Pradesh", "allahabad": "Uttar Pradesh", "ghaziabad": "Uttar Pradesh",
    "meerut": "Uttar Pradesh", "bareilly": "Uttar Pradesh", "aligarh": "Uttar Pradesh",
    "gorakhpur": "Uttar Pradesh", "ayodhya": "Uttar Pradesh", "jhansi": "Uttar Pradesh",
    # Rajasthan
    "jaipur": "Rajasthan", "jodhpur": "Rajasthan", "udaipur": "Rajasthan", "kota": "Rajasthan",
    "bikaner": "Rajasthan", "ajmer": "Rajasthan", "bhilwara": "Rajasthan", "alwar": "Rajasthan",
    # Maharashtra
    "mumbai": "Maharashtra", "pune": "Maharashtra", "nagpur": "Maharashtra",
    "thane": "Maharashtra", "nashik": "Maharashtra", "aurangabad": "Maharashtra",
    # Haryana
    "gurugram": "Haryana", "gurgaon": "Haryana", "faridabad": "Haryana",
    "panipat": "Haryana", "ambala": "Haryana", "rohtak": "Haryana", "karnal": "Haryana",
    "hisar": "Haryana", "sonipat": "Haryana",
    # West Bengal
    "kolkata": "West Bengal", "howrah": "West Bengal", "durgapur": "West Bengal",
    "asansol": "West Bengal", "siliguri": "West Bengal",
    # Delhi NCR
    "delhi": "Delhi", "new delhi": "Delhi",
}

CATEGORIES = ["Services", "Works", "Goods"]


class TenderSearchFilter(BaseModel):
    query: Optional[str] = Field(default=None, description="Free text keywords")
    tender_number: Optional[str] = Field(default=None, description="Exact or partial tender reference number / ID")
    state: Optional[str] = Field(default=None, description="Indian state name (e.g. Bihar)")
    city_or_district: Optional[str] = Field(default=None, description="City or district (e.g. Patna)")
    category: Optional[str] = Field(default=None, description="Services, Works, or Goods")
    min_value_inr: Optional[float] = Field(default=None, description="Minimum estimated contract value")
    max_value_inr: Optional[float] = Field(default=None, description="Maximum estimated contract value")
    min_tenure_months: Optional[int] = Field(default=None, description="Minimum contract period in months")
    max_tenure_months: Optional[int] = Field(default=None, description="Maximum contract period in months")
    buyer_name: Optional[str] = Field(default=None, description="Issuing authority / department")
    active_only: bool = Field(default=True, description="Filter only active tenders with upcoming deadlines")
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)


class TenderSearchResult(BaseModel):
    tender_id: str
    tender_number: str
    title: str
    buyer_name: str
    state: str
    category: str
    estimated_value_inr: Optional[float] = None
    emd_amount_inr: Optional[float] = None
    tenure_months: Optional[int] = None
    submission_deadline: Optional[str] = None
    portal: str
    source_url: Optional[str] = None
    status: str = "ACTIVE"


class QueryParser:
    """
    Parses natural language procurement requests into structured TenderSearchFilter.
    Supports hybrid execution:
    1. First attempts LLM-based query comprehension for complex natural language prompts.
    2. Falls back to deterministic regex parser across Indian geography, categories, and financials.
    """

    @classmethod
    def parse(cls, prompt: str, llm_adapter: Optional[Any] = None) -> TenderSearchFilter:
        text = prompt.strip()
        lower = text.lower()

        # Step 1: Attempt LLM-based query parsing if adapter available
        if llm_adapter is not None:
            try:
                llm_parsed = llm_adapter.parse_query(prompt)
                if llm_parsed:
                    logger.info("LLM query parser extracted structured filters: %s", llm_parsed.model_dump())
                    return TenderSearchFilter(
                        query=llm_parsed.query,
                        tender_number=getattr(llm_parsed, "tender_number", None),
                        state=llm_parsed.state,
                        city_or_district=llm_parsed.city_or_district,
                        category=llm_parsed.category,
                        min_value_inr=llm_parsed.min_value_inr,
                        max_value_inr=llm_parsed.max_value_inr,
                        min_tenure_months=llm_parsed.min_tenure_months,
                        buyer_name=llm_parsed.buyer_name,
                    )
            except Exception as e:
                logger.debug("LLM query parsing encountered exception, falling back to deterministic parser: %s", e)

        # Step 2: Deterministic Rule-Based Parsing
        # Direct URL detection: preserve tender URL or extract embedded ID cleanly
        if text.startswith("http://") or text.startswith("https://"):
            tender_number = cls._extract_tender_number(text)
            return TenderSearchFilter(
                query=None if tender_number else text,
                tender_number=tender_number,
            )

        tender_number = cls._extract_tender_number(text)
        state = cls._extract_state(lower)
        category = cls._extract_category(lower)
        city = cls._extract_city(lower, state)
        if not state and city:
            state = cls._infer_state_from_city(city)
        min_val, max_val = cls._extract_values(lower)
        min_tenure = cls._extract_tenure(lower)
        keywords = cls._extract_keywords(text, state, category, city, tender_number=tender_number)

        return TenderSearchFilter(
            query=keywords if keywords else None,
            tender_number=tender_number,
            state=state,
            city_or_district=city,
            category=category,
            min_value_inr=min_val,
            max_value_inr=max_val,
            min_tenure_months=min_tenure,
        )

    @classmethod
    def _extract_tender_number(cls, text: str) -> Optional[str]:
        """
        Extracts exact or partial tender numbers, RFQ IDs, or portal bid numbers.
        Handles prefixes ('tender 141349', 'tender no 2026_HRY_530295_1') and
        well-known Indian portal numbering schemes.
        """
        # 1. Check for explicit prefix: tender no, tender #, tender id, tender number, rfq, bid no
        m_prefix = re.search(
            r"(?:tender\s*(?:no\.?|number|id|#)?|rfq\s*(?:no\.?|number|id|#)?|bid\s*(?:no\.?|number|id|#)?)\s*[:\-]?\s*([A-Za-z0-9_\/-]{4,})",
            text,
            re.IGNORECASE,
        )
        if m_prefix:
            cand = m_prefix.group(1).strip().lstrip("/").rstrip(".,;:/")
            # Filter out common non-tender words if matched erroneously
            if cand.lower() not in (
                "active", "notice", "notices", "details", "detail", "document", "documents",
                "service", "services", "goods", "works", "bihar", "haryana", "delhi"
            ):
                return cand

        # 2. Bihar eProc2 format: BIH/EPROC2/141349 or EPROC2/141349
        m_bih = re.search(r"\b(BIH/EPROC2/\d+|EPROC2/\d+)\b", text, re.IGNORECASE)
        if m_bih:
            return m_bih.group(1).upper()

        # 3. CPPP / GePNIC tender IDs: e.g. 2026_HRY_530295_1, 2025_CPPP_123456_1
        m_cppp = re.search(r"\b(20\d\d_[A-Za-z0-9_]+_\d+_\d+|20\d\d_[A-Za-z0-9_]+_\d+)\b", text)
        if m_cppp:
            return m_cppp.group(1)

        # 4. GeM Bid Numbers: e.g. GEM/2026/B/1234567, GEM/2025/R/12345, or slug GEM-2026-B-894210
        m_gem = re.search(r"\b(GEM[-_/](\d{4})[-_/]([A-Za-z])[-_/](\d+))\b", text, re.IGNORECASE)
        if m_gem:
            return f"GEM/{m_gem.group(2)}/{m_gem.group(3).upper()}/{m_gem.group(4)}"

        # 5. Railway / IREPS / Department tender numbers with slashes: e.g. ECR/HAJIPUR/CIVIL/2026/09
        m_dept = re.search(r"\b([A-Z]{2,10}/[A-Za-z0-9_\/-]{5,})\b", text)
        if m_dept:
            return m_dept.group(1)

        # 6. TenderBee internal ID format: tnd_bih_141349 or tnd_...
        m_tnd = re.search(r"\b(tnd_[a-zA-Z0-9_]+)\b", text, re.IGNORECASE)
        if m_tnd:
            return m_tnd.group(1).lower()

        # 7. Standalone numeric RFQ or tender ID (e.g. 141349, 140751, 530295) if entire text is digits
        stripped = text.strip()
        if re.match(r"^\d{4,10}$", stripped):
            return stripped

        # 8. 6-digit RFQ ID typically used in Bihar eProc2 (14XXXX)
        m_rfq = re.search(r"\b(14\d{4})\b", text)
        if m_rfq:
            return m_rfq.group(1)

        return None

    @classmethod
    def _extract_state(cls, text: str) -> Optional[str]:
        for s in INDIAN_STATES:
            if re.search(r"\b" + re.escape(s.lower()) + r"\b", text):
                return s
        for alias, state_name in STATE_ALIASES.items():
            if re.search(r"\b" + re.escape(alias) + r"\b", text):
                return state_name
        return None

    @classmethod
    def _extract_category(cls, text: str) -> Optional[str]:
        if re.search(r"\b(service|services|housekeeping|sanitation|security|manpower|facility|it)\b", text):
            return "Services"
        if re.search(r"\b(work|works|civil|construction|road|bridge|building|pipeline|drainage|expressway|flyover)\b", text):
            return "Works"
        if re.search(r"\b(good|goods|supply|supplies|equipment|hardware|vehicle|material|solar)\b", text):
            return "Goods"
        return None

    @classmethod
    def _extract_city(cls, text: str, state: Optional[str]) -> Optional[str]:
        for c in CITY_TO_STATE:
            if re.search(r"\b" + re.escape(c) + r"\b", text):
                return "Gurugram" if c == "gurgaon" else c.title()
        return None

    @classmethod
    def _infer_state_from_city(cls, city: str) -> Optional[str]:
        return CITY_TO_STATE.get(city.lower())

    @classmethod
    def _extract_values(cls, text: str) -> tuple[Optional[float], Optional[float]]:
        min_val = None
        max_val = None

        # Regex for Crore (Cr / Crore / Crores)
        cr_matches = re.findall(r"(\d+(?:\.\d+)?)\s*(?:cr|crore|crores)\b", text)
        # Regex for Lakh (Lakh / Lakhs / L / Lac / Lacs)
        lakh_matches = re.findall(r"(\d+(?:\.\d+)?)\s*(?:lakh|lakhs|lac|lacs|l)\b", text)

        # Look for above / minimum / >
        above_m = re.search(r"(?:above|min|minimum|greater than|>|more than)\s*₹?\s*(\d+(?:\.\d+)?)\s*(cr|crore|crores|lakh|lakhs|l)?", text)
        if above_m:
            num = float(above_m.group(1))
            unit = (above_m.group(2) or "").lower()
            if "cr" in unit:
                min_val = num * 10000000.0
            elif "l" in unit or "lac" in unit:
                min_val = num * 100000.0
            else:
                min_val = num

        # Look for below / maximum / <
        below_m = re.search(r"(?:below|max|maximum|less than|<|upto)\s*₹?\s*(\d+(?:\.\d+)?)\s*(cr|crore|crores|lakh|lakhs|l)?", text)
        if below_m:
            num = float(below_m.group(1))
            unit = (below_m.group(2) or "").lower()
            if "cr" in unit:
                max_val = num * 10000000.0
            elif "l" in unit or "lac" in unit:
                max_val = num * 100000.0
            else:
                max_val = num

        # If bare number with Cr was found and no above/below
        if min_val is None and cr_matches:
            min_val = float(cr_matches[0]) * 10000000.0
        elif min_val is None and lakh_matches:
            min_val = float(lakh_matches[0]) * 100000.0

        return min_val, max_val

    @classmethod
    def _extract_tenure(cls, text: str) -> Optional[int]:
        # Years
        yr_m = re.search(r"(\d+)\s*(?:year|years|yr|yrs)\b", text)
        if yr_m:
            return int(yr_m.group(1)) * 12
        # Months
        m_m = re.search(r"(\d+)\s*(?:month|months|mo|mos)\b", text)
        if m_m:
            return int(m_m.group(1))
        return None

    @classmethod
    def _extract_keywords(
        cls,
        original: str,
        state: Optional[str],
        category: Optional[str],
        city: Optional[str],
        tender_number: Optional[str] = None,
    ) -> str:
        s = original
        if tender_number:
            # Strip tender number from residual keywords
            s = re.sub(re.escape(tender_number), " ", s, flags=re.IGNORECASE)
            if tender_number.isdigit():
                s = re.sub(r"\b(?:BIH/EPROC2/|EPROC2/|GEM/\d{4}/[A-Z]/)\b", " ", s, flags=re.IGNORECASE)

        remove_terms = [
            "tenders", "tender", "related", "to", "released", "in", "for", "give", "me", "show",
            "active", "above", "below", "greater", "less", "than", "with", "tenure", "duration",
            "period", "capital", "value", "budget", "find", "search", "between", "from", "upto",
            "having", "contract", "like", "any", "all", "around", "near", "location", "is", "these",
            "those", "there", "wanted", "want", "look", "looking", "procurement", "notice", "notices",
            "number", "numbers", "rfq", "bid", "no"
        ]
        if state:
            remove_terms.extend([state.lower(), f"in {state.lower()}"])
            for alias, full_state in STATE_ALIASES.items():
                if full_state.lower() == state.lower():
                    remove_terms.extend([alias, f"in {alias}"])
        if category:
            remove_terms.extend([category.lower(), f"{category.lower()}s"])
        if city:
            remove_terms.extend([city.lower(), f"in {city.lower()}"])

        pattern = r"\b(" + "|".join(re.escape(w) for w in remove_terms) + r")\b"
        cleaned = re.sub(pattern, " ", s, flags=re.IGNORECASE)
        # Remove numbers and currency words
        cleaned = re.sub(r"\b\d+(?:\.\d+)?\s*(cr|crore|crores|lakh|lakhs|l|lac|lacs|year|years|yr|yrs|month|months|mo|mos|rs|inr|₹)?\b", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"[^\w\s]", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned


class TenderSearchService:
    """
    Orchestrates multi-criteria tender discovery across the local database index,
    live GeM portal search, and state e-procurement systems (like eproc2.bihar.gov.in).
    """

    def __init__(
        self,
        storage: Optional[TenderStorage] = None,
        llm_adapter: Optional[Any] = None,
        live_search_engine: Optional[Any] = None,
    ):
        self.storage = storage or TenderStorage()
        if llm_adapter is not None:
            self.llm_adapter = llm_adapter
        else:
            try:
                from backend.services.llm import LLMAdapter
                self.llm_adapter = LLMAdapter()
            except Exception:
                self.llm_adapter = None

        if live_search_engine is not None:
            self.live_search_engine = live_search_engine
        else:
            try:
                from backend.services.live_search import LiveTenderSearchEngine
                self.live_search_engine = LiveTenderSearchEngine(storage=self.storage)
            except Exception:
                self.live_search_engine = None

    def search(self, filters: TenderSearchFilter, raw_prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute search query across local index and connected portals.
        """
        # 1. Search local indexed database
        local_results = self.storage.search_indexed_tenders(
            query=filters.query,
            tender_number=filters.tender_number,
            state=filters.state,
            category=filters.category,
            min_value_inr=filters.min_value_inr,
            max_value_inr=filters.max_value_inr,
            min_tenure_months=filters.min_tenure_months,
            buyer_name=filters.buyer_name,
            limit=filters.limit,
            offset=(filters.page - 1) * filters.limit,
        )

        total_count = len(local_results)

        # 2. If no local match, check if query is a specific tender identifier or portal URL,
        # and dispatch the universal scraper intake!
        target_ident = None
        if raw_prompt and (raw_prompt.startswith("http://") or raw_prompt.startswith("https://")):
            target_ident = raw_prompt.strip()
        elif filters.tender_number:
            target_ident = filters.tender_number.strip()
        elif filters.query and (filters.query.startswith("http://") or filters.query.startswith("https://")):
            target_ident = filters.query.strip()

        if total_count == 0 and target_ident:
            try:
                from backend.apps.tenders.services import TenderService
                service = TenderService(storage=self.storage)
                intake_res = service.intake_tender(identifier=target_ident, org_id="org_default")
                if intake_res.get("success"):
                    tender_id = intake_res.get("tender_id")
                    new_tender = self.storage.get_tender(tender_id, mode="skim")
                    if new_tender:
                        return {
                            "success": True,
                            "applied_filters": filters.model_dump(),
                            "total_matches": 1,
                            "page": 1,
                            "limit": filters.limit,
                            "source": "live_scraper_intake",
                            "results": [new_tender],
                        }
            except Exception as e:
                logger.error("Scraper intake fallback failed for %s: %s", target_ident, e)

        # 3. If no local matches, automatically trigger live procurement portal search!
        if total_count == 0 and self.live_search_engine:
            logger.info("No local match found. Dispatching live portal search for filters %s", filters.model_dump())
            live_tenders = self.live_search_engine.search_live(
                query=filters.tender_number or filters.query,
                state=filters.state,
                category=filters.category,
                city=filters.city_or_district,
                raw_prompt=raw_prompt or filters.tender_number,
                limit=filters.limit,
            )
            if live_tenders:
                return {
                    "success": True,
                    "applied_filters": filters.model_dump(),
                    "total_matches": len(live_tenders),
                    "page": filters.page,
                    "limit": filters.limit,
                    "source": "live_portal_discovery",
                    "results": live_tenders,
                }

        # 2. Concurrently enrich candidate tenders missing financial / preview details from the eye button
        if self.live_search_engine and local_results:
            missing = [
                t for t in local_results
                if t.get("estimated_value_inr") is None
                and ("eproc2.bihar.gov.in" in (t.get("portal") or "") or "BIH/EPROC2/" in str(t.get("tender_number") or ""))
            ]
            if missing:
                from concurrent.futures import ThreadPoolExecutor
                def _enrich_worker(t):
                    try:
                        prev = self.live_search_engine.fetch_tender_preview(t)
                        if prev:
                            if prev.get("estimated_value_inr") is not None:
                                t["estimated_value_inr"] = prev["estimated_value_inr"]
                            if prev.get("emd_amount_inr") is not None:
                                t["emd_amount_inr"] = prev["emd_amount_inr"]
                            if prev.get("dealing_officer"):
                                t["dealing_officer"] = prev["dealing_officer"]
                            if prev.get("tender_fee_inr") is not None:
                                t["tender_fee_inr"] = prev["tender_fee_inr"]
                            if prev.get("processing_fee_inr") is not None:
                                t["processing_fee_inr"] = prev["processing_fee_inr"]
                            if prev.get("mandatory_documents"):
                                t["mandatory_documents"] = prev["mandatory_documents"]
                            if prev.get("attachments"):
                                t["attachments"] = prev["attachments"]
                                t["nit_attachment"] = prev.get("nit_attachment")
                                t["boq_attachment"] = prev.get("boq_attachment")
                            
                            self.storage.save_tender_and_snapshot(
                                org_id="org_default",
                                tender_number=t["tender_number"],
                                tender_title=t["title"],
                                source_url=t.get("source_url") or "",
                                buyer_name=t.get("buyer_name"),
                                submission_deadline=t.get("submission_deadline"),
                                estimated_value_inr=t.get("estimated_value_inr"),
                                extracted_data=t,
                                raw_text_payload=json.dumps(t, default=str),
                                tender_id=t["tender_id"],
                                state=t.get("state"),
                                category=t.get("category"),
                                portal=t.get("portal"),
                                tenure_months=t.get("tenure_months"),
                                emd_amount_inr=t.get("emd_amount_inr"),
                                location=t.get("state"),
                            )
                    except Exception as e:
                        logger.debug("Failed to enrich tender %s: %s", t.get("tender_number"), e)

                with ThreadPoolExecutor(max_workers=min(len(missing), 8)) as ex:
                    list(ex.map(_enrich_worker, missing))

        return {
            "success": True,
            "applied_filters": filters.model_dump(),
            "total_matches": total_count,
            "page": filters.page,
            "limit": filters.limit,
            "source": "local_index",
            "results": local_results,
        }

    def search_by_prompt(self, prompt: str) -> Dict[str, Any]:
        """
        End-to-end natural language search:
        1. Parses prompt to structured filters using LLM with deterministic fallback.
        2. Executes multi-criteria search with live portal discovery.
        3. Returns ranked tenders.
        """
        parsed_filters = QueryParser.parse(prompt, llm_adapter=self.llm_adapter)
        logger.info("Parsed prompt '%s' to filters: %s", prompt, parsed_filters.model_dump())
        res = self.search(parsed_filters, raw_prompt=prompt)
        res["interpreted_prompt"] = prompt
        return res

    def get_tender(self, identifier: str, mode: str = "skim") -> Optional[Dict[str, Any]]:
        """
        Retrieves tender by tender_id or external tender_number.
        Supports two viewing modes:
        - 'skim': Fast high-level overview (financials, buyer, deadline, tenure, status)
        - 'detailed': Complete breakdown including parsed PDF clauses, page citations, and rule pack.
        """
        from backend.apps.tenders.services import TenderService

        is_direct_pdf = identifier.endswith(".pdf") or (os.path.exists(identifier) and not os.path.isdir(identifier))
        if is_direct_pdf:
            service = TenderService(storage=self.storage)
            intake_res = service.intake_tender_pdf(identifier)
            if intake_res.get("success"):
                tender = self.storage.get_tender(intake_res["tender_id"], mode=mode)
                if tender and mode == "detailed":
                    tender["rule_pack"] = intake_res.get("rule_pack")
            else:
                tender = None
        else:
            tender = self.storage.get_tender(identifier, mode=mode)

        # If tender lacks rich preview details (e.g. from raw initial index), fetch them via portal preview
        if tender and self.live_search_engine and not is_direct_pdf:
            portal = (tender.get("portal") or "").lower()
            t_num = str(tender.get("tender_number") or "")
            if ("eproc2.bihar.gov.in" in portal or "BIH/EPROC2/" in t_num) and (
                tender.get("estimated_value_inr") is None
                or tender.get("emd_amount_inr") is None
                or not tender.get("mandatory_documents")
                or tender.get("dealing_officer") is None
                or tender.get("tender_fee_inr") is None
            ):
                preview = self.live_search_engine.fetch_tender_preview(tender)
                if preview:
                    val_inr = preview.get("estimated_value_inr")
                    emd_inr = preview.get("emd_amount_inr")
                    dealing_officer = preview.get("dealing_officer")
                    if val_inr is not None:
                        tender["estimated_value_inr"] = val_inr
                    if emd_inr is not None:
                        tender["emd_amount_inr"] = emd_inr
                    if dealing_officer:
                        tender["dealing_officer"] = dealing_officer
                    if preview.get("org_hierarchy"):
                        tender["org_hierarchy"] = preview["org_hierarchy"]
                    if preview.get("tender_fee_inr") is not None:
                        tender["tender_fee_inr"] = preview["tender_fee_inr"]
                    if preview.get("processing_fee_inr") is not None:
                        tender["processing_fee_inr"] = preview["processing_fee_inr"]
                    if preview.get("mandatory_documents"):
                        tender["mandatory_documents"] = preview["mandatory_documents"]
                    if preview.get("attachments"):
                        tender["attachments"] = preview["attachments"]
                        tender["nit_attachment"] = preview.get("nit_attachment")
                        tender["boq_attachment"] = preview.get("boq_attachment")
                    if preview.get("preview_details"):
                        tender["preview_details"] = preview["preview_details"]

                    # Persist enriched preview back to storage
                    self.storage.save_tender_and_snapshot(
                        org_id="org_default",
                        tender_number=tender["tender_number"],
                        tender_title=tender["title"],
                        source_url=tender.get("source_url") or "",
                        buyer_name=tender.get("buyer_name"),
                        submission_deadline=tender.get("submission_deadline"),
                        estimated_value_inr=tender["estimated_value_inr"],
                        extracted_data=tender,
                        raw_text_payload=json.dumps(tender, default=str),
                        tender_id=tender["tender_id"],
                        state=tender.get("state"),
                        category=tender.get("category"),
                        portal=tender.get("portal"),
                        tenure_months=tender.get("tenure_months"),
                        emd_amount_inr=tender["emd_amount_inr"],
                        location=tender.get("state"),
                    )

        # If detailed mode requested and no PDF has been parsed yet, robustly acquire & parse it
        if mode == "detailed" and not is_direct_pdf:
            if not tender:
                service = TenderService(storage=self.storage)
                intake_res = service.intake_tender(identifier)
                if intake_res.get("success"):
                    tender = self.storage.get_tender(intake_res["tender_id"], mode="detailed")
                    if tender:
                        tender["rule_pack"] = intake_res.get("rule_pack")

            # If tender exists but has no parsed clauses/pages, robustly acquire and parse PDF
            ext = tender.get("extraction") if tender else None
            has_deep_clauses = isinstance(ext, dict) and (
                bool(ext.get("verbatim_clauses")) or ext.get("total_pages") is not None
            )
            if tender and (tender.get("pdf_status") != "PARSED" or not has_deep_clauses):
                    from backend.services.pdf_resolver import TenderPDFResolver
                    resolver = TenderPDFResolver(storage=self.storage)
                    resolved_pdf = resolver.resolve_and_acquire_pdf(tender)
                    if resolved_pdf:
                        service = TenderService(storage=self.storage)
                        intake_res = service.intake_tender_pdf(
                            resolved_pdf,
                            tender_id=tender.get("tender_id"),
                        )
                        if intake_res.get("success"):
                            tender = self.storage.get_tender(tender["tender_id"], mode="detailed")
                            if tender:
                                tender["rule_pack"] = intake_res.get("rule_pack")

            if tender and tender.get("has_pdf_document") and "rule_pack" not in tender:
                service = TenderService(storage=self.storage)
                rule_pack = service.get_rule_pack_by_tender_id(tender["tender_id"])
                if rule_pack:
                    tender["rule_pack"] = rule_pack.model_dump()

        if tender:
            from backend.engine.schema import TenderPDFExtractionResult
            tender["json_schema"] = TenderPDFExtractionResult.get_json_schema()

            # Synchronize all eye-button preview details into extraction dict
            if isinstance(tender.get("extraction"), dict):
                for k in (
                    "estimated_value_inr", "emd_amount_inr", "tender_fee_inr",
                    "processing_fee_inr", "dealing_officer", "org_hierarchy",
                    "mandatory_documents", "attachments", "nit_attachment",
                    "boq_attachment", "preview_details"
                ):
                    if tender.get(k) is not None and (k not in tender["extraction"] or tender["extraction"][k] is None):
                        tender["extraction"][k] = tender[k]

        return tender

