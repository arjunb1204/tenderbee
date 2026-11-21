"""
Accounts & Organization models with Multi-Tenant isolation.
"""
import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class Organization(models.Model):
    """
    Tenant entity isolating all tenders, documents, rulepacks, and verdicts.
    """
    id = models.CharField(primary_key=True, max_length=64, editable=False)
    name = models.CharField(max_length=255)
    gstin = models.CharField(max_length=15, blank=True, null=True)
    udyam_number = models.CharField(max_length=30, blank=True, null=True)
    pan = models.CharField(max_length=10, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = f"org_{uuid.uuid4().hex[:12]}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.id})"


class UserRole(models.TextChoices):
    OWNER = "owner", "Owner"
    REVIEWER = "reviewer", "Reviewer"
    MEMBER = "member", "Member"
    # Backward compatibility aliases
    ADMIN = "admin", "Admin (Legacy)"
    BID_MANAGER = "bid_manager", "Bid Manager (Legacy)"
    VIEWER = "viewer", "Viewer (Legacy)"


class User(AbstractUser):
    """
    Custom user model authenticated via email and linked to an Organization tenant.
    """
    email = models.EmailField(unique=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="members",
        null=True,
        blank=True,
    )
    role = models.CharField(
        max_length=32,
        choices=UserRole.choices,
        default=UserRole.MEMBER,
    )
    failed_login_attempts = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    @property
    def organization_id(self):
        return self.organization.id if self.organization else None

    @property
    def is_owner(self):
        return self.role in (UserRole.OWNER, UserRole.ADMIN)

    @property
    def is_reviewer_or_owner(self):
        return self.role in (UserRole.OWNER, UserRole.REVIEWER, UserRole.ADMIN, UserRole.BID_MANAGER)

    @property
    def is_member(self):
        return bool(self.organization_id)

    def is_locked(self):
        from django.utils import timezone
        return bool(self.locked_until and self.locked_until > timezone.now())

    def reset_lockout(self):
        self.failed_login_attempts = 0
        self.locked_until = None
        self.save(update_fields=["failed_login_attempts", "locked_until"])

    def record_failed_login(self, max_attempts=5, lockout_minutes=15):
        from django.utils import timezone
        from datetime import timedelta
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= max_attempts:
            self.locked_until = timezone.now() + timedelta(minutes=lockout_minutes)
        self.save(update_fields=["failed_login_attempts", "locked_until"])

    def __str__(self):
        return f"{self.email} [{self.role}]"


class TenantAwareModel(models.Model):
    """
    Abstract base model enforcing organization tenant isolation and audit timestamps.
    """
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="%(class)ss",
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
