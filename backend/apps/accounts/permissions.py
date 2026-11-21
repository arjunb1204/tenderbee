"""
Unified RBAC Permissions and Multi-Tenant Isolation for TenderBee.

Roles per organization:
- member: Upload documents, view own org tenders, assessments, and evidence, run assessments.
- reviewer: Member abilities + confirm/freeze rule packs, review/override verdicts, approve proposals.
- owner: Reviewer abilities + manage organization profile and members.
"""
from rest_framework import permissions
from django.http import Http404


class IsMember(permissions.BasePermission):
    """
    Grants access to authenticated members belonging to an active Organization tenant,
    or development/demo fallback.
    """
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if user and user.is_authenticated and getattr(user, "organization_id", None):
            return True
        from django.conf import settings
        if getattr(settings, "DEBUG", False):
            return True
        return False

    def has_object_permission(self, request, view, obj):
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated and getattr(user, "organization_id", None)):
            from django.conf import settings
            return bool(getattr(settings, "DEBUG", False))
        # Object must match user's organization
        obj_org_id = getattr(obj, "organization_id", None)
        if hasattr(obj, "organization") and obj.organization:
            obj_org_id = str(obj.organization.id)
        return str(obj_org_id) == str(user.organization_id)


class IsReviewerOrOwner(permissions.BasePermission):
    """
    Grants access to Reviewers and Owners.
    Can confirm/freeze rule packs, review & override verdicts, approve proposals.
    """
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if user and user.is_authenticated and getattr(user, "organization_id", None) and getattr(user, "is_reviewer_or_owner", False):
            return True
        from django.conf import settings
        if getattr(settings, "DEBUG", False):
            return True
        return False

    def has_object_permission(self, request, view, obj):
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated and getattr(user, "organization_id", None) and user.is_reviewer_or_owner):
            from django.conf import settings
            return bool(getattr(settings, "DEBUG", False))
        obj_org_id = getattr(obj, "organization_id", None)
        if hasattr(obj, "organization") and obj.organization:
            obj_org_id = str(obj.organization.id)
        return str(obj_org_id) == str(user.organization_id)


class IsOwner(permissions.BasePermission):
    """
    Grants access exclusively to Organization Owners.
    Can manage organization settings, profile, and team members.
    """
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if user and user.is_authenticated and getattr(user, "organization_id", None) and getattr(user, "is_owner", False):
            return True
        from django.conf import settings
        if getattr(settings, "DEBUG", False):
            return True
        return False

    def has_object_permission(self, request, view, obj):
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated and getattr(user, "organization_id", None) and user.is_owner):
            from django.conf import settings
            return bool(getattr(settings, "DEBUG", False))
        obj_org_id = getattr(obj, "organization_id", None)
        if hasattr(obj, "organization") and obj.organization:
            obj_org_id = str(obj.organization.id)
        return str(obj_org_id) == str(user.organization_id)


class TenantIsolationMixin:
    """
    Ensures every queryset and object lookup is strictly isolated by the user's organization.
    Crucially: Accessing another tenant's object raises 404 Not Found (NEVER 403),
    preventing ID enumeration or existence confirmation.
    """
    def get_queryset(self):
        qs = super().get_queryset()
        user = getattr(self.request, "user", None)
        if not user or not user.is_authenticated or not getattr(user, "organization", None):
            from apps.accounts.utils import get_tenant_org_id
            org_id = get_tenant_org_id(self.request)
            model = qs.model
            if hasattr(model, "organization_id"):
                return qs.filter(organization_id=org_id)
            elif hasattr(model, "organization"):
                return qs.filter(organization_id=org_id)
            return qs.none()
        
        # Support both direct organization foreign key and models where org is referenced
        model = qs.model
        if hasattr(model, "organization"):
            return qs.filter(organization=user.organization)
        elif hasattr(model, "organization_id"):
            return qs.filter(organization_id=user.organization_id)
        return qs

    def get_object(self):
        """
        Enforce strict 404 on cross-tenant object access.
        """
        try:
            obj = super().get_object()
        except Exception:
            raise Http404("Resource not found.")
        
        user = getattr(self.request, "user", None)
        if not user or not user.is_authenticated or not getattr(user, "organization", None):
            from apps.accounts.utils import get_tenant_org_id
            org_id = get_tenant_org_id(self.request)
            obj_org = getattr(obj, "organization_id", None)
            if hasattr(obj, "organization") and obj.organization:
                obj_org = str(obj.organization.id)
            if obj_org and str(obj_org) != str(org_id):
                raise Http404("Resource not found.")
            return obj
            
        obj_org = getattr(obj, "organization_id", None)
        if hasattr(obj, "organization") and obj.organization:
            obj_org = str(obj.organization.id)
            
        if obj_org and str(obj_org) != str(user.organization_id):
            # Return 404 instead of 403 to prevent confirming object existence across tenants
            raise Http404("Resource not found.")
            
        return obj
