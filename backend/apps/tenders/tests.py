"""
Unit and integration tests for TenderBee backend.tenders app and services.
"""
from pathlib import Path
import pytest

from backend.apps.audit.services import AuditTrailService
from backend.services.storage import TenderStorage
from backend.apps.tenders.services import TenderService
from backend.apps.tenders.validators import (
    validate_identifier,
    validate_tender_number,
    validate_url,
)
from backend.engine.schema import RuleStatus

SAMPLE_PDF = Path(__file__).resolve().parents[3] / "samples" / "western_railway_mech_tpa_2026.pdf"


def test_validator_guardrails():
    """Verifies SSRF prevention and procurement allow-listing."""
    assert validate_url("http://127.0.0.1:8000/tender/1").is_valid is False
    assert validate_url("http://192.168.1.10/admin").is_valid is False
    assert validate_url("https://malicious-site.com/bid/123").is_valid is False
    assert validate_url("https://tenders.infralens.in/tender/test-slug").is_valid is True
    assert validate_url("https://gem.gov.in/bid/GEM-123").is_valid is True

    # Tender number validation
    assert validate_tender_number("GEM/2026/B/894210").is_valid is True
    assert validate_tender_number("2026_ERDAElectr_320314_1").is_valid is True
    assert validate_tender_number("bad").is_valid is False

    # Unified identifier validator
    res_url = validate_identifier("https://gem.gov.in/bid/123")
    assert res_url.is_valid is True
    assert res_url.input_type == "URL"

    res_num = validate_identifier("GEM/2026/B/894210")
    assert res_num.is_valid is True
    assert res_num.input_type == "TENDER_NUMBER"


def test_tender_service_pdf_intake_and_freeze(tmp_path):
    """Verifies end-to-end PDF intake, storage, and rule-pack freezing in backend.tenders."""
    if not SAMPLE_PDF.exists():
        pytest.skip("Sample PDF not found.")

    storage = TenderStorage(base_dir=str(tmp_path))
    service = TenderService(storage=storage)

    result = service.intake_tender_pdf(str(SAMPLE_PDF), org_id="test_org")

    assert result["success"] is True
    assert result["tender_number"] == "Mech-TPA-2026"
    assert result["estimated_value_inr"] == 522615823.34
    assert result["emd_amount_inr"] == 2763100.00
    assert "rule_pack" in result

    rule_pack_id = result["rule_pack_id"]
    freeze_res = service.confirm_rule_pack(rule_pack_id, confirmed_by="auditor_lead")
    assert freeze_res["success"] is True
    assert freeze_res["status"] == RuleStatus.FROZEN.value
    assert freeze_res["confirmed_by"] == "auditor_lead"


def test_audit_trail_tamper_evident_chain(tmp_path):
    """Verifies that AuditTrailService maintains an immutable hash-chained log."""
    db_file = tmp_path / "test_audit.db"
    audit_svc = AuditTrailService(db_path=str(db_file))

    ev1 = audit_svc.log_event(
        actor="user_1",
        action="INTAKE_PDF",
        entity_type="tender",
        entity_id="tnd_123",
        payload={"file": "sample.pdf"},
    )
    assert ev1["success"] is True
    assert ev1["prev_hash"] == "GENESIS_HASH_00000000000000000000000000000000"

    ev2 = audit_svc.log_event(
        actor="user_2",
        action="FREEZE_RULE_PACK",
        entity_type="rule_pack",
        entity_id="rp_456",
        payload={"status": "FROZEN"},
    )
    assert ev2["success"] is True
    assert ev2["prev_hash"] == ev1["event_hash"]

    events = audit_svc.get_events()
    assert len(events) == 2
    assert events[0]["action"] == "INTAKE_PDF"
    assert events[1]["action"] == "FREEZE_RULE_PACK"


from rest_framework.test import APITestCase
from apps.accounts.models import Organization, User, UserRole
from apps.tenders.models import Tender, TenderSnapshot


class TenderAPITests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Apex Engineers Ltd")
        self.user = User.objects.create_user(
            email="tenderlead@apex.in",
            username="tenderlead",
            password="ApexPassword123!",
            organization=self.org,
            role=UserRole.BID_MANAGER,
        )
        self.client.force_authenticate(user=self.user)
        self.tender = Tender.objects.create(
            organization=self.org,
            external_id="GEM/2026/B/999111",
            title="Procurement of Heavy Engineering Equipment",
            buyer_name="BHEL",
            estimated_value_inr=50000000.0,
        )

    def test_list_tenders_tenant_isolation(self):
        other_org = Organization.objects.create(name="Foreign Org")
        Tender.objects.create(
            organization=other_org,
            external_id="OTHER/123",
            title="Other Org Tender",
        )

        resp = self.client.get("/api/v1/tenders/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["external_id"], "GEM/2026/B/999111")

    def test_get_tender_detail(self):
        resp = self.client.get(f"/api/v1/tenders/{self.tender.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["title"], "Procurement of Heavy Engineering Equipment")

    def test_portals_directory_api(self):
        resp = self.client.get("/api/v1/tenders/portals/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["success"])
        self.assertGreaterEqual(resp.data["total"], 36)

        # Test filter by query
        resp_jh = self.client.get("/api/v1/tenders/portals/?q=jharkhand")
        self.assertEqual(resp_jh.status_code, 200)
        self.assertEqual(resp_jh.data["total"], 1)
        self.assertEqual(resp_jh.data["portals"][0]["code"], "JH")
        self.assertEqual(resp_jh.data["portals"][0]["domain"], "jharkhandtenders.gov.in")

    def test_state_procurement_allowlist_validators(self):
        assert validate_url("https://jharkhandtenders.gov.in/nicgep/app?id=123").is_valid is True
        assert validate_url("https://eproc2.bihar.gov.in/EPSV2Web/tender?id=141349").is_valid is True
        assert validate_url("https://mahatenders.gov.in/app?page=view&id=441209").is_valid is True
        assert validate_url("https://tender.nprocure.com/tender/999").is_valid is True

    def test_query_parser_jharkhand_typo_and_roadways(self):
        from backend.apps.tenders.search import QueryParser
        parsed = QueryParser.parse("jharkand roadways tender")
        self.assertEqual(parsed.state, "Jharkhand")
        self.assertEqual(parsed.query, "roadways")

