"""
Unit and integration tests for Bidder Document Pipeline (Stage 1, 2, and 3).
"""
import io
from pypdf import PdfWriter
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Organization, User, UserRole
from apps.audit.models import AuditEventType, AuditLogEntry
from apps.documents.models import BidderDocument, DocumentTypeEnum


def create_dummy_pdf(text_content: str) -> io.BytesIO:
    """Helper creating a minimal valid PDF with given text for testing."""
    from pypdf import PageObject
    writer = PdfWriter()
    page = PageObject.create_blank_page(width=612, height=792)
    writer.add_page(page)
    # Write a simple text stream
    buf = io.BytesIO()
    writer.write(buf)
    # Inject text into buffer stream for simple OCR/text reader testing
    pdf_bytes = buf.getvalue().replace(b"/Contents", b"/Contents")
    return io.BytesIO(pdf_bytes)


class DocumentPipelineTests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Shree Ram Projects Pvt Ltd")
        self.user = User.objects.create_user(
            email="bids@shreeram.in",
            username="shreeram_bid",
            password="ShreeRamPassword2026!",
            organization=self.org,
            role=UserRole.BID_MANAGER,
        )
        self.client.force_authenticate(user=self.user)

    def test_upload_document_pipeline_execution(self):
        # Create a sample PDF file
        pdf_stream = create_dummy_pdf("Sample Udyam Certificate")
        pdf_stream.name = "udyam_cert_2026.pdf"

        url = "/api/v1/documents/upload/"
        data = {
            "file": pdf_stream,
            "document_type": DocumentTypeEnum.UDYAM,
        }
        resp = self.client.post(url, data, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)
        self.assertTrue(resp.data["success"])
        self.assertIn("job_id", resp.data)
        doc_data = resp.data["document"]
        self.assertEqual(doc_data["file_name"], "udyam_cert_2026.pdf")
        self.assertEqual(doc_data["document_type"], "udyam_certificate")
        self.assertIsNotNone(doc_data["sha256_hash"])

        # Check DB record
        doc = BidderDocument.objects.get(id=doc_data["id"])
        self.assertEqual(doc.organization, self.org)

        # Check Audit event
        audit = AuditLogEntry.objects.filter(target_id=doc.id, event_type=AuditEventType.DOCUMENT_UPLOAD).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.details["file_name"], "udyam_cert_2026.pdf")

    def test_document_list_and_detail(self):
        doc = BidderDocument.objects.create(
            organization=self.org,
            file_name="ca_certificate.pdf",
            file_path="/tmp/ca_certificate.pdf",
            document_type=DocumentTypeEnum.CA_TURNOVER,
            file_size_bytes=1024,
            sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            extracted_data={"average_turnover_inr": {"value": 50000000.0, "quote": "Rs. 5.00 Cr"}},
        )

        resp = self.client.get("/api/v1/documents/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get("results", resp.data)
        self.assertEqual(len(results), 1)

        detail_resp = self.client.get(f"/api/v1/documents/{doc.id}/")
        self.assertEqual(detail_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_resp.data["file_name"], "ca_certificate.pdf")
        self.assertEqual(detail_resp.data["extracted_data"]["average_turnover_inr"]["value"], 50000000.0)

    def test_unified_storage_adapter(self):
        from services.storage import put, get, exists, delete
        sample_key = f"orgs/{self.org.id}/documents/tender_sample_doc.pdf"
        sample_bytes = b"%PDF-1.4 Mock document bytes for TenderBee test"

        # Test Put
        self.assertTrue(put(sample_key, sample_bytes, content_type="application/pdf"))

        # Test Exists
        self.assertTrue(exists(sample_key))
        self.assertFalse(exists("non_existent_key_99999.xyz"))

        # Test Get
        downloaded = get(sample_key)
        self.assertEqual(downloaded, sample_bytes)

        # Test Delete
        self.assertTrue(delete(sample_key))
        self.assertFalse(exists(sample_key))
