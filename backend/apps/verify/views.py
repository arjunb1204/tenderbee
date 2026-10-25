"""
API Views for Verification Assessments, Deterministic Rules Execution, and Registry Lookups.
"""
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.utils import get_tenant_org_id
from apps.verify.models import VerificationAssessment
from apps.verify.serializers import (
    AssessmentRequestSerializer,
    VerificationAssessmentSerializer,
)
from apps.verify.services import VerificationService


class AssessmentEvaluateAPIView(APIView):
    """
    POST /api/v1/verify/evaluate/
    Executes the 7-stage verification pipeline for a bidder on a specific tender.
    Returns composite verdict (READY, NEEDS_REVIEW, BLOCKED), rule-by-rule verdicts,
    missing documents, actionable FixList, and external registry validations.
    """
    permission_classes = [permissions.AllowAny]
    def post(self, request, *args, **kwargs):
        serializer = AssessmentRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        tender_id = serializer.validated_data["tender_id"]
        rule_pack_id = serializer.validated_data.get("rule_pack_id")
        org_id = get_tenant_org_id(request)
        actor = getattr(request.user, "email", "compliance_user")

        service = VerificationService()
        result = service.run_assessment(
            tender_id=tender_id,
            organization_id=org_id,
            rule_pack_id=rule_pack_id if rule_pack_id else None,
            actor=actor,
        )

        if not result.get("success"):
            return Response(result, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        return Response(result, status=status.HTTP_200_OK)


class AssessmentListAPIView(APIView):
    """
    GET /api/v1/verify/assessments/
    Lists previous assessments for the tenant organization.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        org_id = get_tenant_org_id(request)
        queryset = VerificationAssessment.objects.filter(organization_id=org_id)

        tender_id = request.query_params.get("tender_id")
        if tender_id:
            queryset = queryset.filter(tender_id=tender_id)

        serializer = VerificationAssessmentSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AssessmentDetailAPIView(APIView):
    """
    GET /api/v1/verify/assessments/<assessment_id>/
    Retrieves full audit report for a previous assessment.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, assessment_id, *args, **kwargs):
        org_id = get_tenant_org_id(request)
        try:
            assessment = VerificationAssessment.objects.get(
                id=assessment_id,
                organization_id=org_id,
            )
        except VerificationAssessment.DoesNotExist:
            return Response(
                {"error": f"Assessment '{assessment_id}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = VerificationAssessmentSerializer(assessment)
        return Response(serializer.data, status=status.HTTP_200_OK)
