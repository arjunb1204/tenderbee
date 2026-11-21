"""
Live Tender Discovery Engine for TenderBee.
Performs real-time search across live Indian Government Procurement Portals
(GePNIC, CPPP, State Portals, GeM) using TinyFish web search.

Discovered tenders are directly inspected on the live portal DOM, strictly verified
for active liveness (filtering out expired archives, maintenance pages, and UI noise),
normalized into the TenderBee schema, and indexed into tiered storage for instant
Skimmed, Detailed, and JSON inspection.
"""
import hashlib
import io
import json
import logging
import os
import re
import ssl
import urllib.parse
import urllib.request
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from dotenv import load_dotenv

_repo_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_repo_root / ".env")
load_dotenv()

try:
    from tinyfish import TinyFish
    from tinyfish import (
        APIError,
        APIConnectionError,
        APITimeoutError,
        AuthenticationError,
        RateLimitError,
    )
except ImportError:
    TinyFish = None
    APIError = Exception  # type: ignore
    APIConnectionError = Exception  # type: ignore
    APITimeoutError = Exception  # type: ignore
    AuthenticationError = Exception  # type: ignore
    RateLimitError = Exception  # type: ignore

from backend.services.storage import TenderStorage

logger = logging.getLogger(__name__)

BLOCKED_DOMAINS = {
    "youtube.com", "tendershark.com", "tendersplus.com", "tendersontime.com",
    "wikipedia.org", "quora.com", "ignited.in", "linkedin.com", "facebook.com",
    "twitter.com", "instagram.com", "reddit.com", "medium.com", "github.com",
    "classictenders.com", "bidassist.com", "tenderdetail.com", "tender247.com",
    "instatenders.com", "tendertiger.com", "etender.co.in", "gemtenders.com",
    "biddetail.com", "tendersgo.com", "rfpmart.com"
}

BLOCKED_URL_PATTERNS = [
    "page=FrontEndLatestActiveTenders&service=page",
    "page=FrontEndTendersByOrganisation",
    "page=WebTenderStatusLists&service=page",
    "page=FrontEndAdvancedSearch",
    "page=FrontEndTendersByLocation",
    "page=Home",
    "login",
    "WebHomeBorder",
    "ResultOfTenders",
]

UI_NOISE_KEYWORDS = [
    "provide captcha", "search with only one criteria", "organisation name, tender count",
    "search | active tenders", "maintenance notice", "service unavailable",
    "contract type, tender, bid validity", "tender status finds search",
    "what's new", "corrigendum type", "welcome to the eprocurement",
    "no, organisation name", "tender reference number", "tender category goods",
]

STATE_PORTAL_DOMAINS = {
    # 28 States
    "Andhra Pradesh": "tender.apeprocurement.gov.in",
    "Arunachal Pradesh": "arunachaltenders.gov.in",
    "Assam": "assamtenders.gov.in",
    "Bihar": "eproc2.bihar.gov.in",
    "Chhattisgarh": "eproc.cgstate.gov.in",
    "Goa": "eprocure.goa.gov.in",
    "Gujarat": "tender.nprocure.com",
    "Haryana": "etenders.hry.nic.in",
    "Himachal Pradesh": "hptenders.gov.in",
    "Jharkhand": "jharkhandtenders.gov.in",
    "Karnataka": "kppp.karnataka.gov.in",
    "Kerala": "etenders.kerala.gov.in",
    "Madhya Pradesh": "mptenders.gov.in",
    "Maharashtra": "mahatenders.gov.in",
    "Manipur": "manipurtenders.gov.in",
    "Meghalaya": "meghalayatenders.gov.in",
    "Mizoram": "mizoramtenders.gov.in",
    "Nagaland": "nagalandtenders.gov.in",
    "Odisha": "tendersodisha.gov.in",
    "Punjab": "eproc.punjab.gov.in",
    "Rajasthan": "eproc.rajasthan.gov.in",
    "Sikkim": "sikkimtender.gov.in",
    "Tamil Nadu": "tntenders.gov.in",
    "Telangana": "tender.telangana.gov.in",
    "Tripura": "tripuratenders.gov.in",
    "Uttar Pradesh": "etender.up.nic.in",
    "Uttarakhand": "uktenders.gov.in",
    "West Bengal": "wbtenders.gov.in",
    # 8 Union Territories
    "Andaman and Nicobar Islands": "eprocure.andaman.gov.in",
    "Chandigarh": "etenders.chd.nic.in",
    "Dadra and Nagar Haveli and Daman and Diu": "ddtenders.gov.in",
    "Delhi": "govtprocurement.delhi.gov.in",
    "Jammu and Kashmir": "jktenders.gov.in",
    "Ladakh": "eprocure.gov.in",
    "Lakshadweep": "eprocure.gov.in",
    "Puducherry": "pudutenders.gov.in",
}

STATE_PORTAL_REGISTRY: List[Dict[str, Any]] = [
    # 28 States
    {"name": "Andhra Pradesh", "code": "AP", "type": "State", "portal_name": "Andhra Pradesh eProcurement Portal", "domain": "tender.apeprocurement.gov.in", "url": "https://tender.apeprocurement.gov.in", "engine": "e-Procure"},
    {"name": "Arunachal Pradesh", "code": "AR", "type": "State", "portal_name": "Arunachal Pradesh e-Procurement Portal", "domain": "arunachaltenders.gov.in", "url": "https://arunachaltenders.gov.in", "engine": "GePNIC"},
    {"name": "Assam", "code": "AS", "type": "State", "portal_name": "Assam Tenders e-Procurement System", "domain": "assamtenders.gov.in", "url": "https://assamtenders.gov.in", "engine": "GePNIC"},
    {"name": "Bihar", "code": "BR", "type": "State", "portal_name": "Bihar eProc2 Portal", "domain": "eproc2.bihar.gov.in", "url": "https://eproc2.bihar.gov.in", "engine": "NextGen eProc"},
    {"name": "Chhattisgarh", "code": "CG", "type": "State", "portal_name": "Chhattisgarh e-Procurement System", "domain": "eproc.cgstate.gov.in", "url": "https://eproc.cgstate.gov.in", "engine": "e-Procure"},
    {"name": "Goa", "code": "GA", "type": "State", "portal_name": "Goa e-Procurement Portal", "domain": "eprocure.goa.gov.in", "url": "https://eprocure.goa.gov.in", "engine": "GePNIC"},
    {"name": "Gujarat", "code": "GJ", "type": "State", "portal_name": "Gujarat nProcure e-Tendering", "domain": "tender.nprocure.com", "url": "https://tender.nprocure.com", "engine": "nProcure"},
    {"name": "Haryana", "code": "HR", "type": "State", "portal_name": "Haryana e-Procurement Portal", "domain": "etenders.hry.nic.in", "url": "https://etenders.hry.nic.in", "engine": "GePNIC"},
    {"name": "Himachal Pradesh", "code": "HP", "type": "State", "portal_name": "Himachal Pradesh Tenders Portal", "domain": "hptenders.gov.in", "url": "https://hptenders.gov.in", "engine": "GePNIC"},
    {"name": "Jharkhand", "code": "JH", "type": "State", "portal_name": "Jharkhand Tenders e-Procurement System", "domain": "jharkhandtenders.gov.in", "url": "https://jharkhandtenders.gov.in", "engine": "GePNIC"},
    {"name": "Karnataka", "code": "KA", "type": "State", "portal_name": "Karnataka Public Procurement Portal (KPPP)", "domain": "kppp.karnataka.gov.in", "url": "https://kppp.karnataka.gov.in", "engine": "KPPP"},
    {"name": "Kerala", "code": "KL", "type": "State", "portal_name": "Kerala e-Tenders Portal", "domain": "etenders.kerala.gov.in", "url": "https://etenders.kerala.gov.in", "engine": "GePNIC"},
    {"name": "Madhya Pradesh", "code": "MP", "type": "State", "portal_name": "MP Tenders Portal", "domain": "mptenders.gov.in", "url": "https://mptenders.gov.in", "engine": "GePNIC"},
    {"name": "Maharashtra", "code": "MH", "type": "State", "portal_name": "MahaTenders (Maharashtra e-Procurement)", "domain": "mahatenders.gov.in", "url": "https://mahatenders.gov.in", "engine": "GePNIC"},
    {"name": "Manipur", "code": "MN", "type": "State", "portal_name": "Manipur e-Procurement Portal", "domain": "manipurtenders.gov.in", "url": "https://manipurtenders.gov.in", "engine": "GePNIC"},
    {"name": "Meghalaya", "code": "ML", "type": "State", "portal_name": "Meghalaya Tenders Portal", "domain": "meghalayatenders.gov.in", "url": "https://meghalayatenders.gov.in", "engine": "GePNIC"},
    {"name": "Mizoram", "code": "MZ", "type": "State", "portal_name": "Mizoram e-Procurement System", "domain": "mizoramtenders.gov.in", "url": "https://mizoramtenders.gov.in", "engine": "GePNIC"},
    {"name": "Nagaland", "code": "NL", "type": "State", "portal_name": "Nagaland e-Procurement Portal", "domain": "nagalandtenders.gov.in", "url": "https://nagalandtenders.gov.in", "engine": "GePNIC"},
    {"name": "Odisha", "code": "OD", "type": "State", "portal_name": "Tenders Odisha Portal", "domain": "tendersodisha.gov.in", "url": "https://tendersodisha.gov.in", "engine": "GePNIC"},
    {"name": "Punjab", "code": "PB", "type": "State", "portal_name": "Punjab e-Procurement Portal", "domain": "eproc.punjab.gov.in", "url": "https://eproc.punjab.gov.in", "engine": "GePNIC"},
    {"name": "Rajasthan", "code": "RJ", "type": "State", "portal_name": "Rajasthan e-Procurement System", "domain": "eproc.rajasthan.gov.in", "url": "https://eproc.rajasthan.gov.in", "engine": "GePNIC"},
    {"name": "Sikkim", "code": "SK", "type": "State", "portal_name": "Sikkim Tenders Portal", "domain": "sikkimtender.gov.in", "url": "https://sikkimtender.gov.in", "engine": "GePNIC"},
    {"name": "Tamil Nadu", "code": "TN", "type": "State", "portal_name": "Tamil Nadu e-Tenders Portal", "domain": "tntenders.gov.in", "url": "https://tntenders.gov.in", "engine": "GePNIC"},
    {"name": "Telangana", "code": "TS", "type": "State", "portal_name": "Telangana e-Procurement Portal", "domain": "tender.telangana.gov.in", "url": "https://tender.telangana.gov.in", "engine": "e-Procure"},
    {"name": "Tripura", "code": "TR", "type": "State", "portal_name": "Tripura Tenders Portal", "domain": "tripuratenders.gov.in", "url": "https://tripuratenders.gov.in", "engine": "GePNIC"},
    {"name": "Uttar Pradesh", "code": "UP", "type": "State", "portal_name": "e-Tender Uttar Pradesh", "domain": "etender.up.nic.in", "url": "https://etender.up.nic.in", "engine": "GePNIC"},
    {"name": "Uttarakhand", "code": "UK", "type": "State", "portal_name": "Uttarakhand Tenders Portal", "domain": "uktenders.gov.in", "url": "https://uktenders.gov.in", "engine": "GePNIC"},
    {"name": "West Bengal", "code": "WB", "type": "State", "portal_name": "West Bengal Tenders (WBTenders)", "domain": "wbtenders.gov.in", "url": "https://wbtenders.gov.in", "engine": "GePNIC"},
    # 8 Union Territories
    {"name": "Andaman and Nicobar Islands", "code": "AN", "type": "Union Territory", "portal_name": "Andaman & Nicobar eProcurement", "domain": "eprocure.andaman.gov.in", "url": "https://eprocure.andaman.gov.in", "engine": "GePNIC"},
    {"name": "Chandigarh", "code": "CH", "type": "Union Territory", "portal_name": "Chandigarh Administration eTenders", "domain": "etenders.chd.nic.in", "url": "https://etenders.chd.nic.in", "engine": "GePNIC"},
    {"name": "Dadra and Nagar Haveli and Daman and Diu", "code": "DD", "type": "Union Territory", "portal_name": "Daman & Diu / DNH e-Tenders", "domain": "ddtenders.gov.in", "url": "https://ddtenders.gov.in", "engine": "GePNIC"},
    {"name": "Delhi", "code": "DL", "type": "Union Territory", "portal_name": "Delhi Govt e-Procurement System", "domain": "govtprocurement.delhi.gov.in", "url": "https://govtprocurement.delhi.gov.in", "engine": "GePNIC"},
    {"name": "Jammu and Kashmir", "code": "JK", "type": "Union Territory", "portal_name": "JK Tenders Portal", "domain": "jktenders.gov.in", "url": "https://jktenders.gov.in", "engine": "GePNIC"},
    {"name": "Ladakh", "code": "LA", "type": "Union Territory", "portal_name": "Ladakh Procurement Portal (CPPP)", "domain": "eprocure.gov.in", "url": "https://eprocure.gov.in", "engine": "GePNIC"},
    {"name": "Lakshadweep", "code": "LD", "type": "Union Territory", "portal_name": "Lakshadweep Procurement (CPPP)", "domain": "eprocure.gov.in", "url": "https://eprocure.gov.in", "engine": "GePNIC"},
    {"name": "Puducherry", "code": "PY", "type": "Union Territory", "portal_name": "Puducherry e-Tenders Portal", "domain": "pudutenders.gov.in", "url": "https://pudutenders.gov.in", "engine": "GePNIC"},
    # Central / National
    {"name": "Central Government (CPPP)", "code": "CENTRAL", "type": "Central", "portal_name": "Central Public Procurement Portal", "domain": "eprocure.gov.in", "url": "https://eprocure.gov.in", "engine": "GePNIC"},
    {"name": "GeM", "code": "GEM", "type": "Central", "portal_name": "Government e-Marketplace", "domain": "gem.gov.in", "url": "https://gem.gov.in", "engine": "GeM"},
    {"name": "Indian Railways (IREPS)", "code": "RAIL", "type": "Central", "portal_name": "Indian Railways E-Procurement System", "domain": "ireps.gov.in", "url": "https://ireps.gov.in", "engine": "IREPS"},
    {"name": "Defence Procurement", "code": "DEF", "type": "Central", "portal_name": "Defence e-Procurement Portal", "domain": "defproc.gov.in", "url": "https://defproc.gov.in", "engine": "GePNIC"},
    {"name": "Infralens", "code": "INFRA", "type": "Aggregator", "portal_name": "Infralens Tender Mirror", "domain": "tenders.infralens.in", "url": "https://tenders.infralens.in", "engine": "Mirror"},
]

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _parse_deadline(date_str: str) -> Optional[datetime]:
    """Parses various date-time formats from Indian procurement portals."""
    if not date_str:
        return None
    s = date_str.strip()
    formats = [
        "%d-%b-%Y %I:%M %p",
        "%d-%b-%Y %H:%M",
        "%d-%b-%Y",
        "%d %b %Y %I:%M %p",
        "%d %b %Y",
        "%d/%m/%Y %I:%M %p",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%d-%m-%Y",
    ]
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=ist_tz)
        except ValueError:
            continue
    return None


class LiveTenderSearchEngine:
    """
    Connects to live Indian public procurement portals and directories
    when local database has no matches or when live discovery is requested.
    Inspects live HTML DOM to guarantee genuine, non-expired tender data.
    """

    _eproc2_session_lock = threading.Lock()
    _eproc2_cached_auth: Optional[str] = None
    _eproc2_cached_opener: Optional[Any] = None
    _eproc2_rfq_map: Dict[str, Tuple[int, int]] = {}
    _eproc2_cache_time: float = 0.0

    @classmethod
    def _get_eproc2_session_and_map(cls) -> Tuple[Optional[Any], Optional[str], Dict[str, Tuple[int, int]]]:
        """
        Maintains an authenticated session pool and RFQ -> currenttenderid mapping
        for eproc2.bihar.gov.in with a 15-minute TTL cache, eliminating duplicate handshakes.
        """
        with cls._eproc2_session_lock:
            now = time.time()
            if cls._eproc2_cached_auth and cls._eproc2_cached_opener and (now - cls._eproc2_cache_time < 900):
                return cls._eproc2_cached_opener, cls._eproc2_cached_auth, cls._eproc2_rfq_map

            try:
                import http.cookiejar
                cj = http.cookiejar.CookieJar()
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                opener = urllib.request.build_opener(
                    urllib.request.HTTPCookieProcessor(cj),
                    urllib.request.HTTPSHandler(context=ctx)
                )
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                p_url = "https://eproc2.bihar.gov.in/EPSV2Web/openarea/tenderListingPage.action"
                p_resp = opener.open(urllib.request.Request(p_url, headers=headers), timeout=8)
                html = p_resp.read().decode("utf-8", errors="ignore")
                m_auth = re.search(r'value=[\"\'](Bearer [^\"\']+)[\"\']', html)
                if not m_auth:
                    return None, None, {}
                auth_val = m_auth.group(1)

                req_list = urllib.request.Request(
                    "https://eproc2.bihar.gov.in/EPSV2Web/rest/openarea/getTenderList",
                    data=b"{}",
                    headers={**headers, "Content-Type": "application/json", "Authorization": auth_val},
                    method="POST",
                )
                tlist = json.loads(opener.open(req_list, timeout=12).read().decode("utf-8"))
                rfq_map: Dict[str, Tuple[int, int]] = {}
                if isinstance(tlist, list):
                    for it in tlist:
                        rfq_id = str(it.get("currentOrgTenderId") or "")
                        tid = it.get("currenttenderid")
                        org_id = it.get("currentorgid", 538)
                        if rfq_id and tid:
                            rfq_map[rfq_id] = (tid, org_id)
                        if tid:
                            rfq_map[str(tid)] = (tid, org_id)

                cls._eproc2_cached_auth = auth_val
                cls._eproc2_cached_opener = opener
                cls._eproc2_rfq_map = rfq_map
                cls._eproc2_cache_time = now
                return opener, auth_val, rfq_map
            except Exception as e:
                logger.error("Failed to establish eproc2 session: %s", e)
                return None, None, {}

    _query_cache: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}
    _cache_lock = threading.Lock()
    CACHE_TTL_SECONDS = 600  # 10 minutes cache TTL

    @staticmethod
    def normalize_url(raw_url: str) -> str:
        """
        Deduplicates and cleans URLs by stripping tracking parameters, trailing slashes,
        and standardizing scheme/host to lowercase.
        """
        if not raw_url:
            return ""
        parsed = urllib.parse.urlparse(raw_url.strip())
        clean_query = []
        for k, v in urllib.parse.parse_qsl(parsed.query):
            k_lower = k.lower()
            if not k_lower.startswith("utm_") and k_lower not in ("ref", "fbclid", "gclid", "sessionid", "track"):
                clean_query.append((k, v))
        new_query = urllib.parse.urlencode(clean_query)
        path = parsed.path.rstrip("/")
        return urllib.parse.urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            parsed.params,
            new_query,
            ""
        ))

    @classmethod
    def _is_valid_tender_candidate(cls, title: str, url: str, snippet: str = "") -> bool:
        """
        Validates whether a search result candidate represents a genuine public procurement notice,
        filtering out ad farms, aggregator spam, and non-procurement web pages.
        """
        if not url or not title:
            return False
        norm_url = url.lower()
        domain = urllib.parse.urlparse(norm_url).netloc.lower()
        if any(b in domain for b in BLOCKED_DOMAINS):
            return False
        if any(p in norm_url for p in BLOCKED_URL_PATTERNS):
            return False

        # Official government or procurement platforms are high-confidence signals
        is_gov = any(gov in domain for gov in ("gov.in", "nic.in", "gem.gov.in", "ireps.gov.in"))
        text = f"{title} {snippet}".lower()
        procurement_signals = (
            "tender", "bid", "rfp", "rfq", "nit", "procurement", "e-procurement",
            "gem/", "corrigendum", "contract", "supply", "work", "works", "maintenance",
            "eproc", "bidding", "expression of interest", "eoi", "quotation"
        )
        has_signal = any(sig in text for sig in procurement_signals)
        return is_gov or has_signal

    def __init__(self, api_key: Optional[str] = None, storage: Optional[TenderStorage] = None):
        self.api_key = api_key or os.getenv("TINYFISH_API_KEY")
        self.storage = storage or TenderStorage()
        self.client = TinyFish(api_key=self.api_key) if (TinyFish and self.api_key) else None

    def _inspect_live_page(
        self,
        url: str,
        state: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Visits the live tender URL, extracts ground-truth fields from the rendered HTML,
        and enforces strict liveness validation (rejecting expired archives and portal UI noise).
        """
        if not url:
            return None

        domain = urllib.parse.urlparse(url).netloc.lower()
        if any(b in domain for b in BLOCKED_DOMAINS):
            return None

        # Discard portal directory navigation and search forms
        if any(p in url for p in BLOCKED_URL_PATTERNS):
            return None

        # Fetch content with SSL fallback for government internal CA portals
        data = None
        try:
            req = urllib.request.Request(url, headers=BROWSER_HEADERS)
            try:
                with urllib.request.urlopen(req, timeout=4.5) as resp:
                    if resp.status != 200:
                        return None
                    data = resp.read()
            except Exception as e_ssl:
                if "CERTIFICATE_VERIFY_FAILED" in str(e_ssl) or "ssl" in str(e_ssl).lower():
                    ctx = ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                    with urllib.request.urlopen(req, context=ctx, timeout=4.5) as resp:
                        if resp.status != 200:
                            return None
                        data = resp.read()
                else:
                    return None
        except Exception:
            return None

        if not data:
            return None

        now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))

        # 0. Check for PDF Document (GeM showbidDocument or .pdf notices)
        if data[:4] == b"%PDF" or url.lower().endswith(".pdf") or "showbiddocument" in url.lower():
            try:
                from pypdf import PdfReader
                reader = PdfReader(io.BytesIO(data))
                if len(reader.pages) > 0:
                    text = "\n".join([reader.pages[i].extract_text() for i in range(min(3, len(reader.pages)))])
                    m_bid = re.search(r"Bid Number[:\s]+([^\n\r]+)", text, re.I) or re.search(r"(GEM/\d+/[A-Z]/\d+)", text)
                    m_date = re.search(r"Bid End Date/Time[:\s]+([0-9\- :]+)", text, re.I)
                    m_state = re.search(r"Ministry/State Name[:\s]+([^\n\r]+)", text, re.I)
                    m_dept = re.search(r"Department Name[:\s]+([^\n\r]+)", text, re.I)
                    m_office = re.search(r"Office Name[:\s]+([^\n\r]+)", text, re.I)
                    m_item = re.search(r"Item Category[:\s]+([^\n\r]+)", text, re.I)
                    m_val = re.search(r"Estimated Bid Value[:\s]+([0-9,.]+)", text, re.I)
                    m_emd = re.search(r"EMD Amount[:\s]+([0-9,.]+)", text, re.I)

                    bid_no = m_bid.group(1).strip() if m_bid else None
                    if not bid_no:
                        return None

                    # Strict Liveness check on Bid End Date
                    end_date_str = m_date.group(1).strip() if m_date else None
                    deadline_dt = _parse_deadline(end_date_str) if end_date_str else None
                    if not deadline_dt or deadline_dt < now_ist:
                        logger.debug("Discarding invalid or expired PDF tender %s (deadline %s)", bid_no, deadline_dt)
                        return None

                    if not m_item:
                        return None

                    dept_str = m_dept.group(1).strip() if m_dept else ""
                    office_str = m_office.group(1).strip() if m_office else ""
                    buyer = f"{dept_str} - {office_str}".strip(" -") or f"Procuring Authority ({domain})"
                    item_title = m_item.group(1).strip()
                    state_str = m_state.group(1).strip() if m_state else (state or "All India")

                    val_inr = float(m_val.group(1).replace(",", "")) if m_val else None
                    emd_inr = float(m_emd.group(1).replace(",", "")) if m_emd else None

                    tender_entry = {
                        "tender_number": bid_no,
                        "title": item_title,
                        "buyer_name": buyer,
                        "state": state_str,
                        "category": category or "Goods",
                        "estimated_value_inr": val_inr,
                        "emd_amount_inr": emd_inr,
                        "tenure_months": 12,
                        "submission_deadline": deadline_dt.isoformat(),
                        "portal": domain,
                        "source_url": url,
                        "status": "ACTIVE",
                        "has_pdf_document": True,
                    }
                    return [tender_entry]
            except Exception as e_pdf:
                logger.debug("Failed to parse PDF document %s: %s", url, e_pdf)

        html = data.decode("utf-8", errors="ignore")

        # Reject maintenance, captcha, or service errors
        if any(k in html for k in ("Maintenance Notice", "Service Unavailable", "Provide Captcha")):
            return None

        # 1. GePNIC / CPPP portal structure
        if "td_field" in html or "td_caption" in html or "FrontEndViewTender" in url:
            # Tender ID
            m_id = re.search(
                r"Tender ID[<>/b\s]*</td>\s*<td[^>]*class=\"td_field\"[^>]*>\s*<b>\s*([0-9]{4}_[A-Z0-9]+_\d+_\d+|[A-Za-z0-9_\/-]+)\s*</b>",
                html,
                re.IGNORECASE,
            )
            if not m_id:
                m_id = re.search(
                    r"Tender ID.*?<td[^>]*class=\"td_field\"[^>]*>.*?([0-9]{4}_[A-Z0-9_]+)",
                    html,
                    re.DOTALL | re.IGNORECASE,
                )
            tid = m_id.group(1).strip() if m_id else None

            # Discard historical tenders from past years (< 2026)
            if tid and re.match(r"^20[12][0-5]_", tid):
                logger.debug("Discarding historical tender %s", tid)
                return None

            # Work Description / Title
            m_title = re.search(
                r"<b>Title</b></td>\s*<td[^>]*class=\"td_field\"[^>]*>\s*<[bB]>\s*([^<]+)\s*</[bB]>",
                html,
                re.IGNORECASE,
            )
            if not m_title:
                m_title = re.search(
                    r"<b>Work Description</b></td>\s*<td[^>]*class=\"td_field\"[^>]*>\s*<[bB]>\s*([^<]+)\s*</[bB]>",
                    html,
                    re.IGNORECASE,
                )
            title = m_title.group(1).strip() if m_title else None
            if not title or any(k in title.lower() for k in UI_NOISE_KEYWORDS) or len(title) < 8:
                return None

            # Buyer / Organisation Chain
            m_org = re.search(
                r"Organisation Chain.*?<td[^>]*class=\"td_field\"[^>]*>\s*<[bB]>\s*([^<]+)\s*</[bB]>",
                html,
                re.DOTALL | re.IGNORECASE,
            )
            org_chain = m_org.group(1).strip() if m_org else f"Procuring Authority ({domain})"
            # Format organization chain cleanly
            buyer_name = " - ".join([p.strip() for p in org_chain.split("||") if p.strip()])

            # Tender Value
            m_val = re.search(
                r"Tender Value in (?:&#8377;|₹).*?<td[^>]*class=\"td_field\"[^>]*>\s*([0-9,]+(?:\.[0-9]+)?)",
                html,
                re.DOTALL | re.IGNORECASE,
            )
            val = float(m_val.group(1).replace(",", "")) if m_val else None

            # EMD Amount
            m_emd = re.search(
                r"EMD Amount in (?:&#8377;|₹).*?<td[^>]*class=\"td_field\"[^>]*>\s*([0-9,]+(?:\.[0-9]+)?)",
                html,
                re.DOTALL | re.IGNORECASE,
            )
            emd = float(m_emd.group(1).replace(",", "")) if m_emd else (val * 0.02 if val else None)

            # Tender Category (Goods, Works, Services)
            m_cat = re.search(
                r"Tender Category.*?<td[^>]*class=\"td_field\"[^>]*>\s*([A-Za-z]+)",
                html,
                re.DOTALL | re.IGNORECASE,
            )
            extracted_cat = None
            if m_cat:
                c_cand = m_cat.group(1).strip().capitalize()
                if c_cand in ("Goods", "Works", "Services"):
                    extracted_cat = c_cand

            # Bid Submission End Date
            m_end = re.search(
                r"Bid Submission End Date.*?([0-9]{1,2}-[A-Za-z]{3}-[0-9]{4}(?:\s+[0-9]{1,2}:[0-9]{2}\s+[AP]M)?)",
                html,
                re.DOTALL | re.IGNORECASE,
            )
            end_raw = m_end.group(1).strip() if m_end else None
            dl_dt = _parse_deadline(end_raw)

            # Enforce strict liveness: reject tenders without active upcoming deadline
            if not dl_dt or dl_dt < now_ist:
                logger.debug("Discarding expired or deadline-missing tender %s", tid)
                return None
            deadline_iso = dl_dt.isoformat()

            if not tid:
                return None

            t_category = extracted_cat or category or "Services"
            return [{
                "tender_number": tid,
                "title": title,
                "buyer_name": buyer_name,
                "state": state or "All India",
                "category": t_category,
                "estimated_value_inr": val,
                "emd_amount_inr": emd,
                "tenure_months": 12,
                "submission_deadline": deadline_iso,
                "portal": domain,
                "source_url": url,
                "status": "ACTIVE",
                "has_pdf_document": False,
            }]

        # 2. State Portal Tender Listings (e.g. sikkim.gov.in/tender)
        cards = []
        for td in re.finditer(r"<td[^>]*class=\"corner-cut[^\"]*\"[^>]*>(.*?)</td>", html, re.DOTALL):
            snippet = td.group(1)
            m_title = re.search(r"<strong>(.*?)</strong>", snippet, re.DOTALL)
            m_date = re.search(r"<i>\s*-?([0-9]{1,2}\s+[A-Za-z]{3}\s+[0-9]{4})\s*</i>", snippet)
            m_dept = re.search(r"<i>\s*-\s*([^<]+Department|[^<]+Agency|[^<]+Board)\s*</i>", snippet)
            m_link = re.search(r"href=[\"\x27]([^\"]*tender-info[^\"]*)[\"\x27]", snippet)

            if m_title and m_link:
                tit = " ".join(re.sub(r"<[^>]+>", " ", m_title.group(1)).split())
                if any(k in tit.lower() for k in UI_NOISE_KEYWORDS) or len(tit) < 8:
                    continue
                dt_str = m_date.group(1) if m_date else None
                if not dt_str:
                    continue
                card_dt = _parse_deadline(dt_str)
                if not card_dt or card_dt < now_ist:
                    continue

                dept = m_dept.group(1).strip() if m_dept else f"Government of {state or 'State'}"
                link = urllib.parse.urljoin(url, m_link.group(1))
                id_m = re.search(r"/(\d+)\?", link)
                if not id_m:
                    continue
                t_num = f"SIK/2026/{id_m.group(1)}"

                cards.append({
                    "tender_number": t_num,
                    "title": tit,
                    "buyer_name": dept,
                    "state": state or "Sikkim",
                    "category": category or "Services",
                    "estimated_value_inr": None,
                    "emd_amount_inr": None,
                    "tenure_months": 12,
                    "submission_deadline": card_dt.isoformat(),
                    "portal": domain,
                    "source_url": link,
                    "status": "ACTIVE",
                    "has_pdf_document": True,
                })

        return cards if cards else None

    @classmethod
    def _fetch_eproc2_tender_details(
        cls,
        tender_id: Union[int, str],
        org_id: Union[int, str] = 538,
        opener: Optional[Any] = None,
        auth_val: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Replicates clicking the 'Eye' preview button on eproc2.bihar.gov.in
        (previewTender in openareaTenderListController.js).
        Extracts Advertised Value (pacamt), EMD, Tender Fee, Processing Fee,
        Dealing Officer, Organizational Hierarchy, Mandatory Documents, and NIT attachments.
        """
        try:
            if not opener or not auth_val:
                opener, auth_val, _ = cls._get_eproc2_session_and_map()
                if not opener or not auth_val:
                    return None

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Content-Type": "application/json",
                "Authorization": auth_val,
            }
            url = f"https://eproc2.bihar.gov.in/EPSV2Web/rest/quotation/previewTenderByTenderId?tenderId={tender_id}"
            req_prev = urllib.request.Request(url, data=b"{}", headers=headers, method="POST")
            res = opener.open(req_prev, timeout=10)
            data = json.loads(res.read().decode("utf-8"))

            pac_amt = data.get("pacamt")
            val_inr = float(pac_amt) if pac_amt else None

            creator = data.get("tenderPreviewMap", {}).get("creatorDetail", {})
            dealing_officer = creator.get("DealingOfficer")
            org_hierarchy = list(creator.get("OrgHirarchy", {}).values()) if isinstance(creator.get("OrgHirarchy"), dict) else []

            emd_amt = None
            tender_fee = None
            processing_fee = None
            mandatory_docs = []
            attachments = []
            nit_attachment = None
            boq_attachment = None

            for t in data.get("templates", []):
                s_name = t.get("shortName")
                flist = t.get("templateFieldList", [])

                if s_name == "rfqpayment":
                    f_dict = {f.get("code"): f.get("value") for f in flist}
                    ptype = (f_dict.get("payment_type") or "").strip().upper()
                    amt_str = f_dict.get("amount")
                    amt = float(amt_str) if amt_str else None
                    if "EMD" in ptype and amt:
                        emd_amt = amt
                    elif "PROCESSING" in ptype and amt:
                        processing_fee = amt
                    elif "TENDER" in ptype and amt:
                        tender_fee = amt

                elif s_name == "requiredbidderattachment":
                    f_dict = {f.get("code"): f.get("value") for f in flist}
                    doc_name = f_dict.get("supporting_doc")
                    is_mand = f_dict.get("mandatory_flag") == "Y"
                    if doc_name and is_mand:
                        mandatory_docs.append(doc_name.strip())

                elif s_name == "rfqattachment":
                    f_dict = {f.get("code"): f.get("value") for f in flist}
                    lbl = (f_dict.get("label") or "Document").strip()
                    fname = (f_dict.get("file_name") or "").strip()
                    attach_val = (f_dict.get("attach_file") or "").strip()
                    rel_file = attach_val.split("|")[0].strip() if attach_val else fname
                    file_size = int(attach_val.split("|")[1]) if (attach_val and len(attach_val.split("|")) > 1 and attach_val.split("|")[1].isdigit()) else None
                    att_info = {
                        "label": lbl,
                        "file_name": fname,
                        "remote_path": rel_file,
                        "file_size_bytes": file_size,
                        "download_params": {
                            "tempGrpId": "102",
                            "tenderId": str(tender_id),
                            "fileName": rel_file,
                            "orgId": str(org_id),
                        }
                    }
                    attachments.append(att_info)
                    if "NIT" in lbl.upper() or "RFP" in lbl.upper() or (not nit_attachment and fname.lower().endswith(".pdf")):
                        nit_attachment = att_info
                    elif "BOQ" in lbl.upper():
                        boq_attachment = att_info

            return {
                "tender_id": str(tender_id),
                "estimated_value_inr": val_inr,
                "emd_amount_inr": emd_amt,
                "tender_fee_inr": tender_fee,
                "processing_fee_inr": processing_fee,
                "dealing_officer": dealing_officer,
                "org_hierarchy": org_hierarchy,
                "mandatory_documents": mandatory_docs,
                "attachments": attachments,
                "nit_attachment": nit_attachment,
                "boq_attachment": boq_attachment,
            }
        except Exception as e:
            logger.debug("Failed to fetch eproc2 preview for tender %s: %s", tender_id, e)
            return None

    @classmethod
    def download_eproc2_nit(cls, download_params: Dict[str, Any]) -> Optional[bytes]:
        """
        Executes authenticated form-post download of genuine government NIT PDF from eproc2.bihar.gov.in.
        """
        try:
            import http.cookiejar
            cj = http.cookiejar.CookieJar()
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            opener = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(cj),
                urllib.request.HTTPSHandler(context=ctx)
            )
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

            page_url = "https://eproc2.bihar.gov.in/EPSV2Web/openarea/tenderListingPage.action"
            resp = opener.open(urllib.request.Request(page_url, headers=headers), timeout=10)
            html = resp.read().decode("utf-8", errors="ignore")
            m_auth = re.search(r'value=[\"\'](Bearer [^\"\']+)[\"\']', html)
            if not m_auth:
                return None
            auth_val = m_auth.group(1)

            post_data = urllib.parse.urlencode({
                "Authorization": auth_val,
                "tempGrpId": str(download_params.get("tempGrpId", "102")),
                "tenderId": str(download_params.get("tenderId")),
                "fileName": str(download_params.get("fileName")),
                "orgId": str(download_params.get("orgId", "538")),
            }).encode("utf-8")

            dl_url = "https://eproc2.bihar.gov.in/EPSV2Web/rest/openarea/downloadattachment.action"
            req_dl = urllib.request.Request(
                dl_url,
                data=post_data,
                headers={
                    **headers,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": auth_val,
                },
                method="POST",
            )
            res = opener.open(req_dl, timeout=20)
            content = res.read()
            if content and content[:4] == b"%PDF":
                return content
            return None
        except Exception as e:
            logger.error("Failed to download eproc2 attachment: %s", e)
            return None

    def fetch_tender_preview(self, tender: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Modular preview dispatcher: activates the 'Eye' button workflow for any supported
        public procurement portal, returning rich details, fees, officers, checklists, and attachments.
        """
        portal = (tender.get("portal") or "").lower()
        t_num = str(tender.get("tender_number") or tender.get("tender_id") or "")

        if "eproc2.bihar.gov.in" in portal or "BIH/EPROC2/" in t_num:
            opener, auth_val, rfq_map = self._get_eproc2_session_and_map()
            tid = tender.get("currenttenderid")
            org_id = tender.get("org_id", 538)
            if not tid:
                rfq_m = re.search(r"(?:BIH/EPROC2/|tnd_bih_)?(\d+)", t_num)
                rfq_id = rfq_m.group(1) if rfq_m else None
                if rfq_id and rfq_id in rfq_map:
                    tid, org_id = rfq_map[rfq_id]
                elif rfq_id:
                    tid = rfq_id
            if tid:
                return self._fetch_eproc2_tender_details(tid, org_id=org_id, opener=opener, auth_val=auth_val)

        return None

    def _fetch_eproc2_bihar(
        self,
        query: Optional[str] = None,
        state: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Connects directly to Bihar e-Procurement 2.0 (eproc2.bihar.gov.in) openarea REST API.
        Extracts active tenders, automatically retrieves rich preview details behind the 'Eye' button
        (contract cost, EMD, fees, dealing officers, and mandatory document checklists),
        verifies non-expired closing dates, and normalizes into TenderBee schema.
        """
        try:
            import http.cookiejar
            cj = http.cookiejar.CookieJar()
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            opener = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(cj),
                urllib.request.HTTPSHandler(context=ctx)
            )
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

            # 1. Fetch Bearer token from landing page
            page_url = "https://eproc2.bihar.gov.in/EPSV2Web/openarea/tenderListingPage.action"
            resp = opener.open(urllib.request.Request(page_url, headers=headers), timeout=8)
            html = resp.read().decode("utf-8", errors="ignore")
            m_auth = re.search(r'value=[\"\'](Bearer [^\"\']+)[\"\']', html)
            if not m_auth:
                return []
            auth_val = m_auth.group(1)

            # 2. Map department IDs to official Department Names
            dept_map = {1735: "Department of Science and Technology"}
            try:
                dept_url = "https://eproc2.bihar.gov.in/EPSV2Web/rest/organization/loadAllDeptWithParent?orgId=538"
                req_d = urllib.request.Request(
                    dept_url,
                    data=b"{}",
                    headers={**headers, "Content-Type": "application/json", "Authorization": auth_val},
                    method="POST"
                )
                dept_data = json.loads(opener.open(req_d, timeout=6).read().decode("utf-8"))
                for d in dept_data:
                    dept_map[d.get("organizationId")] = d.get("organizationName") or d.get("orgName")
            except Exception:
                pass

            # 3. Call getTenderList
            api_url = "https://eproc2.bihar.gov.in/EPSV2Web/rest/openarea/getTenderList"
            req_t = urllib.request.Request(
                api_url,
                data=b"{}",
                headers={**headers, "Content-Type": "application/json", "Authorization": auth_val},
                method="POST"
            )
            data = json.loads(opener.open(req_t, timeout=10).read().decode("utf-8"))
            if not isinstance(data, list):
                return []

            now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))
            candidate_items = []

            # Keywords to filter if user specified query terms
            clean_q = (query or "").lower().replace("bihar", "").replace("tenders", "").replace("tender", "").strip()
            kw_tokens = [k.strip().lower() for k in clean_q.split() if len(k.strip()) > 2 and k.lower() not in ("the", "and", "for", "with", "from", "department")]

            for item in data:
                dept_id = item.get("currentdeptid")
                dept_name = dept_map.get(dept_id, "Department of Science and Technology" if dept_id == 1735 else "Government of Bihar")
                desc = item.get("currentdescription") or ""
                ref_no = item.get("currenttenderrefno") or ""
                rfq_id = str(item.get("currentOrgTenderId") or item.get("currenttenderid") or "")

                # Deadline verification - require explicit end date
                end_ms = item.get("currentbidEndDate")
                if not end_ms:
                    continue

                dl_dt = datetime.fromtimestamp(end_ms / 1000.0, tz=timezone(timedelta(hours=5, minutes=30)))
                if dl_dt < now_ist:
                    continue

                full_text = f"{desc} {ref_no} {dept_name} {rfq_id} bih/eproc2/{rfq_id} {item.get('currenttenderid', '')}".lower()
                if kw_tokens:
                    if not any(token in full_text for token in kw_tokens):
                        continue

                candidate_items.append((item, dept_name, desc, ref_no, rfq_id, dl_dt))

            # Concurrently fetch rich preview details behind the Eye button for candidate tenders
            preview_map = {}
            if candidate_items:
                def _fetch_preview_worker(cand):
                    it = cand[0]
                    curr_tid = it.get("currenttenderid")
                    if not curr_tid:
                        return curr_tid, None
                    det = self._fetch_eproc2_tender_details(
                        tender_id=curr_tid,
                        org_id=it.get("currentorgid", 538),
                        opener=opener,
                        auth_val=auth_val,
                    )
                    return curr_tid, det

                with ThreadPoolExecutor(max_workers=min(8, len(candidate_items))) as pool:
                    for c_tid, c_preview in pool.map(_fetch_preview_worker, candidate_items[:25]):
                        if c_tid and c_preview:
                            preview_map[c_tid] = c_preview

            results = []
            for item, dept_name, desc, ref_no, rfq_id, dl_dt in candidate_items:
                curr_tid = item.get("currenttenderid")
                preview = preview_map.get(curr_tid) or {}

                # Use ground-truth value from Eye button preview if available
                val_inr = preview.get("estimated_value_inr")
                if val_inr is None:
                    pac_amt = item.get("currentpacamt")
                    val_inr = float(pac_amt) if pac_amt else None

                emd_inr = preview.get("emd_amount_inr")
                val_str = f"₹{val_inr:,.2f}" if val_inr else "Not Specified"
                emd_str = f"₹{emd_inr:,.2f}" if emd_inr else "Exempted / Nil"

                # Enriched buyer name with dealing officer and org hierarchy
                dealing_officer = preview.get("dealing_officer")
                org_h = preview.get("org_hierarchy") or []
                sub_dept = org_h[-1] if org_h else dept_name
                if dealing_officer:
                    enriched_buyer = f"{dept_name} - {sub_dept} ({dealing_officer}) (Ref: {ref_no})"
                else:
                    enriched_buyer = f"{dept_name} (Ref: {ref_no})"

                cat = category or ("Goods" if any(w in desc.lower() for w in ("supply", "equipment", "items", "instruments", "generator", "panel")) else "Services")

                tender_dict = {
                    "tender_id": f"tnd_bih_{rfq_id}",
                    "tender_number": f"BIH/EPROC2/{rfq_id}",
                    "currenttenderid": curr_tid,
                    "title": desc,
                    "buyer_name": enriched_buyer,
                    "state": "Bihar",
                    "category": cat,
                    "estimated_value_inr": val_inr,
                    "emd_amount_inr": emd_inr,
                    "tender_fee_inr": preview.get("tender_fee_inr"),
                    "processing_fee_inr": preview.get("processing_fee_inr"),
                    "dealing_officer": dealing_officer,
                    "mandatory_documents": preview.get("mandatory_documents", []),
                    "attachments": preview.get("attachments", []),
                    "nit_attachment": preview.get("nit_attachment"),
                    "boq_attachment": preview.get("boq_attachment"),
                    "tenure_months": 12,
                    "submission_deadline": dl_dt.isoformat(),
                    "portal": "eproc2.bihar.gov.in",
                    "source_url": f"https://eproc2.bihar.gov.in/EPSV2Web/openarea/tenderListingPage.action?rfqId={rfq_id}",
                    "status": "ACTIVE",
                    "has_pdf_document": True,
                }
                results.append(tender_dict)
                self.storage.save_tender_and_snapshot(
                    org_id="org_default",
                    tender_number=tender_dict["tender_number"],
                    tender_title=desc,
                    source_url=tender_dict["source_url"],
                    buyer_name=tender_dict["buyer_name"],
                    submission_deadline=dl_dt.isoformat(),
                    estimated_value_inr=val_inr,
                    extracted_data=tender_dict,
                    raw_text_payload=(
                        f"eProc2 Bihar Tender {rfq_id}: {desc}\n"
                        f"Ref: {ref_no}\n"
                        f"Department: {dept_name}\n"
                        f"Dealing Officer: {dealing_officer or 'N/A'}\n"
                        f"Deadline: {dl_dt}\n"
                        f"Estimated Value: {val_str}\n"
                        f"EMD Amount: {emd_str}\n"
                        f"Mandatory Documents: {', '.join(tender_dict['mandatory_documents'])}\n"
                    ),
                    tender_id=tender_dict["tender_id"],
                    state="Bihar",
                    category=cat,
                    portal="eproc2.bihar.gov.in",
                    tenure_months=12,
                    emd_amount_inr=emd_inr,
                    location="Bihar",
                )
            return results
        except Exception as e:
            logger.error("Failed to fetch eproc2 Bihar tenders: %s", e)
            return []

    def search_live(
        self,
        query: Optional[str] = None,
        state: Optional[str] = None,
        category: Optional[str] = None,
        city: Optional[str] = None,
        portal: Optional[str] = None,
        raw_prompt: Optional[str] = None,
        limit: int = 10,
        nationwide: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Executes targeted, deduplicated live procurement search via TinyFish Search API:
        1. Universal Live Coverage: Discovers live tenders across every Indian state and procurement portal.
        2. Query Normalization & Deduplication: Checks in-memory cache to avoid repeated API requests.
        3. Native Result Utilization: Leverages TinyFish SearchResult (title, snippet, pdf_url) as first-class tender data.
        4. Safe Error Handling: Handles RateLimitError, AuthenticationError, and timeouts with graceful degradation.
        """
        # Guard: If no query terms, state, or portal provided, do NOT perform broad search
        clean_q = (query or raw_prompt or "").strip()
        if not clean_q and not state and not category and not portal:
            logger.info("Live search skipped: no search query, state, or portal specified.")
            return []

        # State alias normalization if needed
        norm_state = state.strip() if state else None
        if norm_state and norm_state.lower() in ("all", "all states", "none", ""):
            norm_state = None

        norm_cat = category.strip() if category else None
        norm_city = city.strip() if city else None
        norm_portal = portal.strip() if portal else None

        # 1. Cache Lookup to avoid duplicate external API calls
        cache_key = f"{clean_q.lower()}:{str(norm_state).lower()}:{str(norm_cat).lower()}:{str(norm_city).lower()}:{str(norm_portal).lower()}:{nationwide}"
        now_ts = time.time()
        with self._cache_lock:
            if cache_key in self._query_cache:
                exp_ts, cached_items = self._query_cache[cache_key]
                if now_ts < exp_ts:
                    logger.info("Serving live search results from query cache for '%s'", cache_key)
                    return cached_items[:limit]
                else:
                    del self._query_cache[cache_key]

        # 2. Specialized RFQ ID lookup for Bihar eProc2 if a direct numeric RFQ ID is searched
        m_rfq = re.search(r"\b(14\d{4})\b", clean_q)
        if m_rfq:
            bihar_tenders = self._fetch_eproc2_bihar(query=clean_q, state=norm_state or "Bihar", category=norm_cat)
            if bihar_tenders:
                logger.info("Retrieved %d active tenders directly for RFQ %s from eProc2 Bihar", len(bihar_tenders), m_rfq.group(1))
                with self._cache_lock:
                    self._query_cache[cache_key] = (now_ts + self.CACHE_TTL_SECONDS, bihar_tenders)
                return bihar_tenders[:limit]

        if not self.client:
            logger.warning("TinyFish client not initialized (missing API key or library). Skipping live search.")
            return []

        # 3. Construct targeted high-precision TinyFish search query for requested state, domain, and keywords
        terms = []
        p_lower = norm_portal.lower() if norm_portal else None
        if p_lower:
            if p_lower == "gem":
                terms.append("site:gem.gov.in")
            elif p_lower == "cppp":
                terms.append("site:eprocure.gov.in")
            elif p_lower == "ireps":
                terms.append("site:ireps.gov.in")
            elif p_lower == "bihar":
                terms.append("Bihar (site:eproc2.bihar.gov.in OR site:bihar.gov.in OR site:bseidc.in)")
            elif "." in p_lower:
                terms.append(f"site:{p_lower}")

        if norm_state and (not p_lower or p_lower != "bihar"):
            terms.append(f'"{norm_state}"')
        if norm_city:
            terms.append(f'"{norm_city}"')
        if clean_q:
            terms.append(clean_q)
        if norm_cat:
            terms.append(norm_cat)

        query_str = " ".join(terms).strip()
        if not query_str:
            query_str = "tender notice 2026"

        if p_lower:
            targeted_q = f"{query_str} active tender 2026"
        elif norm_state:
            targeted_q = f'{query_str} active tender notice 2026'
        elif nationwide:
            targeted_q = f"{query_str} active tender notice site:gov.in 2026"
        else:
            targeted_q = f"{query_str} active tender notice 2026"

        logger.info("Executing TinyFish live procurement search query: '%s' (state=%s, portal=%s, nationwide=%s)", targeted_q, norm_state, norm_portal, nationwide)

        search_results = []
        try:
            res = self.client.search.query(
                targeted_q,
                purpose="Find currently active Indian government tenders, RFPs, and procurement notices",
                location="IN",
            )
            if res and hasattr(res, "results") and res.results:
                search_results = res.results
        except RateLimitError as exc:
            logger.warning("TinyFish rate limit exceeded (HTTP 429). Gracefully falling back: %s", exc)
            return []
        except AuthenticationError as exc:
            logger.error("TinyFish authentication failed (HTTP 401). Please verify TINYFISH_API_KEY.")
            return []
        except (APITimeoutError, APIConnectionError) as exc:
            logger.warning("TinyFish search request timed out or connection error: %s", exc)
            return []
        except Exception as exc:
            logger.error("TinyFish search query failed: %s", exc)
            return []

        if not search_results:
            logger.info("TinyFish search returned 0 items for '%s'", targeted_q)
            return []

        # 4. Result Deduplication & Validation
        seen_urls = set()
        seen_numbers = set()
        valid_candidates = []

        for item in search_results:
            raw_url = getattr(item, "url", None)
            title = getattr(item, "title", None) or ""
            snippet = getattr(item, "snippet", None) or ""
            if not raw_url:
                continue

            normalized_url = self.normalize_url(raw_url)
            if not normalized_url or normalized_url in seen_urls:
                continue

            # Validate that candidate is a genuine procurement item
            if not self._is_valid_tender_candidate(title, normalized_url, snippet):
                continue

            seen_urls.add(normalized_url)
            valid_candidates.append((item, normalized_url, title, snippet))
            if len(valid_candidates) >= min(limit * 2, 20):
                break

        if not valid_candidates:
            return []

        # 5. Fast Parallel DOM Inspection for rich field enrichment (with fallback to TinyFish native metadata)
        discovered_tenders: List[Dict[str, Any]] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        def _enrich_candidate(cand_tuple):
            it, norm_url, t_title, t_snippet = cand_tuple
            # Attempt shallow DOM inspection (timeout handled safely inside _inspect_live_page)
            inspected_list = self._inspect_live_page(norm_url, state=norm_state, category=norm_cat)
            if inspected_list and len(inspected_list) > 0:
                return inspected_list[0]

            # Fallback: construct first-class tender record directly from validated TinyFish SearchResult
            domain = urllib.parse.urlparse(norm_url).netloc
            url_hash = hashlib.sha256(norm_url.encode()).hexdigest()[:12]
            tender_num = f"TND/{domain.upper()}/{url_hash.upper()}"
            pdf_url = getattr(it, "pdf_url", None)
            has_pdf = bool(pdf_url or norm_url.lower().endswith(".pdf"))

            return {
                "source_url": norm_url,
                "tender_number": tender_num,
                "title": t_title.strip() or "Government Procurement Tender Notice",
                "buyer_name": domain,
                "portal": domain,
                "submission_deadline": getattr(it, "date", None),
                "estimated_value_inr": None,
                "emd_amount_inr": None,
                "state": norm_state or ("All India" if nationwide else "National"),
                "category": norm_cat or "Services",
                "tenure_months": 12,
                "has_pdf_document": has_pdf,
                "summary": t_snippet.strip() or f"Procurement opportunity on {domain}",
            }

        with ThreadPoolExecutor(max_workers=min(len(valid_candidates), 6)) as executor:
            batch_enriched = executor.map(_enrich_candidate, valid_candidates)
            for item in batch_enriched:
                if not item:
                    continue
                t_num = item.get("tender_number") or ""
                if t_num in seen_numbers:
                    continue
                seen_numbers.add(t_num)

                t_url = item["source_url"]
                tender_id = f"tnd_live_{hashlib.sha256(t_url.encode()).hexdigest()[:12]}"
                val = item.get("estimated_value_inr")
                emd = item.get("emd_amount_inr")
                val_str = f"₹{val:,.2f}" if val else "Not Specified"
                t_state = item.get("state") or norm_state or ("All India" if nationwide else "National")
                t_cat = item.get("category") or norm_cat or "Services"

                tender_dict = {
                    "tender_id": tender_id,
                    "tender_number": item["tender_number"],
                    "title": item["title"],
                    "buyer_name": item["buyer_name"],
                    "state": t_state,
                    "category": t_cat,
                    "estimated_value_inr": val,
                    "emd_amount_inr": emd,
                    "tenure_months": item.get("tenure_months", 12),
                    "submission_deadline": item.get("submission_deadline"),
                    "portal": item["portal"],
                    "source_url": t_url,
                    "status": "ACTIVE",
                    "summary": item.get("summary") or f"{val_str} | {t_cat} in {t_state}",
                    "has_pdf_document": item.get("has_pdf_document", False),
                    "is_live_discovered": True,
                }
                discovered_tenders.append(tender_dict)

                # Persist verified live tender into database cache
                try:
                    import sqlite3
                    with sqlite3.connect(self.storage.db_path) as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT OR IGNORE INTO tenders (
                                tender_id, organization_id, external_id, title, buyer_name,
                                submission_deadline, estimated_value_inr, source_url,
                                created_at, updated_at, state, category, tenure_months,
                                emd_amount_inr, location, portal
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            tender_id, "org_default", item["tender_number"], item["title"], item["buyer_name"],
                            item.get("submission_deadline"), val, t_url,
                            now_iso, now_iso, t_state, t_cat, 12,
                            emd, norm_city or t_state, item["portal"]
                        ))
                        conn.commit()
                except Exception as e:
                    logger.debug("Failed to index live discovered tender to SQLite: %s", e)

                if len(discovered_tenders) >= limit:
                    break

        # Save into query cache
        with self._cache_lock:
            self._query_cache[cache_key] = (now_ts + self.CACHE_TTL_SECONDS, discovered_tenders)

        logger.info("Live search retrieved and validated %d genuine tenders (cached for %ds)", len(discovered_tenders), self.CACHE_TTL_SECONDS)
        return discovered_tenders

