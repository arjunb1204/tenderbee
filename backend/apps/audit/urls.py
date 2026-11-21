"""
URL endpoints for Immutable Audit Trail.
"""
from django.urls import path
from apps.audit.views import AuditLogListAPIView, AuditLogDetailAPIView

app_name = "audit"

urlpatterns = [
    path("", AuditLogListAPIView.as_view(), name="audit-list"),
    path("<str:id>/", AuditLogDetailAPIView.as_view(), name="audit-detail"),
]
