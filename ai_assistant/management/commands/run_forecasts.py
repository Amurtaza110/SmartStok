"""Run forecasts by calling the AI service for live sales data."""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from inventory.models import Product
from ai_assistant.services.ai_service_client import AIServiceError, request_ai_service


class Command(BaseCommand):
    help = 'Generate AI demand forecasts for all active products'

    def add_arguments(self, parser):
        parser.add_argument(
            '--product', type=int, default=None,
            help='Forecast a single product by ID'
        )
        parser.add_argument(
            '--reindex', action='store_true',
            help='Also reindex product embeddings for semantic search'
        )

    def handle(self, *args, **options):
        start = timezone.now()
        self.stdout.write(self.style.MIGRATE_HEADING(
            '\n🤖 SmartStock AI — Forecast Engine\n' + '─' * 40
        ))

        # ── Semantic Search Reindex ──
        if options['reindex']:
            self.stdout.write('📦 Reindexing product embeddings for semantic search…')
            try:
                count = request_ai_service('POST', '/v1/reindex')['count']
            except AIServiceError as exc:
                raise CommandError(exc.message) from exc
            self.stdout.write(self.style.SUCCESS(f'   ✅ Indexed {count} products'))

        # ── Forecasting ──
        products = Product.objects.filter(is_active=True)
        if options['product'] is not None:
            products = products.filter(pk=options['product'])
        if not products.exists():
            raise CommandError('No active products found for forecasting')

        try:
            result = request_ai_service(
                'POST',
                '/v1/forecasts',
                payload={'product_ids': list(products.values_list('id', flat=True))},
                timeout=300,
            )
        except AIServiceError as exc:
            raise CommandError(exc.message) from exc

        products_by_id = Product.objects.in_bulk(
            forecast['product_id'] for forecast in result['forecasts']
        )
        for forecast in result['forecasts']:
            product = products_by_id.get(forecast['product_id'])
            if product:
                product.last_reorder_qty = forecast['recommended_reorder']
        Product.objects.bulk_update(products_by_id.values(), ['last_reorder_qty'])

        elapsed = (timezone.now() - start).seconds
        self.stdout.write(self.style.SUCCESS(
            f'\nDone! Generated {result["generated"]}, skipped '
            f'{result["skipped"]} without sales data in {elapsed}s.\n'
        ))
