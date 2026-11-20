import hmac
from datetime import date, timedelta

from django.conf import settings
from django.db.models import F, Sum
from django.http import JsonResponse
from django.utils import timezone
from django.views import View

from .models import Category, Product, Sale, SaleItem


class HealthView(View):
    def get(self, request):
        return JsonResponse({"status": "ok", "service": "inventory"})


class InternalAIEndpoint(View):
    def dispatch(self, request, *args, **kwargs):
        expected = settings.INVENTORY_SERVICE_TOKEN
        supplied = request.headers.get("X-Service-Token", "")
        if not expected or not hmac.compare_digest(supplied, expected):
            return JsonResponse({"error": "Invalid service credentials"}, status=401)
        return super().dispatch(request, *args, **kwargs)


class AIInventoryContextView(InternalAIEndpoint):
    def get(self, request):
        today = timezone.localdate()
        month_start = today.replace(day=1)
        lines = []

        low_stock = Product.objects.filter(
            current_stock__lte=F("min_stock"), is_active=True
        ).values("name", "current_stock", "min_stock", "last_reorder_qty")[:20]
        if low_stock:
            lines.append("LOW STOCK PRODUCTS")
            lines.extend(
                f"- {item['name']}: {item['current_stock']} units (minimum "
                f"{item['min_stock']}; reorder suggestion {item['last_reorder_qty']})"
                for item in low_stock
            )

        expiring = Product.objects.filter(
            expiry_date__gte=today,
            expiry_date__lte=today + timedelta(days=30),
            is_active=True,
        ).values("name", "expiry_date", "current_stock")[:10]
        if expiring:
            lines.append("EXPIRING WITHIN 30 DAYS")
            lines.extend(
                f"- {item['name']}: expires {item['expiry_date']}, "
                f"stock {item['current_stock']}"
                for item in expiring
            )

        month_sales = Sale.objects.filter(
            created_at__date__gte=month_start, status="completed"
        )
        revenue = month_sales.aggregate(total=Sum("total_amount"))["total"] or 0
        lines.extend([
            f"SALES THIS MONTH ({today.strftime('%B %Y')})",
            f"- Transactions: {month_sales.count()}",
            f"- Revenue: PKR {revenue:.2f}",
        ])

        top_selling = SaleItem.objects.filter(
            sale__created_at__date__gte=today - timedelta(days=30),
            sale__status="completed",
        ).values("product__name").annotate(
            quantity=Sum("quantity")
        ).order_by("-quantity")[:5]
        if top_selling:
            lines.append("TOP SELLING PRODUCTS (LAST 30 DAYS)")
            lines.extend(
                f"- {item['product__name']}: {item['quantity']} units"
                for item in top_selling
            )

        lines.extend([
            "INVENTORY SUMMARY",
            f"- Active products: {Product.objects.filter(is_active=True).count()}",
            f"- Out of stock: {Product.objects.filter(current_stock=0, is_active=True).count()}",
            f"- Categories: {Category.objects.count()}",
        ])
        return JsonResponse({"context": "\n".join(lines)})


class AIProductsView(InternalAIEndpoint):
    def get(self, request):
        products = Product.objects.filter(is_active=True).select_related("category")
        return JsonResponse([
            {
                "id": product.id,
                "searchable_text": " ".join(filter(None, [
                    product.name,
                    product.generic_name,
                    product.description,
                    product.tags,
                    product.category.name if product.category else "",
                ])),
            }
            for product in products
        ], safe=False)


class AISalesHistoryView(InternalAIEndpoint):
    def get(self, request, product_id):
        try:
            days = max(1, min(int(request.GET.get("days", 120)), 365))
        except ValueError:
            return JsonResponse({"error": "days must be an integer"}, status=400)
        today = timezone.localdate()
        start = today - timedelta(days=days - 1)
        sales = SaleItem.objects.filter(
            product_id=product_id,
            sale__created_at__date__gte=start,
            sale__created_at__date__lte=today,
            sale__status="completed",
        ).values("sale__created_at__date").annotate(
            quantity=Sum("quantity")
        )
        sales_by_date = {row["sale__created_at__date"]: row["quantity"] for row in sales}
        dates = [start + timedelta(days=offset) for offset in range(days)]
        return JsonResponse({
            "dates": [day.isoformat() for day in dates],
            "values": [sales_by_date.get(day, 0) for day in dates],
        })
