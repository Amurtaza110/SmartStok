import json
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from inventory.models import Category, Product, Sale, SaleItem, ChatHistory, ForecastResult
from ai_assistant.services.forecasting import forecast_product_demand, run_forecast_and_save, run_all_forecasts
from ai_assistant.services.semantic_search import semantic_search, keyword_fallback
from ai_assistant.services.ollama_service import is_ollama_running, build_inventory_context, chat_with_ollama

User = get_user_model()


class AIAssistantTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="admin",
            password="adminpassword123",
            role="Admin",
        )
        self.category = Category.objects.create(name="Medicines")
        self.product = Product.objects.create(
            name="Panadol Extra",
            generic_name="Paracetamol",
            tags="fever, headache, pain",
            barcode="PAN-001",
            category=self.category,
            purchase_price="50.00",
            selling_price="70.00",
            current_stock=100,
            min_stock=20,
            reorder_point=40,
        )

    def test_forecast_calculation(self):
        res = forecast_product_demand(self.product.id)
        self.assertTrue(res['success'])
        self.assertEqual(len(res['dates']), 30)
        self.assertGreater(res['recommended_reorder'], 0)

        save_res = run_forecast_and_save(self.product.id)
        self.assertTrue(save_res['success'])
        self.assertTrue(ForecastResult.objects.filter(product=self.product).exists())

    def test_keyword_fallback_search(self):
        results = keyword_fallback("fever", top_k=5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Panadol Extra")

        results_sem = semantic_search("fever", top_k=5)
        self.assertEqual(len(results_sem), 1)
        self.assertEqual(results_sem[0].name, "Panadol Extra")

    def test_chatbot_views(self):
        self.client.force_login(self.user)

        # Chatbot page
        resp = self.client.get(reverse('ai:chatbot'))
        self.assertEqual(resp.status_code, 200)

        session_id = self.client.session.get('chat_session_id')
        self.assertIsNotNone(session_id)

        # Chat API
        post_resp = self.client.post(
            reverse('ai:chat-api'),
            data=json.dumps({'message': 'Show me low stock items', 'session_id': session_id}),
            content_type='application/json',
        )
        self.assertEqual(post_resp.status_code, 200)
        data = post_resp.json()
        self.assertTrue(data['success'])
        self.assertIn('response', data)

        # Verify chat history saved
        self.assertTrue(ChatHistory.objects.filter(user=self.user, session_id=session_id).exists())

        # Clear chat
        clear_resp = self.client.post(reverse('ai:chat-clear'))
        self.assertEqual(clear_resp.status_code, 200)
        self.assertFalse(ChatHistory.objects.filter(session_id=session_id).exists())

    def test_ai_status_view(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('ai:status'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ai_service']['running'])
        self.assertTrue(data['forecasting']['available'])
        self.assertTrue(data['semantic_search']['available'])
