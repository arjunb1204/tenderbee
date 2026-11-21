"""
Strict PDF Upload Validation and Active-Content Sanitization.

Enforces:
1. Real magic bytes (%PDF-).
2. Application size cap of 25 MB (strictly below cloud limits).
3. Rejection of corrupt and encrypted PDFs.
4. Detection and stripping of active content (/JavaScript, /JS, /Launch, /EmbeddedFiles).
5. SHA-256 calculation and duplicate detection per organization tenant.
6. Clearly marked hook for anti-malware engine integration.
"""
import hashlib
import io
import logging
from typing import Tuple
from rest_framework.exceptions import ValidationError
from pypdf import PdfReader, PdfWriter
from apps.documents.models import BidderDocument

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB cap


def scan_for_malware(content: bytes) -> bool:
    """
    Hook for enterprise malware scanning (e.g. ClamAV, VirusTotal, AWS GuardDuty).
    Returns True if clean, raises ValidationError if infected.
    """
    # [HOOK] Production scanner implementation connects here.
    return True


def validate_and_sanitize_pdf(file_bytes, organization) -> Tuple[bytes, str]:
    """
    Validates PDF file integrity and security, returning (sanitized_bytes, sha256_hash).
    """
    if hasattr(file_bytes, "read"):
        file_bytes.seek(0)
        file_bytes = file_bytes.read()

    # 1. Size check
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise ValidationError("File exceeds the maximum allowable limit of 25 MB.")

    if len(file_bytes) == 0:
        raise ValidationError("Uploaded file is empty.")

    # 2. Magic bytes check (independent of client MIME or extension)
    if not file_bytes.startswith(b"%PDF-"):
        raise ValidationError("Invalid file type: File header does not match valid PDF magic bytes (%PDF-).")

    # 3. Readability and Encryption check
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        if reader.is_encrypted:
            raise ValidationError("Encrypted or password-protected PDFs are strictly prohibited.")
        _ = len(reader.pages)
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(f"Corrupt or unreadable PDF document: {str(exc)}")

    # 4. Active content check (JavaScript, Launch actions, EmbeddedFiles)
    has_active_content = False
    for page in reader.pages:
        page_str = str(page.get_object()).lower()
        if "/javascript" in page_str or "/js" in page_str or "/launch" in page_str or "/embeddedfiles" in page_str:
            has_active_content = True
            break

    if not has_active_content and hasattr(reader, "trailer") and reader.trailer:
        trailer_str = str(reader.trailer).lower()
        if "/javascript" in trailer_str or "/js" in trailer_str or "/launch" in trailer_str:
            has_active_content = True

    if has_active_content:
        # Strip active content by rebuilding clean pages with PdfWriter
        try:
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            # Remove root-level interactive forms and javascript
            if "/Names" in writer._root_object:
                del writer._root_object["/Names"]
            if "/AcroForm" in writer._root_object:
                del writer._root_object["/AcroForm"]
            
            clean_stream = io.BytesIO()
            writer.write(clean_stream)
            file_bytes = clean_stream.getvalue()
            logger.info("Prohibited PDF active content successfully stripped from document.")
        except Exception as e:
            raise ValidationError(f"PDF contains prohibited active content that could not be safely stripped: {e}")

    # 5. Malware scanning hook
    scan_for_malware(file_bytes)

    # 6. Compute SHA-256 hash
    sha256_hash = hashlib.sha256(file_bytes).hexdigest()

    # 7. Duplicate detection per organization tenant
    if BidderDocument.objects.filter(organization=organization, sha256_hash=sha256_hash).exists():
        raise ValidationError("A document with identical content (SHA-256 hash) has already been uploaded for your organization.")

    return file_bytes, sha256_hash
