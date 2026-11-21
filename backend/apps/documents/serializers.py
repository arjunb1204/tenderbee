"""
Serializers for Bidder Document Upload and Verification Details.
"""
from rest_framework import serializers
from apps.documents.models import BidderDocument, DocumentTypeEnum


class BidderDocumentUploadSerializer(serializers.Serializer):
    file = serializers.FileField(required=True, help_text="PDF or scanned compliance certificate")
    document_type = serializers.ChoiceField(
        choices=DocumentTypeEnum.choices,
        default=DocumentTypeEnum.OTHER,
        help_text="Compliance document category (e.g. udyam_certificate, ca_turnover_certificate)",
    )
    tender_id = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Optional target tender ID to associate this document with",
    )


class BidderDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = BidderDocument
        fields = (
            "id",
            "tender",
            "file_name",
            "document_type",
            "file_size_bytes",
            "sha256_hash",
            "is_digitally_signed",
            "signature_valid",
            "signature_details",
            "extracted_data",
            "uploaded_at",
        )
        read_only_fields = fields


class AsyncJobSerializer(serializers.ModelSerializer):
    class Meta:
        from apps.documents.models import AsyncJob
        model = AsyncJob
        fields = (
            "id",
            "job_type",
            "status",
            "progress",
            "target_id",
            "result",
            "error",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields
