"""
URL endpoints for Compliance Assessment, Verification, and Verdicts.
"""
from django.urls import path
from apps.verify.views import (
    AssessmentDetailAPIView,
    AssessmentEvaluateAPIView,
    AssessmentListAPIView,
    AssessmentVerdictOverrideAPIView,
    ComplianceDossierAPIView,
    ComplianceDossierPDFAPIView,
)

app_name = "verify"

urlpatterns = [
    path("evaluate/", AssessmentEvaluateAPIView.as_view(), name="assessment-evaluate"),
    path("assessments/", AssessmentListAPIView.as_view(), name="assessment-list"),
    path("assessments/<str:id>/", AssessmentDetailAPIView.as_view(), name="assessment-detail"),
    path("assessments/<str:assessment_id>/override/", AssessmentVerdictOverrideAPIView.as_view(), name="assessment-verdict-override"),
    path("dossier/", ComplianceDossierAPIView.as_view(), name="compliance-dossier"),
    path("dossier/pdf/", ComplianceDossierPDFAPIView.as_view(), name="compliance-dossier-pdf"),
]
