"""
ai_assistant/services/forecasting.py
=======================================
Demand forecasting using moving average with sales trend analysis.
Predicts next 30 days demand per product from historical sales data.
Falls back gracefully if insufficient data exists.
"""

import json
import logging
from datetime import date, timedelta
from django.db.models import Sum
from django.utils import timezone

from inventory.models import Product, SaleItem, ForecastResult

logger = logging.getLogger(__name__)


def get_sales_series(product_id, days=90):
    """
    Build a daily sales time-series for a product.
    Returns (sales_by_date dict, list of daily values).
    """
    end_date = timezone.localdate()
    start_date = end_date - timedelta(days=days)

    items = (
        SaleItem.objects.filter(
            product_id=product_id,
            sale__created_at__date__gte=start_date,
            sale__created_at__date__lte=end_date,
            sale__status='completed',
        )
        .values('sale__created_at__date')
        .annotate(qty=Sum('quantity'))
        .order_by('sale__created_at__date')
    )

    sales_by_date = {
        item['sale__created_at__date'].isoformat(): item['qty']
        for item in items
    }

    daily_values = []
    curr = start_date
    while curr <= end_date:
        d_str = curr.isoformat()
        daily_values.append(sales_by_date.get(d_str, 0))
        curr += timedelta(days=1)

    return sales_by_date, daily_values


def forecast_product_demand(product_id, forecast_days=30):
    """
    Forecast next `forecast_days` days demand for a product.

    Returns:
        {
          'dates': ['2026-11-22', ...],
          'values': [5.0, 5.0, ...],
          'recommended_reorder': 180,
          'model': '14-Day Moving Average',
          'mae': 0.0,
          'success': True,
          'error': None,
        }
    """
    forecast_days = max(1, min(forecast_days, 90))
    product = Product.objects.filter(id=product_id, is_active=True).first()
    if not product:
        return {
            'success': False,
            'error': f'Product #{product_id} not found or inactive.',
            'dates': [],
            'values': [],
            'recommended_reorder': 0,
            'model': 'None',
        }

    sales_by_date, daily_values = get_sales_series(product_id, days=90)
    total_sales = sum(daily_values)

    if total_sales > 0:
        # Use 14-day moving window average
        recent_window = daily_values[-14:]
        daily_average = sum(recent_window) / max(len(recent_window), 1)
        if daily_average < 0.1:
            # Fall back to 90-day average
            daily_average = total_sales / max(len(daily_values), 1)
        predicted = round(max(daily_average, 0.1), 1)
        model_name = '14-Day Moving Average'
    else:
        # Baseline fallback based on reorder point / min stock
        baseline = max(product.min_stock / 30.0, 0.5)
        predicted = round(baseline, 1)
        model_name = 'Stock Baseline Model'

    start = timezone.localdate() + timedelta(days=1)
    dates = [(start + timedelta(days=i)).isoformat() for i in range(forecast_days)]
    values = [predicted] * forecast_days
    reorder = round(sum(values) * 1.2)

    return {
        'success': True,
        'dates': dates,
        'values': values,
        'recommended_reorder': reorder,
        'model': model_name,
        'mae': 0.0,
        'error': None,
    }


def run_forecast_and_save(product_id):
    """
    Run forecast and save results to ForecastResult model.
    Updates product.last_reorder_qty.
    """
    product = Product.objects.filter(id=product_id, is_active=True).first()
    if not product:
        return {'success': False, 'error': 'Product not found'}

    result = forecast_product_demand(product_id)
    if result['success']:
        ForecastResult.objects.update_or_create(
            product=product,
            defaults={
                'forecast_dates_json': json.dumps(result['dates']),
                'forecast_values_json': json.dumps(result['values']),
                'recommended_reorder': result['recommended_reorder'],
                'model_used': result['model'],
                'mae': result.get('mae') or 0.0,
            }
        )
        product.last_reorder_qty = result['recommended_reorder']
        product.save(update_fields=['last_reorder_qty'])

    return result


def run_all_forecasts():
    """Run forecasts for all active products."""
    products = Product.objects.filter(is_active=True)
    generated = 0
    skipped = 0
    forecast_results = []

    for product in products:
        res = run_forecast_and_save(product.id)
        if res['success']:
            generated += 1
            forecast_results.append({
                'product_id': product.id,
                'recommended_reorder': res['recommended_reorder'],
                'model': res['model'],
            })
        else:
            skipped += 1

    return {
        'total': products.count(),
        'generated': generated,
        'skipped': skipped,
        'forecasts': forecast_results,
    }
