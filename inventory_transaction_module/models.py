from django.db import models
from django.utils import timezone
from django.conf import settings

from product_module.models import Product
from location_module.models import Warehouse, Section, Shelf
from user_module.models import User


class TransactionType(models.TextChoices):
    IN = 'IN', 'Inbound'
    OUT = 'OUT', 'Outbound'
    TRANSFER = 'TRANSFER', 'Transfer'


class InventoryTransaction(models.Model):
    transaction_type = models.CharField(max_length=10, choices=TransactionType.choices, verbose_name="Transaction Type")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="transactions")
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit = models.CharField(max_length=50, verbose_name="Unit")

    source_warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name="outgoing_transactions")
    source_section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name="outgoing_section_transactions")
    source_shelf = models.ForeignKey(Shelf, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name="outgoing_shelf_transactions")

    destination_warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True, blank=True,
                                              related_name="incoming_transactions")
    destination_section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True,
                                            related_name="incoming_section_transactions")
    destination_shelf = models.ForeignKey(Shelf, on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name="incoming_shelf_transactions")

    reference_number = models.CharField(max_length=100, blank=True, null=True, verbose_name="Reference Number")
    note = models.TextField(blank=True, null=True, verbose_name="Note")

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   related_name="created_transactions")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    # processed flag for idempotency: true after StockUpdater successfully applied
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Inventory Transaction"
        verbose_name_plural = "Inventory Transactions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=['transaction_type', 'product']),
            models.Index(fields=['reference_number']),
        ]

    def __str__(self):
        return f"{self.transaction_type} - {self.product.name} ({self.quantity} {self.unit})"
