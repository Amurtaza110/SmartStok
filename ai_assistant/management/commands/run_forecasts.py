"""Run forecasts and semantic indexing directly."""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from inventory.models import Product
from ai_assistant.services.forecasting import run_forecast_and_save, run_all_forecasts
from ai_assistant.services.semantic_search import reindex_all_products


class Command(BaseCommand):
    help = 'Generate AI demand forecasts for active products'

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
            count = reindex_all_products()
            self.stdout.write(self.style.SUCCESS(f'   ✅ Indexed {count} products'))

        # ── Forecasting ──
        if options['product'] is not None:
            product = Product.objects.filter(pk=options['product'], is_active=True).first()
            if not product:
                raise CommandError(f'Active product #{options["product"]} not found.')
            result = run_forecast_and_save(product.id)
            if not result['success']:
                raise CommandError(result.get('error', 'Forecast failed'))
            self.stdout.write(self.style.SUCCESS(
                f'   ✅ Forecast generated for {product.name}: '
                f'Reorder {result["recommended_reorder"]} units (Model: {result["model"]})'
            ))
        else:
            result = run_all_forecasts()
            elapsed = (timezone.now() - start).seconds
            self.stdout.write(self.style.SUCCESS(
                f'\nDone! Generated {result["generated"]}, skipped '
                f'{result["skipped"]} without active data in {elapsed}s.\n'
            ))
