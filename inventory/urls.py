"""Inventory app URL routing."""
from django.urls import path
from . import views

urlpatterns = [
    # Root redirect
    path('', views.DashboardView.as_view(), name='home'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),

    # Authentication
    path('accounts/register/', views.RegisterView.as_view(), name='register'),

    # Products
    path('products/', views.ProductListView.as_view(), name='product-list'),
    path('products/new/', views.ProductCreateView.as_view(), name='product-create'),
    path('products/<int:pk>/', views.ProductDetailView.as_view(), name='product-detail'),
    path('products/<int:pk>/edit/', views.ProductUpdateView.as_view(), name='product-update'),
    path('products/<int:pk>/delete/', views.ProductDeleteView.as_view(), name='product-delete'),
    path('products/<int:pk>/stock/', views.StockAdjustmentView.as_view(), name='stock-adjust'),

    # POS
    path('pos/', views.POSView.as_view(), name='pos'),
    path('pos/search/', views.POSProductSearchAPI.as_view(), name='pos-search'),
    path('pos/checkout/', views.CheckoutView.as_view(), name='checkout'),

    # Sales
    path('sales/', views.SaleListView.as_view(), name='sale-list'),
    path('sales/<int:pk>/', views.SaleDetailView.as_view(), name='sale-detail'),

    # Categories
    path('categories/', views.CategoryListView.as_view(), name='category-list'),
    path('categories/new/', views.CategoryCreateView.as_view(), name='category-create'),
    path('categories/<int:pk>/edit/', views.CategoryUpdateView.as_view(), name='category-update'),

    # Suppliers
    path('suppliers/', views.SupplierListView.as_view(), name='supplier-list'),
    path('suppliers/new/', views.SupplierCreateView.as_view(), name='supplier-create'),
    path('suppliers/<int:pk>/edit/', views.SupplierUpdateView.as_view(), name='supplier-update'),

    # Reports
    path('reports/', views.ReportsView.as_view(), name='reports'),
]
