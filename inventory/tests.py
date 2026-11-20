from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse

from inventory.models import Category, Product


class InternalAIAPITests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Drinks")
        Product.objects.create(
            name="Green tea",
            generic_name="Tea leaf",
            tags="herbal drink",
            barcode="TEA-001",
            category=self.category,
            purchase_price="1.00",
            selling_price="2.00",
            current_stock=4,
        )

    @override_settings(INVENTORY_SERVICE_TOKEN="inventory-test-token")
    def test_internal_product_data_requires_service_token(self):
        denied = self.client.get("/internal/ai/products/")
        allowed = self.client.get(
            "/internal/ai/products/",
            HTTP_X_SERVICE_TOKEN="inventory-test-token",
        )

        self.assertEqual(denied.status_code, 401)
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.json()[0]["id"], Product.objects.get().id)
        self.assertIn("Green tea", allowed.json()[0]["searchable_text"])

    def test_inventory_health_endpoint_is_available(self):
        response = self.client.get("/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "service": "inventory"})


class DashboardViewTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="manager",
            password="test-password",
            role="Manager",
        )
        self.client.force_login(user)

    def test_empty_dashboard_renders_real_data_empty_states(self):
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["has_sales_30d"])
        self.assertEqual(len(response.context["chart_labels"]), 30)
        self.assertContains(response, "No completed sales in the last 30 days.")
        self.assertContains(response, "Add products to see category totals.")
