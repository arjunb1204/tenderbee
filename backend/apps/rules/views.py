"""
API Views for RulePack Review, Human Confirmation, and Freezing.
"""
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.utils import get_tenant_org_id
from apps.audit.models import AuditEventType, AuditLogEntry
from apps.rules.models import RulePack, RulePackItem, RulePackStatus
from apps.rules.serializers import (
    RulePackFreezeSerializer,
    RulePackItemSerializer,
    RulePackItemUpdateSerializer,
    RulePackSerializer,
)


class RulePackListAPIView(APIView):
    """
    GET /api/v1/rules/
    Lists RulePacks for the current tenant. Optionally filter by ?tender_id=<id>.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        org_id = get_tenant_org_id(request)
        tender_id = request.query_params.get("tender_id")
        queryset = RulePack.objects.filter(organization_id=org_id)
        if tender_id:
            queryset = queryset.filter(tender_id=tender_id)

        serializer = RulePackSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class RulePackDetailAPIView(APIView):
    """
    GET /api/v1/rules/<rule_pack_id>/
    Retrieves full details of a RulePack and all child rules.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, rule_pack_id, *args, **kwargs):
        org_id = get_tenant_org_id(request)
        try:
            rule_pack = RulePack.objects.get(id=rule_pack_id, organization_id=org_id)
        except RulePack.DoesNotExist:
            return Response(
                {"error": f"RulePack '{rule_pack_id}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = RulePackSerializer(rule_pack)
        return Response(serializer.data, status=status.HTTP_200_OK)


class RulePackFreezeAPIView(APIView):
    """
    POST /api/v1/rules/<rule_pack_id>/confirm/
    Cryptographically freezes a draft RulePack with SHA-256 integrity hash
    and writes an append-only audit event.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, rule_pack_id, *args, **kwargs):
        org_id = get_tenant_org_id(request)
        try:
            rule_pack = RulePack.objects.get(id=rule_pack_id, organization_id=org_id)
        except RulePack.DoesNotExist:
            return Response(
                {"error": f"RulePack '{rule_pack_id}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if rule_pack.status == RulePackStatus.FROZEN:
            return Response(
                {
                    "success": True,
                    "message": "RulePack is already cryptographically frozen.",
                    "rule_pack_id": rule_pack.id,
                    "frozen_hash": rule_pack.frozen_hash,
                },
                status=status.HTTP_200_OK,
            )

        serializer = RulePackFreezeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        confirmed_by = serializer.validated_data["confirmed_by"]
        rule_pack.freeze(confirmed_by_name=confirmed_by)

        # Append to audit trail
        AuditLogEntry.objects.create(
            organization_id=org_id,
            event_type=AuditEventType.RULE_PACK_FROZEN,
            actor=confirmed_by,
            target_id=rule_pack.id,
            details={
                "tender_id": rule_pack.tender_id,
                "version": rule_pack.version,
                "frozen_hash": rule_pack.frozen_hash,
                "confirmed_by": confirmed_by,
                "confirmed_at": rule_pack.confirmed_at.isoformat() if rule_pack.confirmed_at else None,
            },
        )

        return Response(
            {
                "success": True,
                "message": "RulePack cryptographically frozen and ready for deterministic compliance assessment.",
                "rule_pack_id": rule_pack.id,
                "status": rule_pack.status,
                "frozen_hash": rule_pack.frozen_hash,
                "confirmed_by": rule_pack.confirmed_by,
                "confirmed_at": rule_pack.confirmed_at,
            },
            status=status.HTTP_200_OK,
        )


class RuleItemUpdateAPIView(APIView):
    """
    PATCH /api/v1/rules/<rule_pack_id>/items/<item_id>/
    Allows human reviewer to dismiss or modify a rule while the RulePack is in DRAFT.
    Modifications are strictly blocked once FROZEN.
    """
    permission_classes = [permissions.AllowAny]

    def patch(self, request, rule_pack_id, item_id, *args, **kwargs):
        org_id = get_tenant_org_id(request)
        try:
            rule_pack = RulePack.objects.get(id=rule_pack_id, organization_id=org_id)
        except RulePack.DoesNotExist:
            return Response({"error": "RulePack not found."}, status=status.HTTP_404_NOT_FOUND)

        if rule_pack.status == RulePackStatus.FROZEN:
            return Response(
                {"error": "Cannot modify rules in a FROZEN RulePack. Immutability violation."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            item = RulePackItem.objects.get(id=item_id, rule_pack=rule_pack)
        except RulePackItem.DoesNotExist:
            return Response({"error": "Rule item not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = RulePackItemUpdateSerializer(item, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        return Response(RulePackItemSerializer(item).data, status=status.HTTP_200_OK)
