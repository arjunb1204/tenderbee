"""
URL endpoints for Bidder Document Upload and Integrity Management.
"""
from django.urls import path, re_path
from apps.documents.views import (
    DocumentDetailAPIView,
    DocumentDownloadAPIView,
    DocumentListAPIView,
    DocumentUploadAPIView,
    JobDetailAPIView,
)

app_name = "documents"

urlpatterns = [
    re_path(r"^/?$", DocumentListAPIView.as_view(), name="document-list"),
    re_path(r"^upload/?$", DocumentUploadAPIView.as_view(), name="document-upload"),
    re_path(r"^jobs/(?P<id>[^/]+)/?$", JobDetailAPIView.as_view(), name="document-job-detail"),
    re_path(r"^(?P<doc_id>[^/]+)/download/?$", DocumentDownloadAPIView.as_view(), name="document-download"),
    re_path(r"^(?P<id>[^/]+)/?$", DocumentDetailAPIView.as_view(), name="document-detail"),
]
