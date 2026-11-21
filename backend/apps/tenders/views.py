"""
API Views for Tender Intake, PDF Parsing, and RulePack Management.
"""
import os
import tempfile
from pathlib import Path
from rest_framework import status, permissions, generics
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.accounts.permissions import IsMember, TenantIsolationMixin

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
        raw_query = request.query_params.get("query")
        effective_text = (prompt or raw_query or "").strip()

        state_param = request.query_params.get("state")
        if state_param and state_param.strip().lower() in ("all", "all states", "none", ""):
            state_param = None
        elif state_param:
            state_param = state_param.strip()

        city_param = request.query_params.get("city") or request.query_params.get("city_or_district")
        category_param = request.query_params.get("category")
        portal_param = request.query_params.get("portal")
        if portal_param and portal_param.strip().lower() in ("all", "none", ""):
            portal_param = None
        elif portal_param:
            portal_param = portal_param.strip()

        nationwide_raw = (request.query_params.get("nationwide") or "false").strip().lower()
        nationwide = nationwide_raw in ("true", "1", "yes")

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

        service = TenderSearchService()

        # If natural language text is provided, parse it and overlay explicit structured filters
        if effective_text:
            parsed = service.parse_prompt_to_filters(effective_text)
            # Explicit user-selected filters strictly override parsed values
            if state_param:
                parsed.state = state_param
            if city_param:
                parsed.city_or_district = city_param
            if category_param:
                parsed.category = category_param
            if portal_param:
                parsed.portal = portal_param
            if min_val is not None:
                parsed.min_value_inr = min_val
            if max_val is not None:
                parsed.max_value_inr = max_val
            if tenure is not None:
                parsed.min_tenure_months = tenure
            if t_num:
                parsed.tender_number = t_num
            parsed.nationwide = nationwide

            res = service.search(parsed, raw_prompt=effective_text)
            res["interpreted_prompt"] = effective_text
            return Response(res, status=status.HTTP_200_OK)

        # Empty search protection: if no text query, no state, no portal, and no tender number, return empty result
        if not state_param and not t_num and not category_param and not portal_param and not nationwide:
            return Response({
                "success": True,
                "applied_filters": {
                    "query": None,
                    "state": None,
                    "category": None,
                    "portal": None,
                    "nationwide": False,
                },
                "total_matches": 0,
                "page": 1,
                "limit": 20,
                "source": "empty_criteria",
                "results": [],
                "message": "Please enter a search query or select a state to discover tenders.",
            }, status=status.HTTP_200_OK)

        filters = TenderSearchFilter(
            query=raw_query,
            tender_number=t_num,
            state=state_param,
            city_or_district=city_param,
            category=category_param,
            portal=portal_param,
            min_value_inr=min_val,
            max_value_inr=max_val,
            min_tenure_months=tenure,
            buyer_name=request.query_params.get("buyer"),
            nationwide=nationwide,
        )
        res = service.search(filters)
        return Response(res, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        from backend.apps.tenders.search import TenderSearchService, TenderSearchFilter

        prompt = request.data.get("prompt") or request.data.get("q")
        raw_query = request.data.get("query")
        effective_text = (prompt or raw_query or "").strip()

        state_param = request.data.get("state")
        if state_param and state_param.strip().lower() in ("all", "all states", "none", ""):
            state_param = None
        elif state_param:
            state_param = state_param.strip()

        portal_param = request.data.get("portal")
        if portal_param and portal_param.strip().lower() in ("all", "none", ""):
            portal_param = None
        elif portal_param:
            portal_param = portal_param.strip()

        nationwide = bool(request.data.get("nationwide", False))

        service = TenderSearchService()
        if effective_text:
            parsed = service.parse_prompt_to_filters(effective_text)
            if state_param:
                parsed.state = state_param
            if portal_param:
                parsed.portal = portal_param
            if request.data.get("category"):
                parsed.category = request.data.get("category")
            if request.data.get("min_value_inr"):
                parsed.min_value_inr = float(request.data["min_value_inr"])
            if request.data.get("max_value_inr"):
                parsed.max_value_inr = float(request.data["max_value_inr"])
            if request.data.get("tender_number"):
                parsed.tender_number = request.data["tender_number"]
            parsed.nationwide = nationwide

            res = service.search(parsed, raw_prompt=effective_text)
            res["interpreted_prompt"] = effective_text
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


class TenderListAPIView(TenantIsolationMixin, generics.ListAPIView):
    """
    GET /api/v1/tenders/
    Lists tenders belonging strictly to the authenticated tenant organization.
    """
    permission_classes = [IsMember]
    pagination_class = PageNumberPagination

    def get_serializer_class(self):
        from apps.tenders.serializers import TenderSerializer
        return TenderSerializer

    def get_queryset(self):
        from apps.tenders.models import Tender
        return Tender.objects.filter(organization=self.request.user.organization)


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


