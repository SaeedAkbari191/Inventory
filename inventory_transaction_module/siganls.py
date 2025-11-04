from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import InventoryTransaction


@receiver(post_save, sender=InventoryTransaction)
def update_stock_after_transaction(sender, instance, created, **kwargs):
    if created:
        instance.apply_transaction()
