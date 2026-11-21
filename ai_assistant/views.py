"""
ai_assistant/views.py
======================
Direct in-process views for:
1. AI Chatbot (Ollama-powered with context-aware fallback)
2. Demand Forecasting
3. Semantic Search
"""

import json
import uuid
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views import View
from django.views.generic import TemplateView

from inventory.models import ChatHistory, ForecastResult, Product
from .services.forecasting import (
    forecast_product_demand,
    run_forecast_and_save,
    run_all_forecasts,
)
from .services.ollama_service import (
    is_ollama_running,
    get_available_models,
    chat_with_ollama,
)
from .services.semantic_search import (
    semantic_search,
    reindex_all_products,
)


# ─────────────────────────────────────────────
# 1. AI CHATBOT
# ─────────────────────────────────────────────

class ChatbotView(LoginRequiredMixin, TemplateView):
    """
    Main chatbot interface.
    Renders the chat UI with conversation history.
    """
    template_name = 'ai_assistant/chatbot.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        if 'chat_session_id' not in self.request.session:
            self.request.session['chat_session_id'] = str(uuid.uuid4())
        session_id = self.request.session['chat_session_id']

        ctx['session_id'] = session_id
        ctx['ai_service_running'] = True
        ctx['ollama_running'] = is_ollama_running()
        ctx['available_models'] = get_available_models() if ctx['ollama_running'] else []

        history = list(
            ChatHistory.objects.filter(
                user=self.request.user,
                session_id=session_id
            ).order_by('created_at')
        )
        ctx['chat_history'] = history
        return ctx


class ChatAPIView(LoginRequiredMixin, View):
    """
    AJAX endpoint: POST a message, get AI response.
    Saves conversation to ChatHistory.
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

            # Record user message
            ChatHistory.objects.create(
                user=request.user,
                session_id=session_id,
                role='user',
                message=user_message,
            )

            # Retrieve recent conversation history
            recent_history = list(
                ChatHistory.objects.filter(
                    user=request.user,
                    session_id=session_id
                ).order_by('-created_at')[:10]
            )
            recent_history.reverse()

            history_payload = [
                {'role': item.role, 'message': item.message}
                for item in recent_history
            ]

            result = chat_with_ollama(user_message, history_payload)

            # Record assistant response
            if result.get('response'):
                ChatHistory.objects.create(
                    user=request.user,
                    session_id=session_id,
                    role='assistant',
                    message=result['response'],
                )

            return JsonResponse({
                'success': True,
                'response': result.get('response', ''),
                'error': result.get('error'),
                'model': result.get('model', 'SmartStock AI'),
            })

        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
        except Exception as exc:
            return JsonResponse({'success': False, 'error': str(exc)}, status=500)


class ClearChatView(LoginRequiredMixin, View):
    """Clear chat history for current session."""

    def post(self, request):
        session_id = request.session.get('chat_session_id', '')
        if session_id:
            ChatHistory.objects.filter(user=request.user, session_id=session_id).delete()
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
        product = get_object_or_404(Product, id=product_id, is_active=True)
        fc = ForecastResult.objects.filter(product=product).first()
        if not fc:
            result = run_forecast_and_save(product_id)
            if not result['success']:
                return JsonResponse({
                    'success': False,
                    'product_name': product.name,
                    'error': result.get('error', 'Forecast generation failed'),
                }, status=400)
            fc = ForecastResult.objects.filter(product=product).first()

        return JsonResponse({
            'success': True,
            'product_name': product.name,
            'dates': fc.get_dates(),
            'values': fc.get_values(),
            'recommended_reorder': fc.recommended_reorder,
            'model': fc.model_used,
            'mae': fc.mae,
            'cached': True,
        })

    def post(self, request, product_id):
        product = get_object_or_404(Product, id=product_id, is_active=True)
        result = run_forecast_and_save(product_id)
        if not result['success']:
            return JsonResponse({'success': False, 'error': result.get('error')}, status=400)
        return JsonResponse({'success': True, 'product_id': product_id})


class ForecastDashboardView(LoginRequiredMixin, TemplateView):
    """
    Dashboard showing all product forecasts and reorder recommendations.
    """
    template_name = 'ai_assistant/forecast_dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        forecasts = list(
            ForecastResult.objects.filter(product__is_active=True)
            .select_related('product', 'product__category')
            .order_by('-generated_at')[:30]
        )
        forecast_product_ids = {f.product_id for f in forecasts}
        unforecasted = Product.objects.filter(is_active=True).exclude(id__in=forecast_product_ids).count()

        ctx['forecasts'] = forecasts
        ctx['unforecasted'] = unforecasted
        ctx['forecast_error'] = None
        return ctx


class RunAllForecastsView(LoginRequiredMixin, View):
    """Compute demand forecasts for all active products."""

    def post(self, request):
        result = run_all_forecasts()
        return JsonResponse({'success': True, **result})


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
            results = semantic_search(query, top_k=12)
            if ajax:
                data = [
                    {
                        'id': p.id,
                        'name': p.name,
                        'generic_name': p.generic_name,
                        'category': p.category.name if p.category else '-',
                        'current_stock': p.current_stock,
                        'selling_price': float(p.selling_price),
                        'is_low_stock': p.is_low_stock,
                        'similarity_score': getattr(p, 'similarity_score', None),
                        'url': f'/products/{p.id}/',
                    }
                    for p in results
                ]
                return JsonResponse({'results': data, 'query': query, 'count': len(data)})
        else:
            results = []

        return render(request, self.template_name, {
            'query': query,
            'results': results,
        })


class ReindexProductsView(LoginRequiredMixin, View):
    """Admin utility: re-generate embeddings for all active products."""

    def post(self, request):
        if not request.user.is_manager:
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

        count = reindex_all_products()
        return JsonResponse({
            'success': True,
            'message': f'Successfully indexed {count} products.',
            'count': count,
        })


# ─────────────────────────────────────────────
# STATUS CHECK
# ─────────────────────────────────────────────

class AIStatusView(LoginRequiredMixin, View):
    """Returns status of AI components (for dashboard widget)."""

    def get(self, request):
        ollama_ok = is_ollama_running()
        total = Product.objects.filter(is_active=True).count()
        indexed = Product.objects.filter(is_active=True).exclude(embedding_json__isnull=True).exclude(embedding_json='').count()

        return JsonResponse({
            'ai_service': {'running': True, 'error': None},
            'ollama': {
                'running': ollama_ok,
                'models': get_available_models() if ollama_ok else [],
            },
            'semantic_search': {
                'available': True,
                'indexed_products': indexed,
                'total_products': total,
            },
            'forecasting': {'available': True},
        })
