"""
External Outbound Request Security Guard & SSRF Protection for TenderBee.

Enforces:
1. Allow-listed HTTPS domains only for procurement portals and external integrations.
2. Resolution check rejecting private (RFC 1918), loopback (127.0.0.0/8), link-local (169.254.0.0/16), and IPv6 local addresses.
3. Strict redirect validation ensuring redirects remain strictly within allow-listed hosts.
4. Handling of CAPTCHA/OTP challenges, network timeouts, or outages by returning
   NEEDS_REVIEW with EXTERNAL_UNAVAILABLE status without ever attempting to solve or bypass CAPTCHA.
"""
import ipaddress
import logging
import socket
import urllib.parse
from typing import Any, Dict, Optional, Set
import httpx

logger = logging.getLogger(__name__)

# Official allow-listed Indian government procurement and registry domains
DEFAULT_ALLOWED_DOMAINS: Set[str] = {
    "ireps.gov.in",
    "eproc2.bihar.gov.in",
    "eproc.bihar.gov.in",
    "etenders.gov.in",
    "gem.gov.in",
    "cppp.gov.in",
    "udyamregistration.gov.in",
    "gst.gov.in",
    "incometax.gov.in",
    "api.tinyfish.io",
    "tinyfish.io",
}

BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


class SSRFProtectionError(ValueError):
    """Raised when an outbound URL violates SSRF or domain allow-list rules."""
    pass


def is_private_or_loopback_ip(ip_str: str) -> bool:
    """Checks if an IP belongs to private, loopback, or link-local ranges."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return any(ip in net for net in BLOCKED_IP_NETWORKS)
    except ValueError:
        return True


def validate_outbound_url(url: str, allowed_domains: Optional[Set[str]] = None) -> str:
    """
    Validates that a URL is HTTPS, its domain is in the allow-list, and does not resolve
    to any loopback or private network IP.
    """
    allowed = allowed_domains or DEFAULT_ALLOWED_DOMAINS
    parsed = urllib.parse.urlparse(url)

    # 1. Scheme must be HTTPS
    if parsed.scheme.lower() != "https":
        raise SSRFProtectionError(f"Insecure protocol '{parsed.scheme}'. Outbound requests must use HTTPS.")

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise SSRFProtectionError("Outbound URL is missing a valid hostname.")

    # 2. Domain must match allow-list (exact match or subdomain)
    is_domain_allowed = any(hostname == dom or hostname.endswith(f".{dom}") for dom in allowed)
    if not is_domain_allowed:
        raise SSRFProtectionError(
            f"Host '{hostname}' is not in the approved external domain allow-list."
        )

    # 3. DNS resolution & IP range check (anti-DNS rebinding / SSRF)
    try:
        addr_info = socket.getaddrinfo(hostname, 443, proto=socket.IPPROTO_TCP)
        for _, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            if is_private_or_loopback_ip(ip_str):
                raise SSRFProtectionError(
                    f"Resolved IP '{ip_str}' for host '{hostname}' is in a prohibited private/loopback network."
                )
    except socket.gaierror as e:
        raise SSRFProtectionError(f"Unable to resolve host '{hostname}': {e}")

    return url


def safe_fetch(url: str, timeout: float = 10.0, **kwargs) -> Dict[str, Any]:
    """
    Executes a guarded outbound HTTP GET request with SSRF validation,
    redirect filtering, and automatic conversion of bot challenges to NEEDS_REVIEW.
    """
    validated_url = validate_outbound_url(url)

    client = httpx.Client(
        timeout=timeout,
        follow_redirects=False,  # Redirects manually checked against allow-list
        verify=True,
    )

    try:
        current_url = validated_url
        response = client.get(current_url, **kwargs)

        # Handle redirects with allow-list check
        redirect_count = 0
        while response.is_redirect and redirect_count < 3:
            redirect_count += 1
            redirect_target = response.headers.get("Location")
            if not redirect_target:
                break
            abs_redirect = urllib.parse.urljoin(current_url, redirect_target)
            current_url = validate_outbound_url(abs_redirect)
            response = client.get(current_url, **kwargs)

        # Check for CAPTCHA / Bot mitigation walls (Cloudflare, GePNIC CAPTCHA)
        resp_text = response.text[:2000].lower()
        if (
            response.status_code in (403, 429)
            or "cf-mitigated" in str(response.headers).lower()
            or "captcha" in resp_text
            or "one time password" in resp_text
        ):
            return {
                "success": False,
                "status": "NEEDS_REVIEW",
                "reason": "EXTERNAL_UNAVAILABLE",
                "details": "External portal presented a bot challenge (CAPTCHA/OTP) or access limit. Manual review required.",
            }

        if response.status_code >= 400:
            return {
                "success": False,
                "status": "NEEDS_REVIEW",
                "reason": "EXTERNAL_UNAVAILABLE",
                "status_code": response.status_code,
            }

        return {
            "success": True,
            "status": "COMPLETED",
            "status_code": response.status_code,
            "content": response.content,
            "text": response.text,
        }

    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        logger.warning("External portal timeout/network error: %s", exc)
        return {
            "success": False,
            "status": "NEEDS_REVIEW",
            "reason": "EXTERNAL_UNAVAILABLE",
            "details": f"External portal network error or timeout: {str(exc)}",
        }
    except SSRFProtectionError as exc:
        logger.error("SSRF Protection blocked request: %s", exc)
        raise
    finally:
        client.close()
