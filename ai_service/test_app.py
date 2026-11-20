import atexit
import os
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi import HTTPException

_test_storage = TemporaryDirectory(prefix="smartstock-ai-tests-")
os.environ.setdefault(
    "AI_DATABASE_PATH",
    os.path.join(_test_storage.name, "ai-tests.sqlite3"),
)
atexit.register(_test_storage.cleanup)
from ai_service import app as ai_service


class ForecastServiceTests(unittest.TestCase):
    @patch("ai_service.app.inventory_get", return_value={"values": [0] * 14})
    def test_forecast_does_not_invent_demand_without_sales(self, inventory_get):
        with self.assertRaises(HTTPException) as raised:
            ai_service.calculate_forecast(product_id=7, days=3)

        self.assertEqual(raised.exception.status_code, 422)
        inventory_get.assert_called_once_with(
            "/internal/ai/sales/7/", {"days": 120}
        )

    @patch("ai_service.app.inventory_get", return_value={"values": [3] * 14})
    def test_forecast_uses_recent_recorded_sales(self, inventory_get):
        result = ai_service.calculate_forecast(product_id=7, days=3)

        self.assertEqual(result["values"], [3, 3, 3])
        self.assertEqual(result["recommended_reorder"], 11)
        self.assertEqual(result["model"], "14-day moving average")
        self.assertEqual(len(result["dates"]), 3)
        inventory_get.assert_called_once()


class ProductSearchTests(unittest.TestCase):
    @patch("ai_service.app.sentence_model", return_value=None)
    @patch("ai_service.app.inventory_get", return_value=[
        {"id": 8, "searchable_text": "green tea herbal drink"},
        {"id": 9, "searchable_text": "rice grain"},
    ])
    def test_keyword_mode_searches_the_live_catalog(self, inventory_get, sentence_model):
        result = ai_service.search(q="herbal tea", limit=10)

        self.assertEqual(result["mode"], "keyword")
        self.assertEqual(result["results"], [{"id": 8, "score": None}])
        inventory_get.assert_called_once_with("/internal/ai/products/")


class ServiceAuthenticationTests(unittest.TestCase):
    @patch("ai_service.app.AI_TOKEN", "expected-token")
    def test_rejects_invalid_service_token(self):
        with self.assertRaises(HTTPException) as raised:
            ai_service.verify_service_token("wrong-token")

        self.assertEqual(raised.exception.status_code, 401)


class AIStatePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.storage = TemporaryDirectory(prefix="smartstock-ai-state-")
        self.database_path = os.path.join(self.storage.name, "ai.sqlite3")
        self.database_patch = patch.object(ai_service, "DATABASE_PATH", self.database_path)
        self.database_patch.start()
        ai_service.initialize_database()

    def tearDown(self):
        self.database_patch.stop()
        self.storage.cleanup()

    def test_forecast_cache_is_owned_by_ai_service(self):
        result = ai_service.save_forecast(18, {
            "dates": ["2026-11-21"],
            "values": [2.5],
            "recommended_reorder": 3,
            "model": "moving average",
            "mae": None,
        })

        cached = ai_service.cached_forecast(18)

        self.assertFalse(result["cached"])
        self.assertTrue(cached["cached"])
        self.assertEqual(cached["values"], [2.5])

    def test_chat_history_is_scoped_and_persisted_by_ai_service(self):
        completion = unittest.mock.Mock()
        completion.raise_for_status.return_value = None
        completion.json.return_value = {"message": {"content": "Live answer"}}
        with (
            patch.object(ai_service, "AI_TOKEN", "service-token"),
            patch.object(ai_service, "inventory_get", return_value={"context": "Live data"}),
            patch("ai_service.app.requests.post", return_value=completion),
        ):
            response = ai_service.chat(ai_service.ChatRequest(
                message="Current stock?",
                user_id=41,
                session_id="session-a",
            ))
            history = ai_service.chat_history("session-a", user_id=41)
            other_user_history = ai_service.chat_history(
                "session-a",
                user_id=42,
            )

        self.assertTrue(response["success"])
        self.assertEqual([item["role"] for item in history], ["user", "assistant"])
        self.assertEqual(len(other_user_history), 0)

    def test_legacy_imports_are_idempotent_and_keep_forecast_timestamp(self):
        chat_record = ai_service.LegacyChatRecord(
            id=90,
            user_id=41,
            session_id="legacy-session",
            role="user",
            message="Older message",
            created_at="2025-01-02T03:04:05+00:00",
        )
        chat_import = ai_service.LegacyChatImport(records=[chat_record])
        ai_service.import_legacy_chat(chat_import)
        ai_service.import_legacy_chat(chat_import)

        forecast_record = ai_service.LegacyForecastRecord(
            product_id=18,
            dates=["2025-01-03"],
            values=[2],
            recommended_reorder=3,
            model_used="legacy model",
            mae=0,
            generated_at="2025-01-02T03:04:05+00:00",
        )
        forecast_import = ai_service.LegacyForecastImport(records=[forecast_record])
        ai_service.import_legacy_forecasts(forecast_import)
        imported_forecast = ai_service.cached_forecast(18)
        ai_service.save_forecast(18, {
            "dates": ["2026-01-03"],
            "values": [5],
            "recommended_reorder": 6,
            "model": "moving average",
            "mae": None,
        }, generated_at="2026-01-02T03:04:05+00:00")
        ai_service.import_legacy_forecasts(forecast_import)

        history = ai_service.chat_history("legacy-session", user_id=41)
        forecast = ai_service.cached_forecast(18)

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["message"], "Older message")
        self.assertEqual(imported_forecast["generated_at"], "2025-01-02T03:04:05+00:00")
        self.assertEqual(forecast["generated_at"], "2026-01-02T03:04:05+00:00")
        self.assertEqual(forecast["values"], [5])
