"""ai_assistant URL routing."""
from django.urls import path
from . import views

app_name = 'ai'

urlpatterns = [
    # Chatbot
    path('chatbot/', views.ChatbotView.as_view(), name='chatbot'),
    path('chat-api/', views.ChatAPIView.as_view(), name='chat-api'),
    path('chat-clear/', views.ClearChatView.as_view(), name='chat-clear'),

    # Demand Forecasting
    path('forecast/<int:product_id>/', views.ForecastView.as_view(), name='forecast'),
    path('forecast/run/', views.RunAllForecastsView.as_view(), name='run-forecasts'),
    path('forecast/dashboard/', views.ForecastDashboardView.as_view(), name='forecast-dashboard'),

    # Semantic Search
    path('search/', views.SemanticSearchView.as_view(), name='semantic-search'),
    path('reindex/', views.ReindexProductsView.as_view(), name='reindex'),

    # Status
    path('status/', views.AIStatusView.as_view(), name='status'),
]
