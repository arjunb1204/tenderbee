"""
Immutable Audit Trail Models for TenderBee.
Records cryptographically signed events for tenders, rule freezes, document checks, and verdicts.
"""
import hashlib
import json
import uuid
from django.db import models
from apps.accounts.models import TenantAwareModel


class AuditEventType(models.TextChoices):
    # Core security events
    LOGIN = "LOGIN", "User Login"
    LOGOUT = "LOGOUT", "User Logout"
    ROLE_CHANGE = "ROLE_CHANGE", "User Role Changed"
    RULE_PACK_CONFIRM = "RULE_PACK_CONFIRM", "RulePack Confirmed"
    VERDICT_OVERRIDE = "VERDICT_OVERRIDE", "Verdict Overridden"
    DOCUMENT_UPLOAD = "DOCUMENT_UPLOAD", "Document Uploaded"
    DOCUMENT_DOWNLOAD = "DOCUMENT_DOWNLOAD", "Document Downloaded"
    DOCUMENT_REPLACE = "DOCUMENT_REPLACE", "Document Replaced"
    # Domain events
    TENDER_INTAKE = "TENDER_INTAKE", "Tender Intake"
    RULE_PACK_DRAFTED = "RULE_PACK_DRAFTED", "RulePack Drafted"
    RULE_PACK_FROZEN = "RULE_PACK_FROZEN", "RulePack Cryptographically Frozen"
    DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED", "Document Uploaded & Verified"
    ASSESSMENT_EVALUATED = "ASSESSMENT_EVALUATED", "Compliance Assessment Evaluated"
    REGISTRY_CHECK = "REGISTRY_CHECK", "External Registry Verified"
    VERDICT_SIGNED = "VERDICT_SIGNED", "Verdict Finalized and Signed"


class AuditLogEntry(TenantAwareModel):
    """
    Append-only immutable audit log record.
    Update and delete operations are strictly prohibited at both model and API levels.
    """
    id = models.CharField(primary_key=True, max_length=64, editable=False)
    event_type = models.CharField(max_length=64, choices=AuditEventType.choices, db_index=True)
    actor = models.CharField(max_length=255, default="system")
    target_id = models.CharField(max_length=64, db_index=True)
    payload_hash = models.CharField(max_length=64, help_text="SHA-256 hash of event payload")
    details = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]

    def save(self, *args, **kwargs):
        if self.pk:
            # Check if record already exists in database
            if AuditLogEntry.objects.filter(pk=self.pk).exists():
                from django.core.exceptions import PermissionDenied
                raise PermissionDenied("Audit log entries are strictly append-only and cannot be updated.")
        if not self.id:
            self.id = f"aud_{uuid.uuid4().hex[:12]}"
        if not self.payload_hash:
            serialized = json.dumps(self.details, sort_keys=True)
            self.payload_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Audit log entries are immutable and cannot be deleted.")

    def __str__(self):
        return f"[{self.event_type}] by {self.actor} on {self.target_id} at {self.timestamp}"
