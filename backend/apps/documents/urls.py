"""
URL endpoints for Bidder Document Upload and Integrity Management.
"""
from django.urls import path, re_path
from apps.documents.views import (
    DocumentDetailAPIView,
    DocumentListAPIView,
    DocumentUploadAPIView,
)

app_name = "documents"

urlpatterns = [
    re_path(r"^$", DocumentListAPIView.as_view(), name="document-list"),
    re_path(r"^upload/?$", DocumentUploadAPIView.as_view(), name="document-upload"),
    re_path(r"^(?P<doc_id>[^/]+)/?$", DocumentDetailAPIView.as_view(), name="document-detail"),
]
