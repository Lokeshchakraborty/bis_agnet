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
            any(w in core_resp for w in ["10,000", "10000", "10 000", "25,000", "25000", "litre", "liter"]),
            f"Expected capacity limit (10,000 or 25,000 Litres) in core_response, got: {core_resp}"
        )
        self.assertTrue(
            "60" in core_resp or "mg/l" in core_resp,
            f"Expected chemical migration limit (60 mg/l) in core_response, got: {core_resp}"
        )

    def test_08_keep_alive_endpoints(self):
        # 1. Health check includes keep_alive_enabled
        health_resp = self.client.get("/health")
        self.assertEqual(health_resp.status_code, 200)
        self.assertIn("keep_alive_enabled", health_resp.json())

        # 2. Lightweight ping endpoint
        ping_resp = self.client.get("/health/ping")
        self.assertEqual(ping_resp.status_code, 200)
        ping_data = ping_resp.json()
        self.assertEqual(ping_data["status"], "alive")
        self.assertIn("target_url", ping_data)

        # 3. Keep-alive status telemetry endpoint
        status_resp = self.client.get("/api/v1/keep-alive")
        self.assertEqual(status_resp.status_code, 200)
        status_data = status_resp.json()
        self.assertEqual(status_data["status"], "active")
        self.assertEqual(status_data["interval_seconds"], 600)
        self.assertEqual(status_data["interval_minutes"], 10.0)
        self.assertIn("10 minutes", status_data["message"])
        self.assertIn("target_url", status_data)

        # 4. Trigger endpoint propagates ping_result status
        trigger_resp = self.client.post("/api/v1/keep-alive/trigger")
        self.assertEqual(trigger_resp.status_code, 200)
        trigger_data = trigger_resp.json()
        self.assertEqual(trigger_data["status"], trigger_data["ping_result"]["status"])
        self.assertIn("telemetry", trigger_data)

    def test_09_keep_alive_manager_interval_validation(self):
        import os
        from unittest.mock import patch
        from app import KeepAliveManager

        with patch.dict(os.environ):
            # 1. Zero value defaults to 600
            os.environ["KEEP_ALIVE_INTERVAL_SECONDS"] = "0"
            mgr_zero = KeepAliveManager()
            self.assertEqual(mgr_zero.interval_seconds, 600)

            # 2. Negative value defaults to 600
            os.environ["KEEP_ALIVE_INTERVAL_SECONDS"] = "-60"
            mgr_neg = KeepAliveManager()
            self.assertEqual(mgr_neg.interval_seconds, 600)

            # 3. Non-integer defaults to 600
            os.environ["KEEP_ALIVE_INTERVAL_SECONDS"] = "invalid"
            mgr_inv = KeepAliveManager()
            self.assertEqual(mgr_inv.interval_seconds, 600)

            # 4. Valid positive integer succeeds
            os.environ["KEEP_ALIVE_INTERVAL_SECONDS"] = "300"
            mgr = KeepAliveManager()
            self.assertEqual(mgr.interval_seconds, 300)


if __name__ == "__main__":
    unittest.main()


