"""
Structured Security Logging Filter and Context Middleware for TenderBee.
Injects request_id, user_id, and organization_id into all log records,
strictly omitting personal data, tokens, passwords, and raw document text.
"""
import logging
import uuid
from typing import Optional
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class SecurityContextFilter(logging.Filter):
    """
    Injects request_id, user_id, and org_id into log records.
    """
    def filter(self, record):
        if not hasattr(record, "request_id"):
            record.request_id = getattr(_thread_local, "request_id", "-")
        if not hasattr(record, "user_id"):
            record.user_id = getattr(_thread_local, "user_id", "anonymous")
        if not hasattr(record, "org_id"):
            record.org_id = getattr(_thread_local, "org_id", "none")
        return True


import threading
_thread_local = threading.local()


class RequestContextMiddleware(MiddlewareMixin):
    """
    Extracts or generates X-Request-ID and tracks user/tenant context in thread-local storage.
    """
    def process_request(self, request):
        req_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"
        request.request_id = req_id
        _thread_local.request_id = req_id

        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            _thread_local.user_id = str(user.id)
            _thread_local.org_id = str(user.organization_id or "none")
        else:
            _thread_local.user_id = "anonymous"
            _thread_local.org_id = getattr(request, "org_id", "none")

    def process_response(self, request, response):
        if hasattr(request, "request_id"):
            response["X-Request-ID"] = request.request_id
        return response
