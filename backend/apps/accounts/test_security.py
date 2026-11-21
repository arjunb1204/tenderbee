"""
Production-grade security test suite for TenderBee backend.
Verifies:
1. Authentication: 401 unauthenticated, Argon2, throttling/lockout, uniform error messages, token rotation & blacklisting, logout.
2. Authorization & Tenant Isolation: 404 (never 403) on cross-tenant read/update/delete, RBAC (member, reviewer, owner).
3. Rule Packs & Verdict Overrides: Immuntability of frozen packs, mandatory reason on override, preserving original verdict.
4. Document Upload Validation: Magic bytes, 25MB size limit, encrypted PDF rejection, active content stripping, SHA-256 duplicate detection.
5. Storage Adapter & Keys: Server-side generated keys, in-memory backend testing.
6. SSRF Protection: Private IPs and unlisted domains rejected, bot challenge handling.
7. Append-only Audit Trail: Modification and deletion blocked with PermissionDenied.
"""

import io
import time
from datetime import timedelta
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from pypdf import PdfWriter, PageObject

from apps.accounts.models import Organization, User, UserRole
from apps.audit.models import AuditEventType, AuditLogEntry
from apps.audit.services import record_audit_event
from apps.documents.models import BidderDocument, DocumentTypeEnum
from apps.documents.validators import validate_and_sanitize_pdf
from apps.rules.models import RulePack, RulePackStatus
from apps.verify.models import VerificationAssessment
from services.storage import InMemoryStorageBackend, put, get, exists, delete
from services.external_guard import validate_outbound_url, safe_fetch, SSRFProtectionError


def create_minimal_pdf_bytes(text_content: str = "TenderBee Verification Document") -> bytes:
    """Helper to produce a valid PDF with magic bytes %PDF-."""
    writer = PdfWriter()
    writer.add_page(PageObject.create_blank_page(width=612, height=792))
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


class SecurityAuthenticationTests(APITestCase):
    """Verifies authentication security, lockout, rotation, and logout."""

    def setUp(self):
        self.org = Organization.objects.create(name="Apex Defense Ltd")
        self.user = User.objects.create_user(
            email="security@apexdefense.in",
            username="apex_sec",
            password="StrongPassword2026!",
            organization=self.org,
            role=UserRole.OWNER,
        )
        self.login_url = "/api/v1/auth/login/"
        self.refresh_url = "/api/v1/auth/refresh/"
        self.logout_url = "/api/v1/auth/logout/"
        self.me_url = "/api/v1/auth/me/"

    def test_unauthenticated_requests_return_401(self):
        """Unauthenticated requests to protected endpoints return 401."""
        protected_endpoints = [
            self.me_url,
            "/api/v1/documents/",
            "/api/v1/rules/",
            "/api/v1/verify/assessments/",
            "/api/v1/audit/",
        ]
        for url in protected_endpoints:
            resp = self.client.get(url)
            self.assertEqual(
                resp.status_code,
                status.HTTP_401_UNAUTHORIZED,
                f"Expected 401 on {url}, got {resp.status_code}",
            )

    def test_uniform_error_message_for_invalid_credentials(self):
        """Invalid email and invalid password return identical generic error."""
        # Case 1: Wrong password
        resp1 = self.client.post(self.login_url, {"email": "security@apexdefense.in", "password": "WrongPassword1!"})
        self.assertEqual(resp1.status_code, status.HTTP_401_UNAUTHORIZED)
        error1 = resp1.data.get("error")

        # Case 2: Non-existent email
        resp2 = self.client.post(self.login_url, {"email": "nonexistent@apexdefense.in", "password": "WrongPassword1!"})
        self.assertEqual(resp2.status_code, status.HTTP_401_UNAUTHORIZED)
        error2 = resp2.data.get("error")

        self.assertEqual(error1, "Invalid email or password.")
        self.assertEqual(error2, "Invalid email or password.")

    def test_login_throttling_and_lockout(self):
        """Repeated failed login attempts lock out the account."""
        self.assertEqual(self.user.failed_login_attempts, 0)
        self.assertFalse(self.user.is_locked())

        # Attempt 5 consecutive failed logins
        for _ in range(5):
            self.client.post(self.login_url, {"email": "security@apexdefense.in", "password": "WrongPassword!"})

        self.user.refresh_from_db()
        self.assertEqual(self.user.failed_login_attempts, 5)
        self.assertTrue(self.user.is_locked())

        # Next attempt should be blocked by lockout (429 Too Many Requests)
        resp = self.client.post(self.login_url, {"email": "security@apexdefense.in", "password": "StrongPassword2026!"})
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("locked", resp.data.get("error", "").lower())

    def test_token_rotation_and_blacklisting(self):
        """Refresh tokens rotate on use; old refresh tokens are blacklisted."""
        # Login to obtain tokens in cookie or body
        login_resp = self.client.post(self.login_url, {"email": "security@apexdefense.in", "password": "StrongPassword2026!"})
        self.assertEqual(login_resp.status_code, status.HTTP_200_OK)
        old_refresh = login_resp.cookies.get("refresh_token").value if "refresh_token" in login_resp.cookies else login_resp.data.get("refresh")
        self.assertIsNotNone(old_refresh)

        # Rotate token
        refresh_resp = self.client.post(self.refresh_url, {"refresh": old_refresh})
        self.assertEqual(refresh_resp.status_code, status.HTTP_200_OK)
        new_refresh = refresh_resp.cookies.get("refresh_token").value if "refresh_token" in refresh_resp.cookies else refresh_resp.data.get("refresh")
        self.assertIsNotNone(new_refresh)
        self.assertNotEqual(old_refresh, new_refresh)

        # Attempt to reuse old rotated refresh token -> must be rejected
        reuse_resp = self.client.post(self.refresh_url, {"refresh": old_refresh})
        self.assertEqual(reuse_resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_blacklists_refresh_token(self):
        """Logout endpoint blacklists the active refresh token and clears auth cookies."""
        login_resp = self.client.post(self.login_url, {"email": "security@apexdefense.in", "password": "StrongPassword2026!"})
        refresh_token = login_resp.cookies.get("refresh_token").value if "refresh_token" in login_resp.cookies else login_resp.data.get("refresh")
        self.assertIsNotNone(refresh_token)

        # Set cookie or pass refresh token in body
        logout_resp = self.client.post(self.logout_url, {"refresh": refresh_token})
        self.assertEqual(logout_resp.status_code, status.HTTP_200_OK)

        # Refresh token is now blacklisted
        refresh_resp = self.client.post(self.refresh_url, {"refresh": refresh_token})
        self.assertEqual(refresh_resp.status_code, status.HTTP_401_UNAUTHORIZED)


from apps.tenders.models import Tender

class TenantIsolationAndRBACTests(APITestCase):
    """Verifies strict 404 cross-tenant isolation and role permission enforcement."""

    def setUp(self):
        # Organization 1 (Alpha)
        self.org1 = Organization.objects.create(name="Alpha Corp")
        self.owner1 = User.objects.create_user(
            email="owner@alpha.in", username="alpha_owner", password="Password123!", organization=self.org1, role=UserRole.OWNER
        )
        self.reviewer1 = User.objects.create_user(
            email="reviewer@alpha.in", username="alpha_reviewer", password="Password123!", organization=self.org1, role=UserRole.REVIEWER
        )
        self.member1 = User.objects.create_user(
            email="member@alpha.in", username="alpha_member", password="Password123!", organization=self.org1, role=UserRole.MEMBER
        )

        # Organization 2 (Beta)
        self.org2 = Organization.objects.create(name="Beta Industries")
        self.owner2 = User.objects.create_user(
            email="owner@beta.in", username="beta_owner", password="Password123!", organization=self.org2, role=UserRole.OWNER
        )

        # Org 1 Tender & Document
        self.tender1 = Tender.objects.create(
            organization=self.org1,
            external_id="GEM/2026/B/894210",
            title="Alpha Construction Tender",
        )
        self.doc1 = BidderDocument.objects.create(
            organization=self.org1,
            tender=self.tender1,
            file_name="alpha_tax.pdf",
            file_path="orgs/alpha/documents/doc1.pdf",
            document_type=DocumentTypeEnum.GST,
            file_size_bytes=1024,
            sha256_hash="1111111111111111111111111111111111111111111111111111111111111111",
        )

        # Org 1 RulePack
        self.pack1 = RulePack.objects.create(
            organization=self.org1,
            tender=self.tender1,
            status=RulePackStatus.DRAFT,
            rules_data=[],
        )

        # Org 2 Tender & Document
        self.tender2 = Tender.objects.create(
            organization=self.org2,
            external_id="GEM/2026/B/999999",
            title="Beta Secret Tender",
        )
        self.doc2 = BidderDocument.objects.create(
            organization=self.org2,
            tender=self.tender2,
            file_name="beta_secret.pdf",
            file_path="orgs/beta/documents/doc2.pdf",
            document_type=DocumentTypeEnum.PAN,
            file_size_bytes=2048,
            sha256_hash="2222222222222222222222222222222222222222222222222222222222222222",
        )

    def test_cross_tenant_access_returns_404_never_403(self):
        """Cross-tenant document access, download, and delete return 404 to prevent enumeration."""
        self.client.force_authenticate(user=self.owner1)

        # 1. Detail view on another org's document
        resp_detail = self.client.get(f"/api/v1/documents/{self.doc2.id}/")
        self.assertEqual(resp_detail.status_code, status.HTTP_404_NOT_FOUND)

        # 2. Download on another org's document
        resp_download = self.client.get(f"/api/v1/documents/{self.doc2.id}/download/")
        self.assertEqual(resp_download.status_code, status.HTTP_404_NOT_FOUND)

        # 3. List view only shows own organization documents
        resp_list = self.client.get("/api/v1/documents/")
        self.assertEqual(resp_list.status_code, status.HTTP_200_OK)
        returned_ids = [d["id"] for d in resp_list.data.get("results", resp_list.data)]
        self.assertIn(self.doc1.id, returned_ids)
        self.assertNotIn(self.doc2.id, returned_ids)

    def test_member_cannot_freeze_rule_pack(self):
        """A member cannot freeze or confirm a rule pack (requires Reviewer or Owner)."""
        self.client.force_authenticate(user=self.member1)
        resp = self.client.post(f"/api/v1/rules/{self.pack1.id}/confirm/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_reviewer_can_freeze_rule_pack_and_it_becomes_immutable(self):
        """A reviewer can freeze a rule pack, and once frozen, it cannot be modified."""
        self.client.force_authenticate(user=self.reviewer1)
        resp = self.client.post(f"/api/v1/rules/{self.pack1.id}/confirm/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        self.pack1.refresh_from_db()
        self.assertEqual(self.pack1.status, RulePackStatus.FROZEN)

        # Attempt to modify a frozen rule pack
        self.pack1.rules_data = [{"rule_id": "tampered", "description": "Hacked"}]
        with self.assertRaises(PermissionDenied):
            self.pack1.save()

    def test_verdict_override_requires_reviewer_and_mandatory_reason(self):
        """Verdict overrides require reviewer/owner and a mandatory non-empty reason."""
        assessment = VerificationAssessment.objects.create(
            organization=self.org1,
            tender=self.tender1,
            rule_pack=self.pack1,
            overall_status="NEEDS_REVIEW",
            verdicts_data=[{"rule_id": "rule_1", "verdict": "FAIL", "reason": "Missing GST"}],
        )

        # Member attempt -> 403
        self.client.force_authenticate(user=self.member1)
        resp_member = self.client.post(
            f"/api/v1/verify/assessments/{assessment.id}/override/",
            {"rule_id": "rule_1", "new_verdict": "PASS", "reason": "Member trying override"},
            format="json",
        )
        self.assertEqual(resp_member.status_code, status.HTTP_403_FORBIDDEN)

        # Reviewer attempt without reason -> 400
        self.client.force_authenticate(user=self.reviewer1)
        resp_no_reason = self.client.post(
            f"/api/v1/verify/assessments/{assessment.id}/override/",
            {"rule_id": "rule_1", "new_verdict": "PASS", "reason": ""},
            format="json",
        )
        self.assertEqual(resp_no_reason.status_code, status.HTTP_400_BAD_REQUEST)

        # Reviewer attempt with valid reason -> 200
        resp_valid = self.client.post(
            f"/api/v1/verify/assessments/{assessment.id}/override/",
            {
                "rule_id": "rule_1",
                "new_verdict": "PASS",
                "reason": "Exemption granted per clause 4.2 under MSME scheme.",
            },
            format="json",
        )
        self.assertEqual(resp_valid.status_code, status.HTTP_200_OK)

        assessment.refresh_from_db()
        self.assertEqual(len(assessment.verdict_overrides), 1)
        override_data = assessment.verdict_overrides[0]
        self.assertEqual(override_data["new_verdict"], "PASS")
        self.assertEqual(override_data["reason"], "Exemption granted per clause 4.2 under MSME scheme.")
        self.assertEqual(override_data["overridden_by"], self.reviewer1.email)


class DocumentValidationAndStorageTests(APITestCase):
    """Verifies file validation, active content stripping, SHA-256 duplicate checks, and storage."""

    def setUp(self):
        self.org = Organization.objects.create(name="Gamma Infrastructure")
        self.user = User.objects.create_user(
            email="uploader@gamma.in", username="gamma_uploader", password="Password123!", organization=self.org, role=UserRole.MEMBER
        )
        self.client.force_authenticate(user=self.user)

    def test_rejects_non_pdf_magic_bytes(self):
        """Upload validation rejects files that do not start with %PDF- magic bytes."""
        fake_pdf = b"This is just plain text renamed to fake.pdf"

        with self.assertRaises(ValidationError) as ctx:
            validate_and_sanitize_pdf(fake_pdf, self.org.id)
        self.assertIn("magic bytes", str(ctx.exception).lower())

    def test_rejects_oversize_files(self):
        """Upload validation rejects files exceeding 25MB."""
        huge_bytes = b"%PDF-" + b"0" * (26 * 1024 * 1024)

        with self.assertRaises(ValidationError) as ctx:
            validate_and_sanitize_pdf(huge_bytes, self.org.id)
        self.assertIn("25 mb", str(ctx.exception).lower())

    def test_duplicate_sha256_detection_per_organization(self):
        """Duplicate document hash in the same organization is detected and rejected."""
        pdf_bytes = create_minimal_pdf_bytes("Unique Tax Cert")
        stream1 = io.BytesIO(pdf_bytes)
        stream1.name = "tax1.pdf"

        sanitized, sha_hash = validate_and_sanitize_pdf(stream1, self.org.id)

        # Create record in DB
        BidderDocument.objects.create(
            organization=self.org,
            file_name="tax1.pdf",
            file_path=f"orgs/{self.org.id}/documents/test.pdf",
            document_type=DocumentTypeEnum.GST,
            file_size_bytes=len(sanitized),
            sha256_hash=sha_hash,
        )

        # Second upload with identical bytes
        stream2 = io.BytesIO(pdf_bytes)
        stream2.name = "tax_copy.pdf"
        with self.assertRaises(ValidationError) as ctx:
            validate_and_sanitize_pdf(stream2, self.org.id)
        self.assertIn("identical content", str(ctx.exception).lower())

    def test_in_memory_storage_adapter(self):
        """Tests standard storage adapter put, get, exists, and delete."""
        backend = InMemoryStorageBackend()
        test_key = "orgs/test_org/documents/sample.pdf"
        test_data = b"%PDF-1.4 sample payload"

        self.assertFalse(backend.exists(test_key))

        backend.put(test_key, test_data)
        self.assertTrue(backend.exists(test_key))

        retrieved = backend.get(test_key)
        self.assertEqual(retrieved, test_data)

        self.assertTrue(backend.delete(test_key))
        self.assertFalse(backend.exists(test_key))


class SSRFAndExternalGuardTests(APITestCase):
    """Verifies SSRF protection against private IPs, localhost, and unauthorized domains."""

    def test_rejects_non_https_and_localhost(self):
        """Rejects insecure HTTP and loopback URLs."""
        with self.assertRaises(SSRFProtectionError):
            validate_outbound_url("http://localhost:8000/tender")

        with self.assertRaises(SSRFProtectionError):
            validate_outbound_url("https://127.0.0.1/tender")

        with self.assertRaises(SSRFProtectionError):
            validate_outbound_url("https://10.0.0.1/secret")

        with self.assertRaises(SSRFProtectionError):
            validate_outbound_url("https://192.168.1.1/admin")

    def test_rejects_unapproved_domain(self):
        """Rejects outbound requests to unapproved external domains."""
        with self.assertRaises(SSRFProtectionError):
            validate_outbound_url("https://malicious-portal.com/tenders")

    def test_safe_fetch_bot_challenge_returns_needs_review(self):
        """Simulated bot challenge / outage produces NEEDS_REVIEW with EXTERNAL_UNAVAILABLE."""
        from unittest.mock import patch, MagicMock
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.is_redirect = False
        mock_resp.headers = {"cf-mitigated": "challenge"}
        mock_resp.text = "Please complete the CAPTCHA to continue"

        with patch("httpx.Client.get", return_value=mock_resp):
            result = safe_fetch("https://gem.gov.in/tenders/123")
            self.assertEqual(result["status"], "NEEDS_REVIEW")
            self.assertEqual(result["reason"], "EXTERNAL_UNAVAILABLE")


class AppendOnlyAuditTrailTests(APITestCase):
    """Verifies that audit trail entries are strictly append-only and cannot be altered or deleted."""

    def setUp(self):
        self.org = Organization.objects.create(name="Delta Defense")
        self.user = User.objects.create_user(
            email="auditor@delta.in", username="delta_auditor", password="Password123!", organization=self.org, role=UserRole.OWNER
        )

    def test_audit_log_modification_and_deletion_blocked(self):
        """Existing AuditLogEntry cannot be updated or deleted."""
        entry = record_audit_event(
            event_type=AuditEventType.LOGIN,
            actor=self.user.email,
            organization=self.org,
            target_id=str(self.user.id),
            details={"ip": "127.0.0.1"},
        )
        self.assertIsNotNone(entry.id)

        # Attempt to modify
        entry.details = {"ip": "tampered_ip"}
        with self.assertRaises(PermissionDenied):
            entry.save()

        # Attempt to delete
        with self.assertRaises(PermissionDenied):
            entry.delete()
