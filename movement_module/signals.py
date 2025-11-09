# movement_module/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import ProductMovement, MovementStatus
from .services.processor import MovementProcessor

@receiver(post_save, sender=ProductMovement)
def movement_post_save(sender, instance: ProductMovement, created, **kwargs):
    # اگر وضعیت به APPROVED تغییر یافته و هنوز processed نیست، پردازش کن
    if instance.status == MovementStatus.APPROVED and not instance.processed:

        MovementProcessor.process(instance, run_async=False)
