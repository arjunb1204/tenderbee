"""
API Views for RulePack Review, Human Confirmation, and Freezing.
Enforces:
- Only Reviewer or Owner can confirm/freeze rule packs.
- Once frozen, a rule pack is cryptographically immutable.
- Strict tenant isolation (404 on cross-tenant access).
"""
from rest_framework import status, generics, permissions
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from django.http import Http404

from apps.accounts.permissions import IsMember, IsReviewerOrOwner, TenantIsolationMixin
from apps.audit.models import AuditEventType
from apps.audit.services import record_audit_event
from apps.rules.models import RulePack, RulePackItem, RulePackStatus
from apps.rules.serializers import (
    RulePackFreezeSerializer,
    RulePackItemSerializer,
    RulePackItemUpdateSerializer,
    RulePackSerializer,
)


class RulePackPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 50


class RulePackListAPIView(TenantIsolationMixin, generics.ListAPIView):
    """
    GET /api/v1/rules/
    Lists RulePacks for the authenticated tenant organization.
    """
    queryset = RulePack.objects.all()
    serializer_class = RulePackSerializer
    permission_classes = [IsMember]
    pagination_class = RulePackPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        tender_id = self.request.query_params.get("tender_id")
        if tender_id:
            queryset = queryset.filter(tender_id=tender_id)
        return queryset


class RulePackDetailAPIView(TenantIsolationMixin, generics.RetrieveAPIView):
    """
    GET /api/v1/rules/<id>/
    Retrieves full details of a RulePack with cross-tenant 404 isolation.
    """
    serializer_class = RulePackSerializer
    permission_classes = [IsMember]
    queryset = RulePack.objects.all()
    lookup_field = "id"
    lookup_url_kwarg = "rule_pack_id"


class RulePackFreezeAPIView(APIView):
    """
    POST /api/v1/rules/<rule_pack_id>/confirm/
    Cryptographically freezes a draft RulePack with SHA-256 integrity hash.
    Strictly restricted to Reviewer and Owner roles.
    """
    permission_classes = [IsReviewerOrOwner]

    def post(self, request, rule_pack_id, *args, **kwargs):
        user = request.user
        org = user.organization

        try:
            rule_pack = RulePack.objects.get(id=rule_pack_id, organization=org)
        except RulePack.DoesNotExist:
            raise Http404("RulePack not found.")

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

        confirmed_by = serializer.validated_data.get("confirmed_by") or user.email
        rule_pack.freeze(confirmed_by_name=confirmed_by)

        # Append to audit trail
        record_audit_event(
            organization=org,
            actor=confirmed_by or user.email,
            event_type=AuditEventType.RULE_PACK_FROZEN,
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
    Allows human Reviewer/Owner to dismiss or modify a rule while the RulePack is in DRAFT.
    Modifications are strictly blocked once FROZEN.
    """
    permission_classes = [IsReviewerOrOwner]

    def patch(self, request, rule_pack_id, item_id, *args, **kwargs):
        user = request.user
        org = user.organization

        try:
            rule_pack = RulePack.objects.get(id=rule_pack_id, organization=org)
        except RulePack.DoesNotExist:
            raise Http404("RulePack not found.")

        if rule_pack.status == RulePackStatus.FROZEN:
            return Response(
                {"error": "Cannot modify rules in a FROZEN RulePack. Immutability violation."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            item = RulePackItem.objects.get(id=item_id, rule_pack=rule_pack)
        except RulePackItem.DoesNotExist:
            raise Http404("Rule item not found.")

        serializer = RulePackItemUpdateSerializer(item, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        return Response(RulePackItemSerializer(item).data, status=status.HTTP_200_OK)
