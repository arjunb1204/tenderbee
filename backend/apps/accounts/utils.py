"""
Tenant isolation utilities.
"""
def get_tenant_org_id(request) -> str:
    """
    Safely resolves the current tenant organization ID from authenticated user,
    JWT token claims, or request middleware attributes.
    """
    if getattr(request, "user", None) and getattr(request.user, "is_authenticated", False):
        if getattr(request.user, "organization_id", None):
            return str(request.user.organization_id)
    org_id = getattr(request, "org_id", "org_default")
    try:
        from apps.accounts.models import Organization
        Organization.objects.get_or_create(
            id=org_id,
            defaults={"name": "Default Workspace"}
        )
    except Exception:
        pass
    return org_id
