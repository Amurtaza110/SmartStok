"""
ai_assistant/views.py
======================
Views for:
1. AI Chatbot (Ollama-powered)
2. Demand Forecasting
3. Semantic Search
"""

import json
import uuid
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils.dateparse import parse_datetime
from django.views import View
from django.views.generic import TemplateView

from inventory.models import Product
from .services.ai_service_client import AIServiceError, request_ai_service


# ─────────────────────────────────────────────
# 1. AI CHATBOT
# ─────────────────────────────────────────────

class ChatbotView(LoginRequiredMixin, TemplateView):
    """
    Main chatbot interface.
    Renders the chat UI. All messages are sent via AJAX to ChatAPIView.
    """
    template_name = 'ai_assistant/chatbot.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # Get or create session ID for this browser session
        if 'chat_session_id' not in self.request.session:
            self.request.session['chat_session_id'] = str(uuid.uuid4())
        session_id = self.request.session['chat_session_id']

        ctx['session_id'] = session_id
        try:
            health = request_ai_service('GET', '/health', timeout=3)
            ctx['ai_service_running'] = True
            history = request_ai_service(
                'GET',
                f'/v1/chat/history/{session_id}',
                params={'user_id': self.request.user.pk},
                timeout=5,
            )
            for record in history:
                record['created_at'] = parse_datetime(record['created_at'])
            ctx['chat_history'] = history
        except AIServiceError:
            health = {}
            ctx['ai_service_running'] = False
            ctx['chat_history'] = []
        ctx['ollama_running'] = health.get('ollama_running', False)
        ctx['available_models'] = health.get('models', [])

        return ctx


class ChatAPIView(LoginRequiredMixin, View):
    """
    AJAX endpoint: POST a message, get AI response.
    Saves conversation to ChatHistory for context.
    """

    def post(self, request):
        try:
            data = json.loads(request.body)
            if not isinstance(data, dict):
                return JsonResponse({'success': False, 'error': 'Invalid message payload'}, status=400)
            message = data.get('message', '')
            if not isinstance(message, str):
                return JsonResponse({'success': False, 'error': 'Message must be text'}, status=400)
            user_message = message.strip()
            session_id = data.get('session_id', '')

            if not user_message:
                return JsonResponse({'success': False, 'error': 'Empty message'}, status=400)
            if not isinstance(session_id, str) or not session_id:
                return JsonResponse({'success': False, 'error': 'Invalid chat session'}, status=400)
            if session_id != request.session.get('chat_session_id'):
                return JsonResponse({'success': False, 'error': 'Invalid chat session'}, status=403)

            result = request_ai_service(
                'POST',
                '/v1/chat',
                payload={
                    'message': user_message,
                    'user_id': request.user.pk,
                    'session_id': session_id,
                },
            )

            return JsonResponse({
                'success': True,
                'response': result['response'],
                'error': None,
                'model': result['model'],
            })

        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'})
        except AIServiceError as e:
            return JsonResponse(
                {'success': False, 'error': e.message},
                status=e.status_code if 400 <= e.status_code < 600 else 503,
            )


class ClearChatView(LoginRequiredMixin, View):
    """Clear chat history for current session."""

    def post(self, request):
        session_id = request.session.get('chat_session_id', '')
        if session_id:
            try:
                request_ai_service(
                    'DELETE',
                    f'/v1/chat/history/{session_id}',
                    params={'user_id': request.user.pk},
                    timeout=5,
                )
            except AIServiceError as e:
                return JsonResponse(
                    {'success': False, 'error': e.message},
                    status=e.status_code if 400 <= e.status_code < 600 else 503,
                )
            request.session['chat_session_id'] = str(uuid.uuid4())
        return JsonResponse({'success': True})


# ─────────────────────────────────────────────
# 2. DEMAND FORECASTING
# ─────────────────────────────────────────────

class ForecastView(LoginRequiredMixin, View):
    """
    Get/refresh demand forecast for a specific product.
    Returns JSON for Chart.js rendering on product detail page.
    """

    def get(self, request, product_id):
        """Return the AI service's cached or freshly computed forecast."""
        product = get_object_or_404(Product, id=product_id, is_active=True)
        try:
            result = request_ai_service('GET', f'/v1/forecast/{product_id}')
        except AIServiceError as e:
            return JsonResponse(
                {'success': False, 'product_name': product.name, 'error': e.message},
                status=e.status_code if 400 <= e.status_code < 600 else 503,
            )
        return JsonResponse({
            'success': result['success'],
            'product_name': product.name,
            'dates': result['dates'],
            'values': result['values'],
            'recommended_reorder': result['recommended_reorder'],
            'model': result['model'],
            'mae': result.get('mae'),
            'cached': result['cached'],
        })

    def post(self, request, product_id):
        """Force refresh forecast in the AI service."""
        product = get_object_or_404(Product, id=product_id, is_active=True)
        try:
            result = request_ai_service('POST', f'/v1/forecast/{product_id}')
        except AIServiceError as e:
            return JsonResponse(
                {'success': False, 'error': e.message},
                status=e.status_code if 400 <= e.status_code < 600 else 503,
            )
        product.last_reorder_qty = result['recommended_reorder']
        product.save(update_fields=['last_reorder_qty'])
        return JsonResponse({'success': True, 'product_id': product_id})


class ForecastDashboardView(LoginRequiredMixin, TemplateView):
    """
    Dashboard showing all product forecasts and reorder recommendations.
    """
    template_name = 'ai_assistant/forecast_dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from types import SimpleNamespace

        try:
            records = request_ai_service('GET', '/v1/forecasts')
        except AIServiceError as e:
            ctx['forecasts'] = []
            ctx['unforecasted'] = Product.objects.filter(is_active=True).count()
            ctx['forecast_error'] = e.message
            return ctx

        product_ids = [record['product_id'] for record in records]
        products = Product.objects.filter(
            id__in=product_ids, is_active=True
        ).select_related('category').in_bulk()
        ctx['forecasts'] = [
            SimpleNamespace(
                product=products[record['product_id']],
                recommended_reorder=record['recommended_reorder'],
                model_used=record['model'],
                mae=record['mae'],
                generated_at=parse_datetime(record['generated_at']),
                forecast_dates_json=json.dumps(record['dates']),
                forecast_values_json=json.dumps(record['values']),
            )
            for record in records
            if record['product_id'] in products
        ][:30]
        ctx['unforecasted'] = Product.objects.filter(
            is_active=True
        ).exclude(id__in=products.keys()).count()

        return ctx


class RunAllForecastsView(LoginRequiredMixin, View):
    def post(self, request):
        product_ids = list(Product.objects.filter(is_active=True).values_list('id', flat=True))
        try:
            result = request_ai_service(
                'POST',
                '/v1/forecasts',
                payload={'product_ids': product_ids},
                timeout=300,
            )
        except AIServiceError as e:
            return JsonResponse(
                {'success': False, 'error': e.message},
                status=e.status_code if 400 <= e.status_code < 600 else 503,
            )
        products_by_id = Product.objects.in_bulk(
            forecast['product_id'] for forecast in result['forecasts']
        )
        for forecast in result['forecasts']:
            product = products_by_id.get(forecast['product_id'])
            if product:
                product.last_reorder_qty = forecast['recommended_reorder']
        Product.objects.bulk_update(products_by_id.values(), ['last_reorder_qty'])
        return JsonResponse(result)


# ─────────────────────────────────────────────
# 3. SEMANTIC SEARCH
# ─────────────────────────────────────────────

class SemanticSearchView(LoginRequiredMixin, View):
    """
    Semantic product search endpoint.
    GET ?q=fever medicine → returns matching products as JSON (for AJAX)
    GET (no q) → renders search page
    """
    template_name = 'ai_assistant/semantic_search.html'

    def get(self, request):
        query = request.GET.get('q', '').strip()
        ajax = request.GET.get('ajax', '')

        if query:
            try:
                response = request_ai_service(
                    'GET', '/v1/search', params={'q': query, 'limit': 12}
                )
            except AIServiceError as e:
                if ajax:
                    return JsonResponse({'error': e.message}, status=e.status_code)
                return render(request, self.template_name, {
                    'query': query,
                    'results': [],
                    'error': e.message,
                })
            product_ids = [item['id'] for item in response['results']]
            products_by_id = Product.objects.filter(
                id__in=product_ids, is_active=True
            ).select_related('category').in_bulk()
            results = []
            scores = {item['id']: item['score'] for item in response['results']}
            for product_id in product_ids:
                product = products_by_id.get(product_id)
                if product:
                    product.similarity_score = scores[product_id]
                    results.append(product)
            if ajax:
                # Return JSON for AJAX requests
                data = []
                for p in results:
                    data.append({
                        'id': p.id,
                        'name': p.name,
                        'generic_name': p.generic_name,
                        'category': p.category.name if p.category else '-',
                        'current_stock': p.current_stock,
                        'selling_price': float(p.selling_price),
                        'is_low_stock': p.is_low_stock,
                        'similarity_score': p.similarity_score,
                        'url': f'/products/{p.id}/',
                    })
                return JsonResponse({'results': data, 'query': query, 'count': len(data)})
        else:
            results = []

        return render(request, self.template_name, {
            'query': query,
            'results': results,
        })


class ReindexProductsView(LoginRequiredMixin, View):
    """
    Admin utility: re-generate embeddings for all products.
    Only accessible by Admin/Manager.
    """

    def post(self, request):
        if not request.user.is_manager:
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

        try:
            count = request_ai_service('POST', '/v1/reindex')['count']
        except AIServiceError as e:
            return JsonResponse({'success': False, 'error': e.message}, status=e.status_code)
        return JsonResponse({
            'success': True,
            'message': f'Successfully indexed {count} products.',
            'count': count,
        })


# ─────────────────────────────────────────────
# STATUS CHECK
# ─────────────────────────────────────────────

class AIStatusView(LoginRequiredMixin, View):
    """Returns status of all AI components (for dashboard widget)."""

    def get(self, request):
        try:
            health = request_ai_service('GET', '/health', timeout=3)
            ai_service_ok = True
            ai_service_error = None
        except AIServiceError as e:
            ai_service_ok = False
            ai_service_error = e.message

        total = Product.objects.filter(is_active=True).count()

        return JsonResponse({
            'ai_service': {'running': ai_service_ok, 'error': ai_service_error},
            'ollama': {
                'running': health.get('ollama_running', False) if ai_service_ok else False,
                'models': health.get('models', []) if ai_service_ok else [],
            },
            'semantic_search': {
                'available': ai_service_ok,
                'indexed_products': None,
                'total_products': total,
            },
            'forecasting': {'available': ai_service_ok},
        })
