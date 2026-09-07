"""
Automated REST API integration tests for BIS Agentic RAG Assistant.
"""
from __future__ import annotations

import unittest
from fastapi.testclient import TestClient

from app import app, session_manager


class TestBISAgentAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        session_manager.clear_all()

    def test_01_health_check(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("llm_model", data)
        self.assertIn("embedding_provider", data)

    def test_02_root_endpoint(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")

    def test_03_query_endpoint(self):
        payload = {
            "query": "What is gold hallmarking?",
            "session_id": "test-session-1"
        }
        response = self.client.post("/api/v1/query", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["session_id"], "test-session-1")
        self.assertEqual(data["query"], payload["query"])
        self.assertIn("intent", data)
        self.assertIn("intent_localized", data)
        self.assertIn("compliance_metadata", data)
        self.assertIn("confidence_metrics", data)
        self.assertIn("audit_metadata", data)
        self.assertIn("intent_confidence", data["confidence_metrics"])
        self.assertIn("interaction_id", data["audit_metadata"])
        self.assertIn("llm_provider", data)
        self.assertIn("llm_model", data)
        self.assertIn("response_time_ms", data)
        self.assertIn("response_time_seconds", data)
        self.assertIn("core_response", data)
        self.assertIn("token_usage", data)
        self.assertIn("llm_provider", data["token_usage"])
        self.assertIn("llm_model", data["token_usage"])
        self.assertIn("response_time_ms", data["token_usage"])

    def test_04_session_management(self):
        # 1. Create turn to populate session
        sess = session_manager.get_session("sess-abc")
        sess.history.append(("Hello", "Hi there!"))

        # 2. List sessions
        response = self.client.get("/api/v1/sessions")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(data["total_active"], 1)

        # 3. Delete session
        del_resp = self.client.delete("/api/v1/sessions/sess-abc")
        self.assertEqual(del_resp.status_code, 200)
        self.assertEqual(del_resp.json()["status"], "success")

        # 4. Delete non-existent session
        del_err = self.client.delete("/api/v1/sessions/sess-abc")
        self.assertEqual(del_err.status_code, 404)

    def test_05_cache_clear(self):
        response = self.client.post("/api/v1/cache/clear")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")

    def test_06_rate_limiting_and_error_payload(self):
        # Verify SessionRateLimitException returns standardized APIErrorPayload JSON with HTTP 429
        session = session_manager.get_session("limited-sess")
        session.turn_count = 55  # Force turn cap exceeded

        payload = {"query": "Test rate limit", "session_id": "limited-sess"}
        response = self.client.post("/api/v1/query", json=payload)
        self.assertEqual(response.status_code, 429)
        data = response.json()
        self.assertEqual(data["status"], "error")
        self.assertEqual(data["error_code"], "SESSION_TURN_CAP_EXCEEDED")
        self.assertIn("message", data)
        self.assertIn("suggested_action", data)
        self.assertEqual(data["session_id"], "limited-sess")

    def test_07_quantitative_parameter_extraction(self):
        # Verify quantitative parameters (capacities, limits) are extracted directly into core_response
        payload = {
            "query": "What is the maximum capacity limit and overall chemical migration limit for IS 12701 polyethylene water storage tanks?",
            "session_id": "quant-sess-1"
        }
        response = self.client.post("/api/v1/query", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        core_resp = data.get("core_response", "").lower()
        self.assertTrue(
            "10,000" in core_resp or "10000" in core_resp or "10 000" in core_resp or "litre" in core_resp,
            f"Expected capacity limit (10,000 Litres) in core_response, got: {core_resp}"
        )
        self.assertTrue(
            "60" in core_resp or "mg/l" in core_resp,
            f"Expected chemical migration limit (60 mg/l) in core_response, got: {core_resp}"
        )


if __name__ == "__main__":
    unittest.main()
