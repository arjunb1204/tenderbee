"""
API Views for Tender Intake, PDF Parsing, and RulePack Management.
"""
import os
import tempfile
from pathlib import Path
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.tenders.services import TenderService
from backend.apps.tenders.serializers import (
    RulePackConfirmSerializer,
    TenderIntakeRequestSerializer,
    TenderPDFUploadSerializer,
)


class TenderIntakeAPIView(APIView):
    """
    POST /api/tenders/intake/
    Accepts a procurement URL or tender number, scrapes or loads from cache,
    and automatically drafts an executable RulePack.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = TenderIntakeRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        identifier = serializer.validated_data["identifier"]
        org_id = serializer.validated_data["org_id"]
        force_refresh = serializer.validated_data["force_refresh"]

        service = TenderService()
        result = service.intake_tender(
            identifier=identifier,
            org_id=org_id,
            force_refresh=force_refresh,
        )

        if not result.get("success"):
            return Response(result, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        return Response(result, status=status.HTTP_200_OK)


class TenderPDFUploadAPIView(APIView):
    """
    POST /api/tenders/upload-pdf/
    Uploads an Indian procurement tender PDF, extracts clauses and parameters,
    and returns a structured JSON schema along with a draft RulePack.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = TenderPDFUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        pdf_file = serializer.validated_data["pdf_file"]
        org_id = serializer.validated_data["org_id"]

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            for chunk in pdf_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        try:
            service = TenderService()
            result = service.intake_tender_pdf(pdf_path=tmp_path, org_id=org_id)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"success": False, "error": f"PDF parsing failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


class RulePackConfirmAPIView(APIView):
    """
    POST /api/tenders/rule-pack/<rule_pack_id>/confirm/
    Locks and freezes a draft RulePack with cryptographic SHA-256 integrity hash.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, rule_pack_id, *args, **kwargs):
        serializer = RulePackConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        confirmed_by = serializer.validated_data["confirmed_by"]
        service = TenderService()
        result = service.confirm_rule_pack(rule_pack_id=rule_pack_id, confirmed_by=confirmed_by)

        if not result.get("success"):
            return Response(result, status=status.HTTP_404_NOT_FOUND)

        return Response(result, status=status.HTTP_200_OK)


class RulePackDetailAPIView(APIView):
    """
    GET /api/tenders/rule-pack/<rule_pack_id>/
    Retrieves a RulePack by ID.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, rule_pack_id, *args, **kwargs):
        service = TenderService()
        rule_pack = service.get_rule_pack(rule_pack_id=rule_pack_id)
        if not rule_pack:
            return Response(
                {"success": False, "error": f"RulePack '{rule_pack_id}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(rule_pack.model_dump(), status=status.HTTP_200_OK)


class TenderSearchAPIView(APIView):
    """
    GET  /api/v1/tenders/search/?q=services+in+bihar
    POST /api/v1/tenders/search/ {"prompt": "services in bihar above 1 cr"}
    Discovery engine supporting natural language and multi-criteria filters.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        from backend.apps.tenders.search import TenderSearchService, TenderSearchFilter

        prompt = request.query_params.get("q") or request.query_params.get("prompt")
        service = TenderSearchService()
        if prompt:
            res = service.search_by_prompt(prompt)
            return Response(res, status=status.HTTP_200_OK)

        min_val = None
        if "min_value" in request.query_params:
            try:
                min_val = float(request.query_params["min_value"])
            except ValueError:
                pass

        max_val = None
        if "max_value" in request.query_params:
            try:
                max_val = float(request.query_params["max_value"])
            except ValueError:
                pass

        tenure = None
        if "tenure" in request.query_params:
            try:
                tenure = int(request.query_params["tenure"])
            except ValueError:
                pass

        t_num = (
            request.query_params.get("tender_number")
            or request.query_params.get("tender_no")
            or request.query_params.get("tender_id")
            or request.query_params.get("rfq_id")
        )

        filters = TenderSearchFilter(
            query=request.query_params.get("query"),
            tender_number=t_num,
            state=request.query_params.get("state"),
            category=request.query_params.get("category"),
            min_value_inr=min_val,
            max_value_inr=max_val,
            min_tenure_months=tenure,
            buyer_name=request.query_params.get("buyer"),
        )
        res = service.search(filters)
        return Response(res, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        from backend.apps.tenders.search import TenderSearchService, TenderSearchFilter

        prompt = request.data.get("prompt") or request.data.get("q")
        service = TenderSearchService()
        if prompt:
            res = service.search_by_prompt(prompt)
            return Response(res, status=status.HTTP_200_OK)

        try:
            filters = TenderSearchFilter(**request.data)
            res = service.search(filters)
            return Response(res, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class TenderSchemaAPIView(APIView):
    """
    GET /api/v1/tenders/schema/
    Returns the formal JSON Schema for Tender Notice Extractions.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        from backend.engine.schema import TenderPDFExtractionResult
        return Response(TenderPDFExtractionResult.get_json_schema(), status=status.HTTP_200_OK)


class TenderListAPIView(APIView):
    """
    GET /api/v1/tenders/
    Lists tenders belonging to the current tenant.
    """
    def get(self, request, *args, **kwargs):
        from apps.accounts.utils import get_tenant_org_id
        from apps.tenders.models import Tender
        from apps.tenders.serializers import TenderSerializer
        org_id = get_tenant_org_id(request)
        tenders = Tender.objects.filter(organization_id=org_id)
        serializer = TenderSerializer(tenders, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class TenderDetailAPIView(APIView):
    """
    GET /api/v1/tenders/<identifier>/?mode=skim|detailed
    Two viewing modes:
    - 'skim': Fast high-level overview
    - 'detailed': Complete breakdown including parsed PDF clauses, page citations, and rule pack
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, identifier=None, tender_id=None, *args, **kwargs):
        target_id = identifier or tender_id
        mode = request.query_params.get("mode", "skim").lower()
        if mode not in ("skim", "detailed"):
            mode = "skim"

        service = TenderService()
        result = service.get_tender(identifier=target_id, mode=mode)
        if result:
            return Response(result, status=status.HTTP_200_OK)

        if request.user and request.user.is_authenticated:
            from apps.accounts.utils import get_tenant_org_id
            from apps.tenders.models import Tender
            from apps.tenders.serializers import TenderSerializer
            org_id = get_tenant_org_id(request)
            try:
                tender = Tender.objects.get(id=target_id, organization_id=org_id)
                serializer = TenderSerializer(tender)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except Exception:
                pass

        return Response(
            {"success": False, "error": f"Tender '{target_id}' not found."},
            status=status.HTTP_404_NOT_FOUND,
        )


class TenderPortalsAPIView(APIView):
    """
    GET /api/v1/tenders/portals/
    Returns complete directory of all 36 Indian State and Union Territory e-Procurement portals,
    plus central platforms (GeM, CPPP, IREPS, Infralens).
    Supports ?type=State|Union Territory|Central and ?q=<search_text>.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        from backend.services.live_search import STATE_PORTAL_REGISTRY

        portal_type = request.query_params.get("type")
        q = (request.query_params.get("q") or "").strip().lower()

        portals = list(STATE_PORTAL_REGISTRY)

        if portal_type:
            portals = [p for p in portals if p.get("type", "").lower() == portal_type.lower()]

        if q:
            portals = [
                p for p in portals
                if q in p["name"].lower()
                or q in p["domain"].lower()
                or q in p["code"].lower()
                or q in p["portal_name"].lower()
            ]

        return Response(
            {
                "success": True,
                "total": len(portals),
                "portals": portals,
            },
            status=status.HTTP_200_OK,
        )


