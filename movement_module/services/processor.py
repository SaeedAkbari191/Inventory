# movement_module/services/processor.py
from django.db import transaction
from .strategies import get_strategy_for
from ..models import ProductMovement, MovementStatus
from django.utils import timezone


class MovementProcessor:

    @classmethod
    def process(cls, movement: ProductMovement, run_async=False):

        # idempotency: اگر قبلاً پردازش شده، کاری نکن
        if movement.processed:
            return []

        # validation (business rules)
        movement.clean()

        strategy = get_strategy_for(movement.movement_type)

        created_txs = []

        # کل فرایند را در یک transaction دیتابیسی امن انجام می‌دهیم
        # هر segment نیز داخل استراتژی خودش atomic دارد (double safety)
        with transaction.atomic():
            created_txs = strategy.process(movement)

            # اگر همه segmentها پردازش شدند -> movement را تکمیل کن
            if not movement.segments.filter(processed=False).exists():
                movement.processed = True
                movement.status = MovementStatus.COMPLETED
                movement.completed_at = timezone.now()
                movement.save(update_fields=['processed', 'status', 'completed_at'])
            else:
                # اگر بعضی segmentها خطا داشتند، movement در وضعیت APPROVED باقی می‌ماند
                movement.save(update_fields=['status'])

        return created_txs
