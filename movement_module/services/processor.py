# movement_module/services/processor.py
from django.db import transaction
from .strategies import get_strategy_for
from ..models import ProductMovement, MovementStatus

class MovementProcessor:
    """
    دریافت یک ProductMovement و اجرای استراتژی مناسب.
    این کلاس مسئول idempotency، logging و تغییر وضعیت کلی movement است.
    """

    @classmethod
    def process(cls, movement: ProductMovement, run_async=False):
        """
        اگر run_async=True، باید این متد job را در queue بفرستد (Celery) — در این نمونه sync است.
        """
        # idempotency: اگر قبلاً پردازش شده، کاری نکن
        if movement.processed:
            return []

        # validation (business rules)
        movement.clean()

        strategy = get_strategy_for(movement.movement_type)

        created_txs = []
        # کل فرایند را در یک transaction دیتابیسی امن انجام می‌دهیم
        with transaction.atomic():
            # اجرا می‌کنیم (هر strategy خودش روی segments قفل می‌گیرد)
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
