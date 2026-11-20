"""
SmartStock Inventory Views
===========================
Class-Based Views using Django MVT architecture.
Covers: Dashboard, Products, Sales, POS, Reports, Stock Management.
"""

import json
import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Sum, Count, F, Q, Avg
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views import View
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
)
from django.urls import reverse_lazy

from .models import (
    CustomUser, Category, Supplier, Product,
    StockMovement, Sale, SaleItem, PurchaseOrder, PurchaseOrderItem
)
from .forms import (
    ProductForm, CategoryForm, SupplierForm,
    SaleForm, StockAdjustmentForm, UserRegistrationForm
)


# ─────────────────────────────────────────────
# MIXINS
# ─────────────────────────────────────────────

class RoleRequiredMixin(UserPassesTestMixin):
    """Restrict views to specific roles."""
    allowed_roles = []

    def test_func(self):
        return self.request.user.is_authenticated and (
            self.request.user.role in self.allowed_roles or
            self.request.user.role == 'Admin'
        )


class ManagerRequiredMixin(RoleRequiredMixin):
    allowed_roles = ['Admin', 'Manager']


class AdminRequiredMixin(RoleRequiredMixin):
    allowed_roles = ['Admin']


# ─────────────────────────────────────────────
# AUTHENTICATION
# ─────────────────────────────────────────────

class RegisterView(View):
    template_name = 'registration/register.html'

    def get(self, request):
        form = UserRegistrationForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome, {user.username}! Account created.")
            return redirect('dashboard')
        return render(request, self.template_name, {'form': form})


# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────

class DashboardView(LoginRequiredMixin, TemplateView):
    """
    Main dashboard with KPIs, charts data, and alerts.
    All chart data is serialized to JSON for Chart.js.
    """
    template_name = 'inventory/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.localdate()
        month_start = today.replace(day=1)

        # ── KPIs ──
        ctx['total_products'] = Product.objects.filter(is_active=True).count()
        ctx['low_stock_count'] = Product.objects.filter(
            current_stock__lte=F('min_stock'), is_active=True
        ).count()
        ctx['expiring_soon_count'] = Product.objects.filter(
            expiry_date__lte=today + timedelta(days=30),
            expiry_date__gte=today,
            is_active=True
        ).count()
        ctx['total_stock_value'] = Product.objects.filter(is_active=True).aggregate(
            val=Sum(F('current_stock') * F('purchase_price'))
        )['val'] or 0

        # ── Sales this month ──
        month_sales = Sale.objects.filter(
            created_at__gte=month_start, status='completed'
        )
        ctx['monthly_sales_count'] = month_sales.count()
        ctx['monthly_revenue'] = month_sales.aggregate(
            t=Sum('total_amount')
        )['t'] or 0

        # ── Sales chart: last 30 days ──
        chart_start = today - timedelta(days=29)
        daily_revenue = Sale.objects.filter(
            created_at__date__gte=chart_start,
            created_at__date__lte=today,
            status='completed',
        ).values('created_at__date').annotate(
            revenue=Sum('total_amount')
        )
        revenue_by_date = {row['created_at__date']: row['revenue'] for row in daily_revenue}
        chart_dates = [chart_start + timedelta(days=offset) for offset in range(30)]
        ctx['chart_labels'] = [day.strftime('%b %d') for day in chart_dates]
        ctx['chart_sales'] = [
            float(revenue_by_date.get(day, 0)) for day in chart_dates
        ]
        ctx['has_sales_30d'] = bool(revenue_by_date)

        # ── Category distribution ──
        cat_data = Category.objects.annotate(
            cnt=Count('product', filter=Q(product__is_active=True))
        ).filter(cnt__gt=0).values('name', 'cnt').order_by('-cnt')[:8]
        ctx['chart_cat_labels'] = [c['name'] for c in cat_data]
        ctx['chart_cat_values'] = [c['cnt'] for c in cat_data]

        # ── Top 10 best-selling products ──
        top_products = SaleItem.objects.values(
            'product__name'
        ).annotate(
            total_qty=Sum('quantity')
        ).filter(sale__status='completed').order_by('-total_qty')[:10]
        ctx['chart_top_labels'] = [p['product__name'] for p in top_products]
        ctx['chart_top_values'] = [p['total_qty'] for p in top_products]
        ctx['dashboard_date'] = today

        # ── Recent alerts ──
        ctx['low_stock_products'] = Product.objects.filter(
            current_stock__lte=F('min_stock'), is_active=True
        ).order_by('current_stock')[:5]
        ctx['expiring_products'] = Product.objects.filter(
            expiry_date__lte=today + timedelta(days=30),
            expiry_date__gte=today, is_active=True
        ).order_by('expiry_date')[:5]

        # ── Recent sales ──
        ctx['recent_sales'] = Sale.objects.select_related('cashier').order_by('-created_at')[:8]

        return ctx


# ─────────────────────────────────────────────
# PRODUCTS
# ─────────────────────────────────────────────

class ProductListView(LoginRequiredMixin, ListView):
    model = Product
    template_name = 'inventory/product_list.html'
    context_object_name = 'products'
    paginate_by = 20

    def get_queryset(self):
        qs = Product.objects.filter(is_active=True).select_related('category', 'supplier')
        q = self.request.GET.get('q', '').strip()
        category = self.request.GET.get('category', '')
        stock_filter = self.request.GET.get('stock', '')

        if q:
            qs = qs.filter(
                Q(name__icontains=q) | Q(generic_name__icontains=q) | Q(barcode__icontains=q)
            )
        if category:
            qs = qs.filter(category__id=category)
        if stock_filter == 'low':
            qs = qs.filter(current_stock__lte=F('min_stock'))
        elif stock_filter == 'out':
            qs = qs.filter(current_stock=0)
        elif stock_filter == 'expiring':
            qs = qs.filter(
                expiry_date__lte=date.today() + timedelta(days=30),
                expiry_date__gte=date.today()
            )

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['categories'] = Category.objects.all()
        ctx['q'] = self.request.GET.get('q', '')
        ctx['selected_category'] = self.request.GET.get('category', '')
        ctx['stock_filter'] = self.request.GET.get('stock', '')
        return ctx


class ProductDetailView(LoginRequiredMixin, DetailView):
    model = Product
    template_name = 'inventory/product_detail.html'
    context_object_name = 'product'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        product = self.object

        # Stock movement history
        ctx['movements'] = StockMovement.objects.filter(
            product=product
        ).order_by('-created_at')[:30]

        # Sales history (last 30 days)
        thirty_ago = date.today() - timedelta(days=30)
        sale_items = SaleItem.objects.filter(
            product=product, sale__created_at__date__gte=thirty_ago
        ).values('sale__created_at__date').annotate(
            qty=Sum('quantity')
        ).order_by('sale__created_at__date')

        ctx['sales_labels'] = json.dumps([str(s['sale__created_at__date']) for s in sale_items])
        ctx['sales_data'] = json.dumps([s['qty'] for s in sale_items])

        # Forecast data if available
        try:
            forecast = product.forecast
            ctx['forecast'] = forecast
            ctx['forecast_dates'] = json.dumps(forecast.get_dates())
            ctx['forecast_values'] = json.dumps(forecast.get_values())
        except Exception:
            ctx['forecast'] = None

        return ctx


class ProductCreateView(LoginRequiredMixin, ManagerRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = 'inventory/product_form.html'
    success_url = reverse_lazy('product-list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Product '{self.object.name}' created successfully!")
        return response


class ProductUpdateView(LoginRequiredMixin, ManagerRequiredMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = 'inventory/product_form.html'
    success_url = reverse_lazy('product-list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Product '{self.object.name}' updated.")
        return response


class ProductDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = Product
    template_name = 'inventory/product_confirm_delete.html'
    success_url = reverse_lazy('product-list')

    def form_valid(self, form):
        # Soft delete instead of hard delete
        self.object.is_active = False
        self.object.save()
        messages.warning(self.request, f"Product '{self.object.name}' deactivated.")
        return redirect(self.success_url)


# ─────────────────────────────────────────────
# STOCK MANAGEMENT
# ─────────────────────────────────────────────

class StockAdjustmentView(LoginRequiredMixin, ManagerRequiredMixin, View):
    template_name = 'inventory/stock_adjustment.html'

    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        form = StockAdjustmentForm()
        return render(request, self.template_name, {'product': product, 'form': form})

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        form = StockAdjustmentForm(request.POST)
        if form.is_valid():
            movement_type = form.cleaned_data['movement_type']
            qty = form.cleaned_data['quantity']
            notes = form.cleaned_data['notes']

            old_stock = product.current_stock
            if movement_type == 'IN':
                product.current_stock += qty
            elif movement_type in ('OUT', 'EXPIRED'):
                if qty > product.current_stock:
                    messages.error(request, "Quantity exceeds current stock!")
                    return render(request, self.template_name, {'product': product, 'form': form})
                product.current_stock -= qty
            elif movement_type == 'ADJUST':
                product.current_stock = qty  # Set to exact amount

            product.save()

            StockMovement.objects.create(
                product=product,
                movement_type=movement_type,
                quantity=qty,
                balance_after=product.current_stock,
                notes=notes,
                created_by=request.user,
            )
            messages.success(request,
                f"Stock updated: {old_stock} → {product.current_stock} {product.unit}")
            return redirect('product-detail', pk=pk)

        return render(request, self.template_name, {'product': product, 'form': form})


# ─────────────────────────────────────────────
# POINT OF SALE (POS)
# ─────────────────────────────────────────────

class POSView(LoginRequiredMixin, View):
    """POS terminal - barcode scan / search → cart → checkout."""
    template_name = 'inventory/pos.html'

    def get(self, request):
        return render(request, self.template_name)


class POSProductSearchAPI(LoginRequiredMixin, View):
    """AJAX endpoint: search product by name or barcode for POS."""

    def get(self, request):
        query = request.GET.get('q', '').strip()
        if not query:
            return JsonResponse({'products': []})
        products = Product.objects.filter(
            Q(name__icontains=query) | Q(barcode__exact=query),
            is_active=True, current_stock__gt=0
        ).values('id', 'name', 'selling_price', 'current_stock', 'unit')[:10]
        return JsonResponse({'products': list(products)})


class CheckoutView(LoginRequiredMixin, View):
    """Process a sale from POS cart data (JSON POST)."""

    def post(self, request):
        try:
            data = json.loads(request.body)
            cart = data.get('cart', [])
            customer = data.get('customer_name', 'Walk-in Customer')
            paid = Decimal(str(data.get('paid_amount', 0)))
            discount = Decimal(str(data.get('discount', 0)))

            if not cart:
                return JsonResponse({'success': False, 'error': 'Cart is empty'})

            # Generate invoice number
            invoice_no = f"INV-{timezone.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"
            total = Decimal('0')

            sale = Sale.objects.create(
                invoice_number=invoice_no,
                customer_name=customer,
                cashier=request.user,
                discount=discount,
                paid_amount=paid,
                status='completed',
            )

            for item in cart:
                product = Product.objects.get(id=item['product_id'])
                qty = int(item['quantity'])
                price = Decimal(str(item['price']))
                item_total = qty * price

                SaleItem.objects.create(
                    sale=sale,
                    product=product,
                    quantity=qty,
                    unit_price=price,
                    total_price=item_total,
                )

                # Deduct stock
                product.current_stock = max(0, product.current_stock - qty)
                product.save()

                # Record movement
                StockMovement.objects.create(
                    product=product,
                    movement_type='OUT',
                    quantity=qty,
                    balance_after=product.current_stock,
                    reference=invoice_no,
                    created_by=request.user,
                )

                total += item_total

            sale.total_amount = total
            sale.save()

            return JsonResponse({
                'success': True,
                'invoice_number': invoice_no,
                'total': float(total),
                'change': float(max(0, paid - (total - discount))),
            })

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})


# ─────────────────────────────────────────────
# SALES
# ─────────────────────────────────────────────

class SaleListView(LoginRequiredMixin, ListView):
    model = Sale
    template_name = 'inventory/sale_list.html'
    context_object_name = 'sales'
    paginate_by = 20

    def get_queryset(self):
        qs = Sale.objects.select_related('cashier').order_by('-created_at')
        date_from = self.request.GET.get('from')
        date_to = self.request.GET.get('to')
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['total_revenue'] = self.get_queryset().aggregate(
            t=Sum('total_amount'))['t'] or 0
        return ctx


class SaleDetailView(LoginRequiredMixin, DetailView):
    model = Sale
    template_name = 'inventory/sale_detail.html'
    context_object_name = 'sale'


# ─────────────────────────────────────────────
# CATEGORIES & SUPPLIERS (CRUD)
# ─────────────────────────────────────────────

class CategoryListView(LoginRequiredMixin, ListView):
    model = Category
    template_name = 'inventory/category_list.html'
    context_object_name = 'categories'


class CategoryCreateView(LoginRequiredMixin, ManagerRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = 'inventory/category_form.html'
    success_url = reverse_lazy('category-list')


class CategoryUpdateView(LoginRequiredMixin, ManagerRequiredMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = 'inventory/category_form.html'
    success_url = reverse_lazy('category-list')


class SupplierListView(LoginRequiredMixin, ListView):
    model = Supplier
    template_name = 'inventory/supplier_list.html'
    context_object_name = 'suppliers'

    def get_queryset(self):
        return Supplier.objects.filter(is_active=True)


class SupplierCreateView(LoginRequiredMixin, ManagerRequiredMixin, CreateView):
    model = Supplier
    form_class = SupplierForm
    template_name = 'inventory/supplier_form.html'
    success_url = reverse_lazy('supplier-list')


class SupplierUpdateView(LoginRequiredMixin, ManagerRequiredMixin, UpdateView):
    model = Supplier
    form_class = SupplierForm
    template_name = 'inventory/supplier_form.html'
    success_url = reverse_lazy('supplier-list')


# ─────────────────────────────────────────────
# REPORTS
# ─────────────────────────────────────────────

class ReportsView(LoginRequiredMixin, ManagerRequiredMixin, TemplateView):
    template_name = 'inventory/reports.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()

        # Monthly sales trend (last 12 months)
        monthly = []
        for i in range(11, -1, -1):
            m_start = (today.replace(day=1) - timedelta(days=i * 30)).replace(day=1)
            m_end = (m_start.replace(month=m_start.month % 12 + 1, day=1)
                     if m_start.month < 12 else m_start.replace(year=m_start.year + 1, month=1, day=1))
            rev = Sale.objects.filter(
                created_at__date__gte=m_start,
                created_at__date__lt=m_end,
                status='completed'
            ).aggregate(t=Sum('total_amount'))['t'] or 0
            monthly.append({'label': m_start.strftime('%b %Y'), 'revenue': float(rev)})

        ctx['monthly_labels'] = json.dumps([m['label'] for m in monthly])
        ctx['monthly_revenue'] = json.dumps([m['revenue'] for m in monthly])

        # Top products by revenue
        top_products = SaleItem.objects.values('product__name').annotate(
            revenue=Sum(F('quantity') * F('unit_price'))
        ).order_by('-revenue')[:10]
        ctx['top_product_labels'] = json.dumps([p['product__name'] for p in top_products])
        ctx['top_product_revenue'] = json.dumps([float(p['revenue']) for p in top_products])

        # Inventory value by category
        cat_value = Category.objects.annotate(
            val=Sum(F('product__current_stock') * F('product__purchase_price'),
                    filter=Q(product__is_active=True))
        ).values('name', 'val').order_by('-val')
        ctx['cat_value_labels'] = json.dumps([c['name'] for c in cat_value])
        ctx['cat_value_data'] = json.dumps([float(c['val'] or 0) for c in cat_value])

        # Summary stats
        ctx['total_inventory_value'] = Product.objects.filter(is_active=True).aggregate(
            v=Sum(F('current_stock') * F('purchase_price'))
        )['v'] or 0
        ctx['total_sales_ever'] = Sale.objects.filter(
            status='completed').aggregate(t=Sum('total_amount'))['t'] or 0
        ctx['total_products'] = Product.objects.filter(is_active=True).count()
        ctx['low_stock_products'] = Product.objects.filter(
            current_stock__lte=F('min_stock'), is_active=True
        )

        return ctx
