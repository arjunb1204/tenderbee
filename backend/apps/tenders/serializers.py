"""
DRF Serializers for Tender Intake, PDF Parsing, and RulePack Confirmation.
"""
from rest_framework import serializers
from apps.tenders.models import Tender, TenderSnapshot


class TenderIntakeRequestSerializer(serializers.Serializer):
    identifier = serializers.CharField(
        required=True,
        max_length=2048,
        help_text="Procurement URL (e.g. Infralens, GeM) or Tender Number (e.g. GEM/2026/B/894210)",
    )
    org_id = serializers.CharField(
        required=False,
        default="org_default",
        max_length=128,
        help_text="Tenant organization ID",
    )
    force_refresh = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Force scrape bypass of existing snapshot cache",
    )


class TenderPDFUploadSerializer(serializers.Serializer):
    pdf_file = serializers.FileField(
        required=True,
        help_text="Tender Notice PDF file",
    )
    org_id = serializers.CharField(
        required=False,
        default="org_default",
        max_length=128,
        help_text="Tenant organization ID",
    )


class RulePackConfirmSerializer(serializers.Serializer):
    confirmed_by = serializers.CharField(
        required=False,
        default="compliance_lead",
        max_length=128,
        help_text="Identifier of the human reviewer approving the rules",
    )


class TenderSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenderSnapshot
        fields = ("id", "content_hash", "source_url", "extracted_data", "fetched_at")


class TenderSerializer(serializers.ModelSerializer):
    snapshots = TenderSnapshotSerializer(many=True, read_only=True)
    tender_id = serializers.CharField(source="id", read_only=True)
    tender_number = serializers.CharField(source="external_id", read_only=True)

    class Meta:
        model = Tender
        fields = (
            "id",
            "tender_id",
            "external_id",
            "tender_number",
            "title",
            "buyer_name",
            "buyer_location",
            "submission_deadline",
            "bid_opening_date",
            "estimated_value_inr",
            "emd_amount_inr",
            "mse_exemption_allowed",
            "source_url",
            "status",
            "snapshots",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")
