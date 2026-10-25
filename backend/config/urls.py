"""
Root URL Configuration for TenderBee Backend.
Mounts /api/v1/ and core administrative/health endpoints.
"""
from django.contrib import admin
from django.urls import include, path, re_path
from django.http import JsonResponse
from django.conf import settings
from django.conf.urls.static import static


def health_check(request):
    """Liveness and health check endpoint."""
    return JsonResponse({
        "status": "healthy",
        "service": "TenderBee Core API",
        "version": "1.0.0",
        "tenant_id": getattr(request, "org_id", "org_default"),
    })


def api_root(request):
    """Root landing endpoint returning service info and available API endpoints."""
    return JsonResponse({
        "service": "TenderBee Core API",
        "version": "1.0.0",
        "status": "online",
        "documentation": "TenderBee Deterministic Verification & Procurement Platform",
        "endpoints": {
            "health": "/api/health/",
            "admin": "/admin/",
            "auth": {
                "register": "/api/v1/auth/register/",
                "token": "/api/v1/auth/token/",
                "refresh": "/api/v1/auth/refresh/",
                "me": "/api/v1/auth/me/",
            },
            "tenders": "/api/v1/tenders/",
            "rules": "/api/v1/rules/",
            "documents": "/api/v1/documents/",
            "verify": "/api/v1/verify/",
            "evidence": "/api/v1/evidence/",
            "audit": "/api/v1/audit/",
            "find": "/api/v1/find/",
            "prepare": "/api/v1/prepare/",
        },
    })


urlpatterns = [
    path("", api_root, name="api-root"),
    path("admin/", admin.site.urls),
    path("api-auth/", include("rest_framework.urls")),
    path("api/health/", health_check, name="health-check"),

    # API v1 routes
    re_path(r"^api/v1/auth/?", include("apps.accounts.urls")),
    re_path(r"^api/v1/tenders/?", include("apps.tenders.urls")),
    re_path(r"^api/v1/rules/?", include("apps.rules.urls")),
    re_path(r"^api/v1/documents/?", include("apps.documents.urls")),
    re_path(r"^api/v1/verify/?", include("apps.verify.urls")),
    re_path(r"^api/v1/evidence/?", include("apps.evidence.urls")),
    re_path(r"^api/v1/audit/?", include("apps.audit.urls")),
    re_path(r"^api/v1/find/?", include("apps.find.urls")),
    re_path(r"^api/v1/prepare/?", include("apps.prepare.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
