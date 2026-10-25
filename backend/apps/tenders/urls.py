"""
URL endpoints for Tender Management, Intake, Search, Schema, PDF Parsing, and RulePack Confirmation.
"""
from django.urls import path, re_path

from apps.tenders.views import (
    RulePackConfirmAPIView,
    RulePackDetailAPIView,
    TenderDetailAPIView,
    TenderIntakeAPIView,
    TenderListAPIView,
    TenderPDFUploadAPIView,
    TenderSchemaAPIView,
    TenderSearchAPIView,
)

app_name = "tenders"

urlpatterns = [
    re_path(r"^$", TenderListAPIView.as_view(), name="tender-list"),
    re_path(r"^schema/?$", TenderSchemaAPIView.as_view(), name="tender-schema"),
    re_path(r"^search/?$", TenderSearchAPIView.as_view(), name="tender-search"),
    re_path(r"^intake/?$", TenderIntakeAPIView.as_view(), name="tender-intake"),
    re_path(r"^upload-pdf/?$", TenderPDFUploadAPIView.as_view(), name="tender-upload-pdf"),
    re_path(r"^rule-pack/(?P<rule_pack_id>[^/]+)/?$", RulePackDetailAPIView.as_view(), name="rule-pack-detail"),
    re_path(r"^rule-pack/(?P<rule_pack_id>[^/]+)/confirm/?$", RulePackConfirmAPIView.as_view(), name="rule-pack-confirm"),
    re_path(r"^(?P<identifier>.+?)/?$", TenderDetailAPIView.as_view(), name="tender-detail"),
]
