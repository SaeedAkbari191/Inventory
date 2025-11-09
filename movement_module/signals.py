# movement_module/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import ProductMovement, MovementStatus
from .services.processor import MovementProcessor


# @receiver(post_save, sender=ProductMovement)
# def on_movement_saved(sender, instance, created, **kwargs):
    # فقط وقتی وضعیت از DRAFT به APPROVED تغییر کرد یا وقتی APPROVED و processed=False است
    # if instance.status == MovementStatus.APPROVED and not instance.processed:
        # sync processing (برای ترافیک بالا ترجیحا async via Celery)
        # MovementProcessor.process(instance, run_async=False)
