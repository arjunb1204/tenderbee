"""
Verification Assessment Models storing deterministic rules engine verdicts and registry audit proofs.
"""
import uuid
from django.db import models
from apps.accounts.models import TenantAwareModel
from apps.tenders.models import Tender
from apps.rules.models import RulePack


class AssessmentStatus(models.TextChoices):
    READY = "READY", "Ready (Bid Compliant)"
    NEEDS_REVIEW = "NEEDS_REVIEW", "Needs Human Review"
    BLOCKED = "BLOCKED", "Blocked (Ineligible or Disqualified)"


class VerificationAssessment(TenantAwareModel):
    """
    Immutable audit record of a full 7-stage compliance verification evaluation.
    """
    id = models.CharField(primary_key=True, max_length=64, editable=False)
    tender = models.ForeignKey(
        Tender,
        on_delete=models.CASCADE,
        related_name="assessments",
        db_index=True,
    )
    rule_pack = models.ForeignKey(
        RulePack,
        on_delete=models.CASCADE,
        related_name="assessments",
        db_index=True,
    )
    overall_status = models.CharField(
        max_length=32,
        choices=AssessmentStatus.choices,
        default=AssessmentStatus.NEEDS_REVIEW,
        db_index=True,
    )
    verdicts_data = models.JSONField(default=list, help_text="Individual rule verdicts")
    missing_documents = models.JSONField(default=list, help_text="Documents required but not provided")
    fix_list = models.JSONField(default=list, help_text="Actionable fixes required before bidding")
    registry_verifications = models.JSONField(default=dict, help_text="Live checks against official registries via TinyFish")
    verdict_overrides = models.JSONField(default=list, help_text="Human reviewer verdict overrides preserving original verdicts")
    assessed_by = models.CharField(max_length=255, default="deterministic_engine")
    assessed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-assessed_at"]

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = f"asm_{uuid.uuid4().hex[:12]}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Assessment {self.id} for Tender {self.tender.external_id} [{self.overall_status}]"
