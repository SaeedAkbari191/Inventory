# stock_module/models.py
from decimal import Decimal

from django.conf import settings
from django.db import models

from inventory_transaction_module.models import InventoryTransaction
from location_module.models import Warehouse, Section, Shelf
from product_module.models import Product


class Stock(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True)
    shelf = models.ForeignKey(Shelf, on_delete=models.SET_NULL, null=True, blank=True)

    # Use higher precision for quantities
    quantity = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0'))
    unit = models.CharField(max_length=50)

    class Meta:
        unique_together = ('product', 'warehouse', 'section', 'shelf')
        indexes = [
            models.Index(fields=['product', 'warehouse']),
        ]

    def __str__(self):
        return f"{self.product.name} - {self.warehouse.name}: {self.quantity} {self.unit}"

    def save(self, *args, **kwargs):
        # ensure unit defaults to product.base_unit if available and not set
        try:
            base_unit = getattr(self.product, 'base_unit', None)
        except Exception:
            base_unit = None

        if not self.unit and base_unit:
            self.unit = base_unit
        super().save(*args, **kwargs)

    def increase(self, qty):
        self.quantity = (self.quantity or Decimal('0.0')) + Decimal(qty)
        self.save(update_fields=['quantity'])

    def decrease(self, qty):
        self.quantity = (self.quantity or Decimal('0.0')) - Decimal(qty)
        self.save(update_fields=['quantity'])


class StockLedger(models.Model):
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name="ledgers")
    # InventoryTransaction could be in a different app; import by string to avoid circular imports
    transaction = models.ForeignKey('inventory_transaction_module.InventoryTransaction', on_delete=models.SET_NULL,
                                    null=True,
                                    blank=True)
    change = models.DecimalField(max_digits=18, decimal_places=4)  # مثبت یا منفی
    prev_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    new_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Stock Ledger Entry"
        verbose_name_plural = "Stock Ledger Entries"
        indexes = [
            models.Index(fields=['stock', 'created_at']),
        ]

    def __str__(self):
        return f"Ledger {self.pk} | Stock {self.stock_id} | change={self.change} | at {self.created_at}"
