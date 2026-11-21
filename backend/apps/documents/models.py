"""
Bidder Document Models with SHA-256 integrity and cryptographic signature status.
"""
import uuid
from django.db import models
from apps.accounts.models import TenantAwareModel
from apps.tenders.models import Tender


class DocumentTypeEnum(models.TextChoices):
    UDYAM = "udyam_certificate", "Udyam MSME Registration"
    CA_TURNOVER = "ca_turnover_certificate", "CA Turnover Certificate & Balance Sheet"
    NSIC = "nsic_registration", "NSIC Enlistment Certificate"
    GST = "gst_certificate", "GST Registration Certificate"
    PAN = "pan_card", "PAN Card"
    WORK_EXP = "work_experience_certificate", "Work Experience Certificate"
    BANK_REF = "banking_reference_annexure_x", "Banking Reference (Annexure X)"
    TRUTHFULNESS = "truthfulness_undertaking_annexure_i", "Truthfulness Undertaking (Annexure I)"
    BID_FORM = "bid_form_annexure_ii", "Bid Form (Annexure II)"
    OTHER = "other", "Other Compliance Document"


class BidderDocument(TenantAwareModel):
    """
    Uploaded bidder document with file integrity verification (SHA-256)
    and pyHanko cryptographic signature validation.
    """
    id = models.CharField(primary_key=True, max_length=64, editable=False)
    tender = models.ForeignKey(
        Tender,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bidder_documents",
        db_index=True,
    )
    file_name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    document_type = models.CharField(
        max_length=64,
        choices=DocumentTypeEnum.choices,
        default=DocumentTypeEnum.OTHER,
        db_index=True,
    )
    file_size_bytes = models.BigIntegerField(default=0)
    sha256_hash = models.CharField(max_length=64, db_index=True)
    is_digitally_signed = models.BooleanField(default=False)
    signature_valid = models.BooleanField(default=False)
    signature_details = models.JSONField(default=dict)
    extracted_data = models.JSONField(default=dict)
    raw_text = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = f"doc_{uuid.uuid4().hex[:12]}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.file_name} ({self.document_type}) [{self.id}]"


class JobStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    PROCESSING = "PROCESSING", "Processing"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"


class AsyncJob(TenantAwareModel):
    """
    Tracks long-running asynchronous tasks (OCR, compliance eval, PDF extraction)
    with status, progress percentage, and tenant isolation.
    """
    id = models.CharField(primary_key=True, max_length=64, editable=False)
    job_type = models.CharField(max_length=64, default="document_processing")
    status = models.CharField(
        max_length=32,
        choices=JobStatus.choices,
        default=JobStatus.PENDING,
        db_index=True,
    )
    progress = models.PositiveIntegerField(default=0)
    target_id = models.CharField(max_length=64, blank=True)
    result = models.JSONField(default=dict)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = f"job_{uuid.uuid4().hex[:16]}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Job {self.id} ({self.job_type}) [{self.status} - {self.progress}%]"

