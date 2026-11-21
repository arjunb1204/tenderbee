"""
Plain Document Processing Tasks for TenderBee.
Designed as pure Python functions taking document_id and reading data
exclusively through services.storage adapter, allowing seamless execution
via Celery workers, background threads, or serverless functions.
"""
import io
import logging
from typing import Any, Dict, Optional
from pypdf import PdfReader
from apps.documents.models import AsyncJob, BidderDocument, JobStatus
from backend.services import storage

logger = logging.getLogger(__name__)


def process_document_job(document_id: str, job_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Plain function executing document OCR, digital signature inspection,
    and structured entity extraction.
    """
    job = None
    if job_id:
        try:
            job = AsyncJob.objects.get(id=job_id)
            job.status = JobStatus.PROCESSING
            job.progress = 20
            job.save(update_fields=["status", "progress"])
        except AsyncJob.DoesNotExist:
            pass

    try:
        doc = BidderDocument.objects.get(id=document_id)
        
        # 1. Read document bytes exclusively through the storage adapter
        raw_bytes = storage.get(doc.file_path)
        if not raw_bytes:
            raise FileNotFoundError(f"Object {doc.file_path} not found in storage backend.")

        if job:
            job.progress = 50
            job.save(update_fields=["progress"])

        # 2. Extract text from pages
        reader = PdfReader(io.BytesIO(raw_bytes))
        page_texts = []
        for idx, page in enumerate(reader.pages):
            page_texts.append(page.extract_text() or "")
        full_text = "\n\n".join(page_texts)

        # 3. Check for pyHanko digital signatures if present
        is_signed = False
        sig_details = {}
        try:
            from pyhanko.pdf_utils.reader import PdfFileReader
            from pyhanko.sign.validation import validate_pdf_signature
            ph_reader = PdfFileReader(io.BytesIO(raw_bytes))
            if ph_reader.embedded_signatures:
                is_signed = True
                sig_details = {"count": len(ph_reader.embedded_signatures), "signed": True}
        except Exception:
            pass

        # 4. Extract structured facts
        extracted = {}
        try:
            from apps.documents.services import DocumentPipelineService
            pipeline = DocumentPipelineService()
            pages_list = [{"page": i + 1, "text": t} for i, t in enumerate(page_texts)]
            extracted = pipeline._extract_structured_facts(doc.document_type, full_text, pages_list)
        except Exception as e:
            logger.warning("Fact extraction failed on %s: %s", doc.id, e)

        # 5. Update document record
        doc.raw_text = full_text[:50000]  # truncate to prevent excessive DB bloat
        doc.extracted_data = extracted or {}
        doc.is_digitally_signed = is_signed
        doc.signature_details = sig_details
        doc.save(update_fields=["raw_text", "extracted_data", "is_digitally_signed", "signature_details"])

        result_payload = {
            "document_id": doc.id,
            "page_count": len(reader.pages),
            "char_count": len(full_text),
            "is_digitally_signed": is_signed,
        }

        if job:
            job.status = JobStatus.COMPLETED
            job.progress = 100
            job.result = result_payload
            job.save(update_fields=["status", "progress", "result"])

        return result_payload

    except Exception as exc:
        logger.exception("Error processing document %s", document_id)
        if job:
            job.status = JobStatus.FAILED
            job.error = str(exc)
            job.save(update_fields=["status", "error"])
        raise
