"""
API Views for Immutable Audit Trail.
"""
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.utils import get_tenant_org_id
from apps.audit.models import AuditLogEntry
from apps.audit.serializers import AuditLogEntrySerializer


class AuditLogListAPIView(APIView):
    """
    GET /api/v1/audit/
    Retrieves immutable audit trail events for compliance verification,
    rule-freezes, and document intakes.
    """
    permission_classes = [permissions.AllowAny]
    def get(self, request, *args, **kwargs):
        org_id = get_tenant_org_id(request)
        queryset = AuditLogEntry.objects.filter(organization_id=org_id)

        target_id = request.query_params.get("target_id")
        if target_id:
            queryset = queryset.filter(target_id=target_id)

        event_type = request.query_params.get("event_type")
        if event_type:
            queryset = queryset.filter(event_type=event_type)

        serializer = AuditLogEntrySerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
