"""
SmartStock Inventory Models
============================
Complete database schema for the inventory management system.
Includes extended Product model with AI embedding support.
"""

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.validators import MinValueValidator
import json


# ─────────────────────────────────────────────
# USERS & ROLES
# ─────────────────────────────────────────────

class CustomUser(AbstractUser):
    """Extended user model with role-based access control."""

    ROLE_CHOICES = (
        ('Admin',   'Admin'),
        ('Manager', 'Manager'),
        ('Cashier', 'Cashier'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Cashier')
    phone = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)

    def __str__(self):
        return f"{self.username} ({self.role})"

    # Permission helpers used in templates and views
    @property
    def is_admin(self):
        return self.role == 'Admin'

    @property
    def is_manager(self):
        return self.role in ('Admin', 'Manager')

    @property
    def is_cashier(self):
        return True  # All roles can perform cashier actions


# ─────────────────────────────────────────────
# CATEGORY & SUPPLIER
# ─────────────────────────────────────────────

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default='bi-box-seam')  # Bootstrap icon class

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def __str__(self):
        return self.name

    def product_count(self):
        return self.product_set.count()


class Supplier(models.Model):
    name = models.CharField(max_length=200)
    contact = models.CharField(max_length=50)
    address = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


# ─────────────────────────────────────────────
# PRODUCT
# ─────────────────────────────────────────────

class Product(models.Model):
    """
    Core product model.
    New fields vs original:
    - description, tags           → for richer semantic search
    - embedding_json              → stores sentence-transformer vector
    - last_reorder_qty            → AI-suggested reorder (filled by forecast module)
    - reorder_point               → stock level that triggers alert
    """

    name = models.CharField(max_length=200)
    generic_name = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True, help_text="Product description for AI search")
    tags = models.CharField(max_length=300, blank=True,
                            help_text="Comma-separated tags: 'fever,pain,antibiotic'")
    barcode = models.CharField(max_length=100, unique=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2,
                                         validators=[MinValueValidator(0)])
    selling_price = models.DecimalField(max_digits=10, decimal_places=2,
                                         validators=[MinValueValidator(0)])
    unit = models.CharField(max_length=50, default='pcs')
    min_stock = models.IntegerField(default=10, help_text="Minimum stock threshold for alerts")
    reorder_point = models.IntegerField(default=20,
                                        help_text="Stock level that triggers reorder suggestion")
    current_stock = models.IntegerField(default=0)
    expiry_date = models.DateField(null=True, blank=True)
    batch_number = models.CharField(max_length=100, blank=True)

    # AI Fields
    # Stores the numpy vector as JSON string for semantic search
    embedding_json = models.TextField(blank=True, null=True,
                                       help_text="Sentence-transformer embedding (auto-generated)")
    # AI-suggested reorder quantity (updated by forecast module)
    last_reorder_qty = models.IntegerField(default=0,
                                            help_text="AI-recommended reorder quantity")

    image = models.ImageField(upload_to='products/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    # ── Computed Properties ──
    @property
    def is_low_stock(self):
        return self.current_stock <= self.min_stock

    @property
    def is_expiring_soon(self):
        if not self.expiry_date:
            return False
        from datetime import date, timedelta
        return self.expiry_date <= date.today() + timedelta(days=30)

    @property
    def is_expired(self):
        if not self.expiry_date:
            return False
        from datetime import date
        return self.expiry_date < date.today()

    @property
    def profit_margin(self):
        if self.purchase_price > 0:
            return round(((self.selling_price - self.purchase_price) / self.selling_price) * 100, 1)
        return 0

    @property
    def stock_value(self):
        return self.current_stock * self.purchase_price

    def get_embedding(self):
        """Return the stored embedding as a Python list."""
        if self.embedding_json:
            return json.loads(self.embedding_json)
        return None

    def set_embedding(self, vector):
        """Save embedding vector (list/ndarray) to JSON field."""
        if hasattr(vector, 'tolist'):
            vector = vector.tolist()
        self.embedding_json = json.dumps(vector)

    def get_searchable_text(self):
        """Text used for generating semantic search embedding."""
        parts = [self.name, self.generic_name, self.description, self.tags]
        if self.category:
            parts.append(self.category.name)
        return ' '.join(filter(None, parts))


# ─────────────────────────────────────────────
# STOCK MOVEMENTS
# ─────────────────────────────────────────────

class StockMovement(models.Model):
    """Records every stock change (purchase, sale, adjustment, return)."""

    MOVEMENT_TYPES = (
        ('IN',         'Stock In (Purchase)'),
        ('OUT',        'Stock Out (Sale)'),
        ('ADJUST',     'Adjustment'),
        ('RETURN',     'Return'),
        ('EXPIRED',    'Expired Removal'),
    )

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='movements')
    movement_type = models.CharField(max_length=10, choices=MOVEMENT_TYPES)
    quantity = models.IntegerField()
    balance_after = models.IntegerField(help_text="Stock level after this movement")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reference = models.CharField(max_length=100, blank=True,
                                  help_text="Sale ID, PO number, etc.")

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.product.name} {self.movement_type} {self.quantity}"


# ─────────────────────────────────────────────
# SALES
# ─────────────────────────────────────────────

class Sale(models.Model):
    """A sale transaction (invoice header)."""

    STATUS_CHOICES = (
        ('pending',   'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )

    invoice_number = models.CharField(max_length=50, unique=True)
    customer_name = models.CharField(max_length=200, blank=True, default='Walk-in Customer')
    customer_phone = models.CharField(max_length=20, blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='completed')
    cashier = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True,
                                 related_name='sales')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Invoice #{self.invoice_number}"

    @property
    def net_total(self):
        return self.total_amount - self.discount

    @property
    def change_amount(self):
        return max(0, self.paid_amount - self.net_total)


class SaleItem(models.Model):
    """Line items in a sale (invoice detail)."""

    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.sale.invoice_number} - {self.product.name} x{self.quantity}"

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────
# PURCHASE ORDERS
# ─────────────────────────────────────────────

class PurchaseOrder(models.Model):
    """Purchase order sent to a supplier."""

    STATUS_CHOICES = (
        ('draft',     'Draft'),
        ('ordered',   'Ordered'),
        ('received',  'Received'),
        ('cancelled', 'Cancelled'),
    )

    po_number = models.CharField(max_length=50, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    ordered_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True)
    expected_delivery = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    received_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"PO #{self.po_number}"


class PurchaseOrderItem(models.Model):
    """Line items in a purchase order."""

    order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity_ordered = models.IntegerField(validators=[MinValueValidator(1)])
    quantity_received = models.IntegerField(default=0)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        self.total_cost = self.quantity_ordered * self.unit_cost
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────
# AI CHAT HISTORY (for ai_assistant app)
# ─────────────────────────────────────────────

class ChatHistory(models.Model):
    """Stores AI chatbot conversation history per user."""

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='chats')
    session_id = models.CharField(max_length=100)
    role = models.CharField(max_length=10, choices=(('user', 'User'), ('assistant', 'Assistant')))
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.user.username} [{self.role}]: {self.message[:50]}"


# ─────────────────────────────────────────────
# DEMAND FORECAST RESULTS
# ─────────────────────────────────────────────

class ForecastResult(models.Model):
    """Cached forecast results for each product."""

    product = models.OneToOneField(Product, on_delete=models.CASCADE,
                                    related_name='forecast')
    forecast_dates_json = models.TextField()       # JSON list of date strings
    forecast_values_json = models.TextField()      # JSON list of predicted quantities
    recommended_reorder = models.IntegerField(default=0)
    model_used = models.CharField(max_length=100, default='AutoARIMA')
    mae = models.FloatField(default=0, help_text="Mean Absolute Error of model")
    generated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Forecast for {self.product.name} @ {self.generated_at.date()}"

    def get_dates(self):
        return json.loads(self.forecast_dates_json)

    def get_values(self):
        return json.loads(self.forecast_values_json)
