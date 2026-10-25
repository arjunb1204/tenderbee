"""
API Views for Bidder Document Upload, Integrity Checking, and Extraction.
"""
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.utils import get_tenant_org_id
from apps.documents.models import BidderDocument
from apps.documents.serializers import (
    BidderDocumentSerializer,
    BidderDocumentUploadSerializer,
)
from apps.documents.services import DocumentPipelineService


class DocumentUploadAPIView(APIView):
    """
    POST /api/v1/documents/upload/
    Accepts document upload, performs SHA-256 integrity checks,
    pyHanko cryptographic signature validation, text extraction,
    and schema-constrained entity extraction.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = BidderDocumentUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        uploaded_file = serializer.validated_data["file"]
        document_type = serializer.validated_data["document_type"]
        tender_id = serializer.validated_data.get("tender_id")
        org_id = get_tenant_org_id(request)

        pipeline = DocumentPipelineService()
        doc = pipeline.process_document(
            file_obj=uploaded_file,
            file_name=uploaded_file.name,
            document_type=document_type,
            organization_id=org_id,
            tender_id=tender_id if tender_id else None,
        )

        return Response(
            {
                "success": True,
                "document": BidderDocumentSerializer(doc).data,
            },
            status=status.HTTP_201_CREATED,
        )


class DocumentListAPIView(APIView):
    """
    GET /api/v1/documents/
    Lists documents uploaded by the current tenant organization.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        org_id = get_tenant_org_id(request)
        queryset = BidderDocument.objects.filter(organization_id=org_id)

        tender_id = request.query_params.get("tender_id")
        if tender_id:
            queryset = queryset.filter(tender_id=tender_id)

        doc_type = request.query_params.get("document_type")
        if doc_type:
            queryset = queryset.filter(document_type=doc_type)

        serializer = BidderDocumentSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DocumentDetailAPIView(APIView):
    """
    GET /api/v1/documents/<doc_id>/
    Retrieves full verification, integrity, and extraction details for a document.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, doc_id, *args, **kwargs):
        org_id = get_tenant_org_id(request)
        try:
            doc = BidderDocument.objects.get(id=doc_id, organization_id=org_id)
        except BidderDocument.DoesNotExist:
            return Response(
                {"error": f"Document '{doc_id}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = BidderDocumentSerializer(doc)
        return Response(serializer.data, status=status.HTTP_200_OK)
