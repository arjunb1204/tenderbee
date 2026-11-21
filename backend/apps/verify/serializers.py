"""
Serializers for Verification Assessments and Compliance Verdicts.
"""
from rest_framework import serializers
from apps.verify.models import VerificationAssessment


class AssessmentRequestSerializer(serializers.Serializer):
    tender_id = serializers.CharField(required=True, help_text="Tender ID to evaluate compliance for")
    rule_pack_id = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Optional RulePack ID (defaults to latest frozen or active RulePack)",
    )


class VerificationAssessmentSerializer(serializers.ModelSerializer):
    tender_external_id = serializers.CharField(source="tender.external_id", read_only=True)
    tender_title = serializers.CharField(source="tender.title", read_only=True)

    class Meta:
        model = VerificationAssessment
        fields = (
            "id",
            "tender",
            "tender_external_id",
            "tender_title",
            "rule_pack",
            "overall_status",
            "verdicts_data",
            "missing_documents",
            "fix_list",
            "registry_verifications",
            "verdict_overrides",
            "assessed_by",
            "assessed_at",
        )
        read_only_fields = fields


class VerdictOverrideSerializer(serializers.Serializer):
    rule_id = serializers.CharField(required=True, help_text="Rule identifier being overridden (e.g. R-TURNOVER-AVG3)")
    new_verdict = serializers.ChoiceField(
        choices=["PASS", "FAIL", "WAIVED", "NEEDS_REVIEW"],
        required=True,
    )
    reason = serializers.CharField(
        required=True,
        min_length=10,
        help_text="Mandatory human justification explaining the verdict override",
    )
