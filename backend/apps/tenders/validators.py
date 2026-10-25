"""
Validation Engine for Tender URLs and Indian Government Tender Numbers.
Enforces security guardrails (SSRF prevention, domain allow-listing)
and format verification for GeM, CPPP, IREPS, and Infralens tender identifiers.
"""
import ipaddress
import re
from typing import NamedTuple, Optional
from urllib.parse import urlparse

# Allow-listed domains for Indian procurement portals
ALLOWLISTED_DOMAINS = [
    "gov.in",
    "nic.in",
    "gem.gov.in",
    "eprocure.gov.in",
    "etenders.gov.in",
    "defproc.gov.in",
    "ireps.gov.in",
    "www.ireps.gov.in",
    "eproc2.bihar.gov.in",
    "jharkhandtenders.gov.in",
    "mahatenders.gov.in",
    "etender.up.nic.in",
    "kppp.karnataka.gov.in",
    "tender.nprocure.com",
    "infralens.in",
    "tenders.infralens.in",
]

# Standard Indian Government Tender ID Patterns
GEM_BID_PATTERN = re.compile(r"^GEM/\d{4}/[BR]/\d+$", re.IGNORECASE)
CPPP_TENDER_PATTERN = re.compile(r"^\d{4}_[A-Za-z0-9]+_\d+_\d+$")
IREPS_TENDER_PATTERN = re.compile(r"^[A-Za-z0-9\-_/.]+$")
INFRALENS_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")
GENERAL_TENDER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-\/\.]{3,64}$")


class ValidationResult(NamedTuple):
    is_valid: bool
    input_type: str  # "URL" | "TENDER_NUMBER" | "INVALID"
    normalized_value: str
    tender_format: Optional[str] = None  # "GeM", "CPPP", "Infralens", "General", etc.
    error_message: Optional[str] = None


def is_private_ip(hostname: str) -> bool:
    """SSRF Prevention: Checks if hostname resolves to a loopback or private network."""
    try:
        ip = ipaddress.ip_address(hostname)
        return ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local
    except ValueError:
        # It's a domain name, not a raw IP
        if hostname.lower() in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
            return True
        return False


def validate_url(url: str, allow_custom_domains: bool = False) -> ValidationResult:
    """
    Validates a tender URL against structure and security policies.
    - Scheme must be http or https
    - Hostname must not be a private IP (SSRF guardrail)
    - Domain must belong to the approved procurement portal allow-list
    - Path must contain a non-empty tender identifier/slug
    """
    url = url.strip()
    if not url:
        return ValidationResult(False, "URL", url, error_message="URL cannot be empty.")

    try:
        parsed = urlparse(url)
    except Exception as e:
        return ValidationResult(False, "URL", url, error_message=f"Malformed URL: {e}")

    if parsed.scheme not in ("http", "https"):
        return ValidationResult(
            False, "URL", url,
            error_message=f"Invalid protocol '{parsed.scheme}://'. Only HTTPS is permitted."
        )

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return ValidationResult(False, "URL", url, error_message="URL missing valid hostname.")

    # SSRF guardrail: reject private IP ranges
    if is_private_ip(hostname):
        return ValidationResult(
            False, "URL", url,
            error_message=f"Access to private or local network '{hostname}' is blocked."
        )

    # Domain allow-list check
    if not allow_custom_domains:
        domain_matched = any(
            hostname == allowed or hostname.endswith("." + allowed)
            for allowed in ALLOWLISTED_DOMAINS
        )
        if not domain_matched:
            return ValidationResult(
                False, "URL", url,
                error_message=(
                    f"Domain '{hostname}' is not in the allow-list. "
                    "Permitted sources: Indian Government e-Procurement portals (.gov.in, .nic.in, nprocure.com, infralens.in)"
                )
            )

    # Path check: tender URL must have a path or query
    path = parsed.path.strip("/")
    if not path and not parsed.query:
        return ValidationResult(
            False, "URL", url,
            error_message="URL points to portal homepage without a specific tender slug or ID."
        )

    return ValidationResult(True, "URL", url, tender_format="Web URL")


def validate_tender_number(tender_number: str) -> ValidationResult:
    """
    Validates a standalone tender number / bid ID.
    Recognizes:
    - GeM Bid Format: GEM/2026/B/123456
    - CPPP Format: 2026_ERDAElectr_320314_1
    - Infralens slug / General ID: pind-2627-00220-320314
    """
    cleaned = tender_number.strip()
    if not cleaned:
        return ValidationResult(False, "TENDER_NUMBER", cleaned, error_message="Tender number cannot be empty.")

    if len(cleaned) < 4:
        return ValidationResult(
            False, "TENDER_NUMBER", cleaned,
            error_message=f"Tender number '{cleaned}' is too short (min 4 characters)."
        )

    if len(cleaned) > 100:
        return ValidationResult(
            False, "TENDER_NUMBER", cleaned,
            error_message="Tender number exceeds maximum allowed length of 100 characters."
        )

    # Check known formats
    if GEM_BID_PATTERN.match(cleaned):
        return ValidationResult(True, "TENDER_NUMBER", cleaned, tender_format="GeM Bid")

    if CPPP_TENDER_PATTERN.match(cleaned):
        return ValidationResult(True, "TENDER_NUMBER", cleaned, tender_format="CPPP / eProcure")

    if GENERAL_TENDER_PATTERN.match(cleaned):
        return ValidationResult(True, "TENDER_NUMBER", cleaned, tender_format="Standard Tender Ref")

    return ValidationResult(
        False, "TENDER_NUMBER", cleaned,
        error_message=(
            f"Invalid tender number format '{cleaned}'. Expected GeM format (e.g. GEM/2026/B/894210), "
            f"CPPP format (e.g. 2026_ERDAElectr_320314_1), or valid alphanumeric reference."
        )
    )


def validate_identifier(identifier: str) -> ValidationResult:
    """
    Unified entry point: automatically detects whether the input is a URL or a Tender Number
    and validates it with exact reason codes.
    """
    identifier = identifier.strip()
    if not identifier:
        return ValidationResult(False, "INVALID", "", error_message="Input identifier cannot be empty.")

    if identifier.startswith("http://") or identifier.startswith("https://"):
        return validate_url(identifier)

    return validate_tender_number(identifier)
