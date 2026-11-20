from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    CustomUser, Category, Supplier, Product,
    StockMovement, Sale, SaleItem, PurchaseOrder, ChatHistory, ForecastResult
)

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('SmartStock', {'fields': ('role', 'phone')}),
    )
    list_display = ['username', 'email', 'role', 'is_staff']
    list_filter = ['role']

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'product_count']

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['name', 'contact', 'email', 'city', 'is_active']
    list_filter = ['is_active', 'city']

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'current_stock', 'selling_price', 'is_low_stock', 'is_active']
    list_filter = ['category', 'supplier', 'is_active']
    search_fields = ['name', 'generic_name', 'barcode']
    readonly_fields = ['embedding_json', 'created_at', 'updated_at']

@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ['product', 'movement_type', 'quantity', 'balance_after', 'created_by', 'created_at']
    list_filter = ['movement_type']
    date_hierarchy = 'created_at'

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'customer_name', 'total_amount', 'cashier', 'status', 'created_at']
    list_filter = ['status']
    date_hierarchy = 'created_at'

@admin.register(ChatHistory)
class ChatHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'message', 'created_at']
    list_filter = ['role', 'user']

@admin.register(ForecastResult)
class ForecastResultAdmin(admin.ModelAdmin):
    list_display = ['product', 'recommended_reorder', 'model_used', 'generated_at']
    readonly_fields = ['forecast_dates_json', 'forecast_values_json']
