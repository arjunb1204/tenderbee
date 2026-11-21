"""
Unit and integration tests for RulePack lifecycle, human review, and freezing.
"""
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Organization, User, UserRole
from apps.audit.models import AuditEventType, AuditLogEntry
from apps.rules.models import RulePack, RulePackItem, RulePackStatus
from apps.tenders.models import Tender


class RulePackLifecycleTests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="L&T Infrastructure")
        self.user = User.objects.create_user(
            email="compliance@ltinfra.in",
            username="ltcompliance",
            password="LTCompliancePass123!",
            organization=self.org,
            role=UserRole.ADMIN,
        )
        self.client.force_authenticate(user=self.user)

        self.tender = Tender.objects.create(
            organization=self.org,
            external_id="GEM/2026/B/777123",
            title="Design and Construction of Elevated Corridor",
        )

        self.rule_pack = RulePack.objects.create(
            organization=self.org,
            tender=self.tender,
            version=1,
            status=RulePackStatus.DRAFT,
            rules_data=[{"rule_id": "R-TURNOVER-AVG3", "min_avg_turnover": 15000000}],
        )

        self.item = RulePackItem.objects.create(
            rule_pack=self.rule_pack,
            rule_id="R-TURNOVER-AVG3",
            rule_type="numeric_threshold",
            description="Minimum 3-year average turnover must exceed 1.5 Cr.",
            document_type="ca_turnover_certificate",
            parameters={"min_avg_turnover": 15000000},
        )

    def test_list_and_detail_rule_packs(self):
        resp = self.client.get("/api/v1/rules/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get("results", resp.data) if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], self.rule_pack.id)

        detail_resp = self.client.get(f"/api/v1/rules/{self.rule_pack.id}/")
        self.assertEqual(detail_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_resp.data["status"], "DRAFT")
        self.assertEqual(len(detail_resp.data["items"]), 1)

    def test_dismiss_rule_item_in_draft(self):
        url = f"/api/v1/rules/{self.rule_pack.id}/items/{self.item.id}/"
        resp = self.client.patch(url, {"is_dismissed": True}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.item.refresh_from_db()
        self.assertTrue(self.item.is_dismissed)

    def test_freeze_rule_pack_and_audit_event(self):
        freeze_url = f"/api/v1/rules/{self.rule_pack.id}/confirm/"
        resp = self.client.post(freeze_url, {"confirmed_by": "Senior Compliance Lead"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["success"])
        self.assertEqual(resp.data["status"], "FROZEN")
        self.assertIsNotNone(resp.data["frozen_hash"])

        self.rule_pack.refresh_from_db()
        self.assertEqual(self.rule_pack.status, RulePackStatus.FROZEN)
        self.assertEqual(self.rule_pack.confirmed_by, "Senior Compliance Lead")

        # Verify audit log was created
        audit_entry = AuditLogEntry.objects.filter(
            target_id=self.rule_pack.id,
            event_type=AuditEventType.RULE_PACK_FROZEN,
        ).first()
        self.assertIsNotNone(audit_entry)
        self.assertEqual(audit_entry.actor, "Senior Compliance Lead")

    def test_frozen_rule_pack_immutability_enforced(self):
        # Freeze rule pack first
        self.rule_pack.freeze(confirmed_by_name="Lead Auditor")

        # Try to modify item
        url = f"/api/v1/rules/{self.rule_pack.id}/items/{self.item.id}/"
        resp = self.client.patch(url, {"is_dismissed": True}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Immutability violation", resp.data["error"])

    def test_frozen_hash_detects_direct_rule_item_tampering(self):
        self.rule_pack.freeze(confirmed_by_name="Lead Auditor")
        self.assertTrue(self.rule_pack.has_valid_frozen_integrity())

        self.item.parameters = {"min_avg_turnover": 1}
        self.item.save(update_fields=["parameters"])
        self.rule_pack.refresh_from_db()

        self.assertFalse(self.rule_pack.has_valid_frozen_integrity())
