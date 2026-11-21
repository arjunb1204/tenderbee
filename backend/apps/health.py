"""
Health check and dependency diagnostics view for TenderBee.
Safely inspects database, storage, and TinyFish API configuration without leaking credentials.
"""
import logging
import os
from typing import Any, Dict

from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from rest_framework import status

logger = logging.getLogger(__name__)


def health_check(request):
    """
    Lightweight, deterministic API health check endpoint.
    GET /api/health/

    Status Codes:
      - 200 OK: System healthy or operational (even if non-essential dependencies are degraded).
      - 503 Service Unavailable: Essential dependency (e.g. primary database) is down.

    Safety:
      - Never exposes API keys, tokens, connection strings, or internal stack traces.
      - Logs internal failure exceptions safely on the server.
    """
    dependencies: Dict[str, Any] = {}
    is_healthy = True
    is_degraded = False

    # 1. Primary Database Connectivity Check (Essential)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            row = cursor.fetchone()
            if row and row[0] == 1:
                dependencies["database"] = {
                    "status": "healthy",
                    "engine": connection.vendor,
                }
            else:
                dependencies["database"] = {
                    "status": "unhealthy",
                    "error": "Unexpected query response",
                }
                is_healthy = False
    except Exception as exc:
        logger.error("Health check failed on primary database connection: %s", exc, exc_info=True)
        dependencies["database"] = {
            "status": "unhealthy",
            "error": "Database connection unavailable",
        }
        is_healthy = False

    # 2. Storage Subsystem Check (Essential for tender documents)
    try:
        storage_backend = getattr(settings, "STORAGE_BACKEND", "local")
        if storage_backend == "b2":
            b2_endpoint = getattr(settings, "B2_ENDPOINT_URL", "")
            b2_bucket = getattr(settings, "B2_BUCKET_NAME", "")
            has_b2_keys = bool(
                getattr(settings, "B2_APPLICATION_KEY_ID", None)
                and getattr(settings, "B2_APPLICATION_KEY", None)
            )
            if has_b2_keys and b2_bucket:
                dependencies["storage"] = {
                    "status": "healthy",
                    "backend": "Backblaze B2",
                    "bucket": b2_bucket,
                }
            else:
                dependencies["storage"] = {
                    "status": "degraded",
                    "backend": "Backblaze B2 (incomplete credentials)",
                }
                is_degraded = True
        else:
            dependencies["storage"] = {
                "status": "healthy",
                "backend": "local_filesystem",
            }
    except Exception as exc:
        logger.error("Health check failed on storage check: %s", exc, exc_info=True)
        dependencies["storage"] = {
            "status": "degraded",
            "error": "Storage inspection failed",
        }
        is_degraded = True

    # 3. TinyFish Search & Scraper API Check (Optional external integration)
    try:
        tinyfish_key = os.getenv("TINYFISH_API_KEY")
        if tinyfish_key and len(tinyfish_key.strip()) > 5:
            dependencies["tinyfish_search"] = {
                "status": "configured",
                "mode": "live_discovery_enabled",
            }
        else:
            dependencies["tinyfish_search"] = {
                "status": "unconfigured",
                "mode": "live_discovery_disabled",
                "note": "TINYFISH_API_KEY not set. Operating in local-index-only mode.",
            }
            is_degraded = True
    except Exception as exc:
        logger.warning("Health check failed inspecting TinyFish configuration: %s", exc)
        dependencies["tinyfish_search"] = {
            "status": "error",
            "error": "Failed to inspect integration",
        }
        is_degraded = True

    # Overall System Status
    if not is_healthy:
        overall_status = "unhealthy"
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    elif is_degraded:
        overall_status = "degraded"
        http_status = status.HTTP_200_OK
    else:
        overall_status = "healthy"
        http_status = status.HTTP_200_OK

    response_payload = {
        "status": overall_status,
        "service": "TenderBee Core API",
        "version": "1.0.0",
        "dependencies": dependencies,
    }

    return JsonResponse(response_payload, status=http_status)
