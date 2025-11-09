# inventory/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import InventoryTransaction
from .services.stock_updater import StockUpdater

@receiver(post_save, sender=InventoryTransaction)
def update_stock_after_transaction(sender, instance, created, **kwargs):
    if created:
        StockUpdater.apply(instance)
