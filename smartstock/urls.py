"""
SmartStock - Main URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from inventory.internal_api import (
    AIInventoryContextView,
    AIProductsView,
    AISalesHistoryView,
    HealthView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', HealthView.as_view(), name='health'),
    path('internal/ai/context/', AIInventoryContextView.as_view(), name='internal-ai-context'),
    path('internal/ai/products/', AIProductsView.as_view(), name='internal-ai-products'),
    path('internal/ai/sales/<int:product_id>/', AISalesHistoryView.as_view(), name='internal-ai-sales'),

    # Authentication
    path('accounts/', include('django.contrib.auth.urls')),

    # Main inventory app
    path('', include('inventory.urls')),

    # AI Assistant app
    path('ai-features/', include('ai_assistant.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
