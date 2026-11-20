"""Move existing chat and forecast records into the AI service database."""

from django.core.management.base import BaseCommand, CommandError

from ai_assistant.services.ai_service_client import AIServiceError, request_ai_service
from inventory.models import ChatHistory, ForecastResult


class Command(BaseCommand):
    help = 'Import legacy chat and forecast records into the AI service database'

    def add_arguments(self, parser):
        parser.add_argument('--batch-size', type=int, default=200)

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        if batch_size < 1 or batch_size > 1000:
            raise CommandError('Batch size must be between 1 and 1000')

        chats = ChatHistory.objects.order_by('pk').values(
            'id', 'user_id', 'session_id', 'role', 'message', 'created_at'
        )
        chat_batch = []
        imported_chats = 0
        for record in chats.iterator(chunk_size=batch_size):
            record['created_at'] = record['created_at'].isoformat()
            chat_batch.append(record)
            if len(chat_batch) == batch_size:
                self._import('/v1/migrate/chat-history', chat_batch)
                imported_chats += len(chat_batch)
                chat_batch = []
        if chat_batch:
            self._import('/v1/migrate/chat-history', chat_batch)
            imported_chats += len(chat_batch)

        forecasts = []
        for forecast in ForecastResult.objects.select_related('product').iterator(
            chunk_size=batch_size
        ):
            forecasts.append({
                'product_id': forecast.product_id,
                'dates': forecast.get_dates(),
                'values': forecast.get_values(),
                'recommended_reorder': forecast.recommended_reorder,
                'model_used': forecast.model_used,
                'mae': forecast.mae,
                'generated_at': forecast.generated_at.isoformat(),
            })
            if len(forecasts) == batch_size:
                self._import('/v1/migrate/forecasts', forecasts)
                forecasts = []
        if forecasts:
            self._import('/v1/migrate/forecasts', forecasts)

        self.stdout.write(self.style.SUCCESS(
            f'Imported {imported_chats} legacy chat messages and '
            f'{ForecastResult.objects.count()} forecast records.'
        ))

    @staticmethod
    def _import(path, records):
        try:
            request_ai_service(
                'POST',
                path,
                payload={'records': records},
                timeout=60,
            )
        except AIServiceError as exc:
            raise CommandError(f'AI data import failed: {exc.message}') from exc
