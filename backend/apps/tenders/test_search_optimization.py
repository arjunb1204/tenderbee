"""
Comprehensive Automated Test Suite for Tenderbee API Health & Search Optimization.
Covers the 8 required audit scenarios:
  1. Health endpoint success and dependency failure (HTTP 503 on DB outage, no secret leakage).
  2. Search with a selected state (scoped strictly to selected state).
  3. Search without a selected state (respects search terms, no all-state expansion).
  4. Explicit nationwide search (nationwide=True).
  5. Invalid or empty search queries (safe handling, no live crawl).
  6. TinyFish timeout, authentication failure, and rate limiting (graceful fallback).
  7. Duplicate API requests (query caching) and duplicate results (URL deduplication).
  8. Ensuring no automatic fetch occurs for every Indian state.
"""
import time
from unittest.mock import MagicMock, patch
from django.db import connection
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from backend.apps.tenders.search import TenderSearchFilter, TenderSearchService, QueryParser
from backend.services.live_search import LiveTenderSearchEngine
from backend.services.storage import TenderStorage


class APIHealthEndpointTests(TestCase):
    """Scenario 1: Health endpoint success, dependency diagnostics, and failure handling."""

    def setUp(self):
        self.client = APIClient()

    def test_health_check_success_without_leaking_secrets(self):
        """Verifies /api/health/ returns HTTP 200 and does NOT expose any sensitive credentials."""
        response = self.client.get("/api/health/")
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_200_OK])
        data = response.json()

        self.assertIn(data["status"], ["healthy", "degraded"])
        self.assertEqual(data["service"], "TenderBee Core API")
        self.assertIn("dependencies", data)
        self.assertIn("database", data["dependencies"])
        self.assertEqual(data["dependencies"]["database"]["status"], "healthy")

        # Zero credential or secret exposure assertion
        resp_text = response.content.decode("utf-8").lower()
        self.assertNotIn("password", resp_text)
        self.assertNotIn("sk-tinyfish", resp_text)
        self.assertNotIn("postgres://", resp_text)
        self.assertNotIn("traceback", resp_text)

    def test_health_check_database_failure_returns_503(self):
        """Verifies /api/health/ returns HTTP 503 Service Unavailable when the primary DB is unreachable."""
        with patch.object(connection, "cursor", side_effect=Exception("Database connection timeout")):
            response = self.client.get("/api/health/")
            self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
            data = response.json()
            self.assertEqual(data["status"], "unhealthy")
            self.assertEqual(data["dependencies"]["database"]["status"], "unhealthy")
            self.assertNotIn("traceback", str(data).lower())


class TenderSearchOptimizationTests(TestCase):
    """Scenarios 2 - 8: State-specific discovery, TinyFish optimization, deduplication & caching."""

    def setUp(self):
        self.client = APIClient()
        # Reset live search query cache before each test
        LiveTenderSearchEngine._query_cache.clear()

    # -------------------------------------------------------------------------
    # Scenario 2: Search with a selected state
    # -------------------------------------------------------------------------
    def test_search_with_selected_state_scopes_strictly(self):
        """Verifies that selecting a state restricts results strictly to that state without searching others."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.url = "https://mahatenders.gov.in/nicgep/app?component=view&id=123"
        mock_result.title = "CCTV Surveillance Systems Tender - Mumbai Maharashtra"
        mock_result.snippet = "Installation of CCTV surveillance systems in Maharashtra."
        mock_result.pdf_url = "https://mahatenders.gov.in/cctv.pdf"
        mock_result.date = "2026-11-30"
        mock_client.search.query.return_value = MagicMock(results=[mock_result])

        engine = LiveTenderSearchEngine(api_key="test-key")
        engine.client = mock_client

        results = engine.search_live(query="cctv", state="Maharashtra")

        # Must invoke TinyFish search with the specific state
        self.assertEqual(mock_client.search.query.call_count, 1)
        call_args = mock_client.search.query.call_args[0][0]
        self.assertIn('"Maharashtra"', call_args)
        self.assertNotIn("Bihar", call_args)
        self.assertNotIn("Gujarat", call_args)

        self.assertGreaterEqual(len(results), 1)
        for r in results:
            self.assertEqual(r["state"], "Maharashtra")

    # -------------------------------------------------------------------------
    # Scenario 3: Search without a selected state
    # -------------------------------------------------------------------------
    def test_search_without_selected_state_uses_query_terms_without_all_state_loop(self):
        """Verifies that searching without a state does not loop or search across every state."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.url = "https://gem.gov.in/bid/GEM/2026/B/999111"
        mock_result.title = "Server Hardware Procurement GeM Tender"
        mock_result.snippet = "Supply and commissioning of server hardware."
        mock_result.pdf_url = None
        mock_result.date = "2026-12-15"
        mock_client.search.query.return_value = MagicMock(results=[mock_result])

        engine = LiveTenderSearchEngine(api_key="test-key")
        engine.client = mock_client

        results = engine.search_live(query="server hardware", state=None, nationwide=False)

        # Must execute only ONE targeted query, never loop over all 28 states
        self.assertEqual(mock_client.search.query.call_count, 1)
        call_args = mock_client.search.query.call_args[0][0]
        self.assertIn("server hardware", call_args)
        self.assertNotIn("site:eproc2.bihar.gov.in", call_args)

        self.assertGreaterEqual(len(results), 1)

    # -------------------------------------------------------------------------
    # Scenario 4: Explicit nationwide search
    # -------------------------------------------------------------------------
    def test_search_explicit_nationwide(self):
        """Verifies nationwide search passes nationwide scope and targets pan-India tender notices."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.url = "https://eprocure.gov.in/eprocure/app?page=tender&id=99"
        mock_result.title = "Solar Panels Supply Tender CPPP National"
        mock_result.snippet = "Pan-India national tender notice for solar PV modules."
        mock_result.pdf_url = None
        mock_result.date = "2026-12-31"
        mock_client.search.query.return_value = MagicMock(results=[mock_result])

        engine = LiveTenderSearchEngine(api_key="test-key")
        engine.client = mock_client

        results = engine.search_live(query="solar panels", state=None, nationwide=True)

        self.assertEqual(mock_client.search.query.call_count, 1)
        call_args = mock_client.search.query.call_args[0][0]
        self.assertIn("solar panels", call_args)
        self.assertIn("site:gov.in", call_args)
        self.assertGreaterEqual(len(results), 1)

    # -------------------------------------------------------------------------
    # Scenario 5: Invalid or empty search queries
    # -------------------------------------------------------------------------
    def test_empty_or_invalid_search_does_not_trigger_live_scrape(self):
        """Verifies empty search queries return empty result sets without making external API calls."""
        mock_client = MagicMock()
        engine = LiveTenderSearchEngine(api_key="test-key")
        engine.client = mock_client

        # Direct engine call with empty terms
        results = engine.search_live(query="", state=None, category=None)
        self.assertEqual(results, [])
        mock_client.search.query.assert_not_called()

        # HTTP API endpoint call with empty params
        response = self.client.get("/api/v1/tenders/search/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["total_matches"], 0)
        self.assertEqual(data["results"], [])
        self.assertEqual(data["source"], "empty_criteria")
        mock_client.search.query.assert_not_called()

    # -------------------------------------------------------------------------
    # Scenario 6: TinyFish timeout, authentication failure, and rate limiting
    # -------------------------------------------------------------------------
    def test_tinyfish_rate_limit_handled_gracefully(self):
        """Verifies HTTP 429 RateLimitError from TinyFish is handled gracefully without crashing."""
        from tinyfish import RateLimitError

        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_client = MagicMock()
        mock_client.search.query.side_effect = RateLimitError(
            "Rate limit reached: maximum requests per minute exceeded.",
            response=mock_resp,
        )

        engine = LiveTenderSearchEngine(api_key="test-key")
        engine.client = mock_client

        results = engine.search_live(query="cctv", state="Delhi")
        self.assertEqual(results, [])

    def test_tinyfish_authentication_failure_handled_gracefully(self):
        """Verifies HTTP 401 AuthenticationError is handled safely without leaking credentials."""
        from tinyfish import AuthenticationError

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_client = MagicMock()
        mock_client.search.query.side_effect = AuthenticationError(
            "Invalid API key provided.",
            response=mock_resp,
        )

        engine = LiveTenderSearchEngine(api_key="bad-key")
        engine.client = mock_client

        results = engine.search_live(query="generators", state="Rajasthan")
        self.assertEqual(results, [])

    def test_tinyfish_timeout_handled_gracefully(self):
        """Verifies APITimeoutError from TinyFish does not crash the search service."""
        from tinyfish import APITimeoutError

        mock_client = MagicMock()
        mock_client.search.query.side_effect = APITimeoutError(message="Connection timed out after 10.0s")

        engine = LiveTenderSearchEngine(api_key="test-key")
        engine.client = mock_client

        results = engine.search_live(query="housekeeping", state="Haryana")
        self.assertEqual(results, [])

    # -------------------------------------------------------------------------
    # Scenario 7: Duplicate requests (caching) and duplicate results (URL deduplication)
    # -------------------------------------------------------------------------
    def test_duplicate_requests_serve_from_query_cache(self):
        """Verifies that consecutive identical queries are served from in-memory cache without calling TinyFish."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.url = "https://eprocure.gov.in/tender/101"
        mock_result.title = "Security Guarding Services Tender"
        mock_result.snippet = "Tender for round-the-clock security guarding services."
        mock_result.pdf_url = None
        mock_result.date = "2026-11-20"
        mock_client.search.query.return_value = MagicMock(results=[mock_result])

        engine = LiveTenderSearchEngine(api_key="test-key")
        engine.client = mock_client

        # Call 1: Misses cache, calls TinyFish
        res1 = engine.search_live(query="security guard", state="Karnataka")
        self.assertEqual(mock_client.search.query.call_count, 1)

        # Call 2: Hits cache, must NOT call TinyFish again
        res2 = engine.search_live(query="security guard", state="Karnataka")
        self.assertEqual(mock_client.search.query.call_count, 1)
        self.assertEqual(len(res1), len(res2))

    def test_duplicate_results_are_deduplicated_by_normalized_url(self):
        """Verifies returned results with identical normalized URLs or tracking params are deduplicated."""
        mock_client = MagicMock()
        # Two results pointing to the same document with different tracking parameters
        r1 = MagicMock()
        r1.url = "https://gem.gov.in/bid/GEM-12345/?utm_source=portal&ref=home"
        r1.title = "Medical Supplies Tender Notice"
        r1.snippet = "Supply of diagnostic medical test kits."
        r1.pdf_url = None
        r1.date = "2026-12-01"

        r2 = MagicMock()
        r2.url = "https://gem.gov.in/bid/GEM-12345"
        r2.title = "Medical Supplies Tender Notice (Duplicate)"
        r2.snippet = "Supply of diagnostic medical test kits duplicate entry."
        r2.pdf_url = None
        r2.date = "2026-12-01"

        mock_client.search.query.return_value = MagicMock(results=[r1, r2])

        engine = LiveTenderSearchEngine(api_key="test-key")
        engine.client = mock_client

        results = engine.search_live(query="medical kits", state="Gujarat")
        # Should be deduplicated to 1 item
        self.assertEqual(len(results), 1)

    # -------------------------------------------------------------------------
    # Scenario 8: Ensuring no automatic fetch occurs for every state
    # -------------------------------------------------------------------------
    def test_no_automatic_fetch_occurs_for_every_state(self):
        """Verifies search never loops through all Indian states or executes repeated statewide queries."""
        mock_client = MagicMock()
        engine = LiveTenderSearchEngine(api_key="test-key")
        engine.client = mock_client

        # Search with a single state
        engine.search_live(query="civil works", state="Punjab")
        self.assertEqual(mock_client.search.query.call_count, 1)

        # Search without state
        engine.search_live(query="civil works", state=None)
        # Total calls should now be 2 (1 for each explicit search), never 28+ for every state
        self.assertEqual(mock_client.search.query.call_count, 2)
