"""
API Views for Immutable Audit Trail.
Append-only: List and Retrieve operations only. Modifying or deleting audit records is impossible.
"""
from rest_framework import generics
from rest_framework.pagination import PageNumberPagination
from apps.accounts.permissions import IsMember, TenantIsolationMixin
from apps.audit.models import AuditLogEntry
from apps.audit.serializers import AuditLogEntrySerializer


class AuditPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class AuditLogListAPIView(TenantIsolationMixin, generics.ListAPIView):
    """
    GET /api/v1/audit/
    Retrieves paginated immutable audit trail events for the authenticated organization.
    """
    queryset = AuditLogEntry.objects.all()
    serializer_class = AuditLogEntrySerializer
    permission_classes = [IsMember]
    pagination_class = AuditPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        target_id = self.request.query_params.get("target_id")
        if target_id:
            queryset = queryset.filter(target_id=target_id)
        event_type = self.request.query_params.get("event_type")
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        return queryset


class AuditLogDetailAPIView(TenantIsolationMixin, generics.RetrieveAPIView):
    """
    GET /api/v1/audit/<id>/
    Retrieves a single immutable audit entry by ID with cross-tenant 404 protection.
    """
    serializer_class = AuditLogEntrySerializer
    permission_classes = [IsMember]
    queryset = AuditLogEntry.objects.all()
    lookup_field = "id"
