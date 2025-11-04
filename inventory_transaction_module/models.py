from django.db import models
from django.utils import timezone
from user_module.models import User
from product_module.models import Product
from location_module.models import Warehouse, Section, Shelf
from stock_module.models import Stock


class TransactionType(models.TextChoices):
    IN = 'IN', 'Inbound'
    OUT = 'OUT', 'Outbound'
    TRANSFER = 'TRANSFER', 'Transfer'


class InventoryTransaction(models.Model):
    transaction_type = models.CharField(
        max_length=10,
        choices=TransactionType.choices,
        verbose_name="Transaction Type"
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="transactions")
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    unit = models.CharField(max_length=50, verbose_name="Unit")

    source_warehouse = models.ForeignKey(
        Warehouse, on_delete=models.SET_NULL, null=True, blank=True, related_name="outgoing_transactions"
    )
    source_section = models.ForeignKey(
        Section, on_delete=models.SET_NULL, null=True, blank=True, related_name="outgoing_section_transactions"
    )
    source_shelf = models.ForeignKey(
        Shelf, on_delete=models.SET_NULL, null=True, blank=True, related_name="outgoing_shelf_transactions"
    )

    destination_warehouse = models.ForeignKey(
        Warehouse, on_delete=models.SET_NULL, null=True, blank=True, related_name="incoming_transactions"
    )
    destination_section = models.ForeignKey(
        Section, on_delete=models.SET_NULL, null=True, blank=True, related_name="incoming_section_transactions"
    )
    destination_shelf = models.ForeignKey(
        Shelf, on_delete=models.SET_NULL, null=True, blank=True, related_name="incoming_shelf_transactions"
    )

    reference_number = models.CharField(max_length=100, blank=True, null=True, verbose_name="Reference Number")
    note = models.TextField(blank=True, null=True, verbose_name="Note")

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="created_transactions")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Inventory Transaction"
        verbose_name_plural = "Inventory Transactions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.transaction_type} - {self.product.name} ({self.quantity} {self.unit})"

    def apply_transaction(self):
        if self.transaction_type == 'IN':
            stock, _ = Stock.objects.get_or_create(
                product=self.product,
                warehouse=self.destination_warehouse,
                section=self.destination_section,
                shelf=self.destination_shelf,
                defaults={'quantity': 0, 'unit': self.unit}
            )
            stock.increase(self.quantity)

        elif self.transaction_type == 'OUT':
            stock = Stock.objects.filter(
                product=self.product,
                warehouse=self.source_warehouse,
                section=self.source_section,
                shelf=self.source_shelf,
            ).first()
            if stock:
                stock.decrease(self.quantity)

        elif self.transaction_type == 'TRANSFER':
            source_stock = Stock.objects.filter(
                product=self.product,
                warehouse=self.source_warehouse,
                section=self.source_section,
                shelf=self.source_shelf,
            ).first()
            dest_stock, _ = Stock.objects.get_or_create(
                product=self.product,
                warehouse=self.destination_warehouse,
                section=self.destination_section,
                shelf=self.destination_shelf,
                defaults={'quantity': 0, 'unit': self.unit}
            )
            if source_stock:
                source_stock.decrease(self.quantity)
            dest_stock.increase(self.quantity)
