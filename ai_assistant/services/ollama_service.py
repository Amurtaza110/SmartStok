"""
ai_assistant/services/ollama_service.py
=========================================
Clean Ollama integration with graceful fallback.
Supports context-aware inventory queries using RAG pattern.

Installation for local LLM:
  Linux/Mac: curl -fsSL https://ollama.com/install.sh | sh
  Windows:   Download from https://ollama.com/download
  Model:     ollama pull llama3.2
  Run:       ollama serve
"""

import logging
from datetime import date, timedelta
import requests

from django.conf import settings
from django.db.models import F, Sum
from django.utils import timezone

from inventory.models import Category, Product, Sale, SaleItem

logger = logging.getLogger(__name__)

OLLAMA_URL = getattr(settings, 'OLLAMA_BASE_URL', 'http://localhost:11434').rstrip('/')
OLLAMA_MODEL = getattr(settings, 'OLLAMA_MODEL', 'llama3.2')
OLLAMA_TIMEOUT = int(getattr(settings, 'OLLAMA_TIMEOUT', 60))


def is_ollama_running():
    """Ping Ollama API to check if it's available."""
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


def get_available_models():
    """List models installed in Ollama."""
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=2)
        if response.status_code == 200:
            return [m['name'] for m in response.json().get('models', [])]
    except Exception:
        pass
    return []


def build_inventory_context():
    """
    Fetch live inventory data and format it as a context string
    to inject into the LLM prompt (RAG approach).
    """
    today = timezone.localdate()
    month_start = today.replace(day=1)
    lines = []

    # 1. Low stock products
    low_stock = Product.objects.filter(
        current_stock__lte=F('min_stock'),
        is_active=True
    ).values('name', 'current_stock', 'min_stock', 'last_reorder_qty')[:15]

    if low_stock:
        lines.append("=== LOW STOCK PRODUCTS ===")
        for item in low_stock:
            lines.append(
                f"- {item['name']}: {item['current_stock']} units left "
                f"(min: {item['min_stock']}, AI suggested reorder: {item['last_reorder_qty']})"
            )

    # 2. Expiring products within 30 days
    expiring = Product.objects.filter(
        expiry_date__gte=today,
        expiry_date__lte=today + timedelta(days=30),
        is_active=True
    ).values('name', 'expiry_date', 'current_stock')[:10]

    if expiring:
        lines.append("\n=== EXPIRING WITHIN 30 DAYS ===")
        for item in expiring:
            lines.append(f"- {item['name']}: expires {item['expiry_date']} (stock: {item['current_stock']})")

    # 3. Sales this month
    month_sales = Sale.objects.filter(
        created_at__date__gte=month_start,
        status='completed'
    )
    month_rev = month_sales.aggregate(total=Sum('total_amount'))['total'] or 0
    lines.append(f"\n=== SALES THIS MONTH ({today.strftime('%B %Y')}) ===")
    lines.append(f"  Transactions: {month_sales.count()}")
    lines.append(f"  Revenue: PKR {month_rev:,.2f}")

    # 4. Top selling products
    top_selling = SaleItem.objects.filter(
        sale__created_at__date__gte=today - timedelta(days=30),
        sale__status='completed'
    ).values('product__name').annotate(
        total_sold=Sum('quantity')
    ).order_by('-total_sold')[:5]

    if top_selling:
        lines.append("\n=== TOP SELLING (LAST 30 DAYS) ===")
        for item in top_selling:
            lines.append(f"- {item['product__name']}: {item['total_sold']} units sold")

    # 5. Inventory summary
    total_products = Product.objects.filter(is_active=True).count()
    out_of_stock = Product.objects.filter(is_active=True, current_stock=0).count()
    categories_count = Category.objects.count()

    lines.append("\n=== INVENTORY SUMMARY ===")
    lines.append(f"  Total active products: {total_products}")
    lines.append(f"  Out of stock: {out_of_stock}")
    lines.append(f"  Categories: {categories_count}")

    return "\n".join(lines)


def _generate_fallback_response(user_message, context):
    """
    Provide an intelligent, rule-based response when Ollama is offline.
    Uses real-time data from the live inventory context.
    """
    msg = user_message.lower()

    if any(k in msg for k in ['low stock', 'out of stock', 'shortage', 'reorder']):
        low_stock = Product.objects.filter(current_stock__lte=F('min_stock'), is_active=True)
        if low_stock.exists():
            items = [f"• **{p.name}**: {p.current_stock} in stock (min: {p.min_stock}, suggested reorder: {p.last_reorder_qty})" for p in low_stock[:10]]
            return "### ⚠️ Low Stock Alert\n\n" + "\n".join(items) + "\n\n*(Data retrieved live from database)*"
        return "✅ All active products currently meet or exceed their minimum stock thresholds."

    if any(k in msg for k in ['expire', 'expiring', 'expiry', 'date']):
        today = timezone.localdate()
        expiring = Product.objects.filter(expiry_date__gte=today, expiry_date__lte=today + timedelta(days=30), is_active=True)
        if expiring.exists():
            items = [f"• **{p.name}**: expires {p.expiry_date} ({p.current_stock} units in stock)" for p in expiring[:10]]
            return "### ⏳ Products Expiring Within 30 Days\n\n" + "\n".join(items)
        return "✅ No products are expiring within the next 30 days."

    if any(k in msg for k in ['sale', 'revenue', 'income', 'earn', 'performance', 'turnover']):
        today = timezone.localdate()
        month_start = today.replace(day=1)
        month_sales = Sale.objects.filter(created_at__date__gte=month_start, status='completed')
        total_rev = month_sales.aggregate(total=Sum('total_amount'))['total'] or 0
        return f"### 📊 Current Month Sales Summary ({today.strftime('%B %Y')})\n\n• **Completed Transactions:** {month_sales.count()}\n• **Total Revenue:** PKR {total_rev:,.2f}\n\nCheck the **Reports** section for full analytics."

    if any(k in msg for k in ['product', 'stock', 'catalog', 'item', 'summary', 'overview', 'stats']):
        total = Product.objects.filter(is_active=True).count()
        out_of_stock = Product.objects.filter(is_active=True, current_stock=0).count()
        categories = Category.objects.count()
        return f"### 📦 SmartStock Inventory Overview\n\n• **Active Products:** {total}\n• **Categories:** {categories}\n• **Out of Stock:** {out_of_stock}\n\nAsk about 'low stock', 'sales', or search for any item via the top search bar."

    # General greeting or other query
    return (
        f"Hello! I am your **SmartStock AI Assistant**.\n\n"
        f"Here is a quick snapshot of the inventory:\n\n"
        f"```\n{context}\n```\n\n"
        f"💡 *Tip: For full conversational AI, start Ollama locally (`ollama serve`).*"
    )


def chat_with_ollama(user_message, conversation_history=None):
    """
    Send a message to Ollama and return the response.
    Falls back gracefully to direct context response if Ollama is offline.

    Args:
        user_message: The user's question/message
        conversation_history: List of {'role': ..., 'message': ...} dicts

    Returns:
        dict with keys: 'success', 'response', 'error', 'model'
    """
    context = build_inventory_context()
    today_str = timezone.localdate().strftime("%A, %d %B %Y")

    if not is_ollama_running():
        fallback = _generate_fallback_response(user_message, context)
        return {
            'success': True,
            'response': fallback,
            'model': 'SmartStock Assistant (Live Database Context)',
            'error': None,
        }

    system_prompt = (
        "You are SmartStock AI, an expert inventory management assistant. "
        "Use only the live business data provided below. "
        "Be concise, accurate, helpful, and provide actionable recommendations. "
        "Currency: PKR.\n\n"
        f"LIVE INVENTORY DATA:\n{context}\n\n"
        f"Today's date: {today_str}"
    )

    messages = [{"role": "system", "content": system_prompt}]

    if conversation_history:
        for item in conversation_history[-10:]:
            role = item.get('role', 'user')
            content = item.get('message') or item.get('content', '')
            if role in ('user', 'assistant') and content:
                messages.append({'role': role, 'content': content})

    messages.append({'role': 'user', 'content': user_message})

    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 512,
                },
            },
            timeout=OLLAMA_TIMEOUT,
        )
        response.raise_for_status()
        content = response.json().get('message', {}).get('content')
        if content:
            return {
                'success': True,
                'response': content,
                'model': OLLAMA_MODEL,
                'error': None,
            }
        return {
            'success': False,
            'response': None,
            'model': OLLAMA_MODEL,
            'error': 'Ollama returned an empty response.',
        }
    except requests.Timeout:
        return {
            'success': True,
            'response': _generate_fallback_response(user_message, context),
            'model': 'SmartStock Assistant (Timeout Fallback)',
            'error': None,
        }
    except Exception as exc:
        logger.warning(f"Ollama request error: {exc}")
        return {
            'success': True,
            'response': _generate_fallback_response(user_message, context),
            'model': 'SmartStock Assistant (Direct Mode)',
            'error': None,
        }
