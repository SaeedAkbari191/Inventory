from decimal import Decimal
from django.db import models, transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.conf import settings
from user_module.models import User
from product_module.models import Product
from location_module.models import Warehouse
from inventory_transaction_module.models import InventoryTransaction




class MovementType(models.TextChoices):
    IN = "IN", "Inbound"
    OUT = "OUT", "Outbound"
    TRANSFER = "TRANSFER", "Transfer"


class MovementStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    APPROVED = "APPROVED", "Approved"
    IN_TRANSIT = "IN_TRANSIT", "In Transit"
    COMPLETED = "COMPLETED", "Completed"
    CANCELLED = "CANCELLED", "Cancelled"


class ProductMovement(models.Model):
    reference_no = models.CharField(max_length=128, unique=True)
    movement_type = models.CharField(max_length=20, choices=MovementType.choices, db_index=True)
    source_warehouse = models.ForeignKey(
        Warehouse, on_delete=models.SET_NULL, null=True, blank=True, related_name="outgoing_movements"
    )
    destination_warehouse = models.ForeignKey(
        Warehouse, on_delete=models.SET_NULL, null=True, blank=True, related_name="incoming_movements"
    )

    status = models.CharField(max_length=20, choices=MovementStatus.choices, default=MovementStatus.DRAFT,
                              db_index=True)
    note = models.TextField(blank=True, null=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   related_name="created_movements")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="approved_movements")
    created_at = models.DateTimeField(default=timezone.now)
    approved_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    processed = models.BooleanField(default=False,
                                    help_text="True when movement processed into inventory transactions and stock updated")

    class Meta:
        verbose_name = "Product Movement"
        verbose_name_plural = "Product Movements"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference_no} ({self.movement_type})"

    def clean(self):
        # basic business validation (raises ValidationError if invalid)
        if self.movement_type == MovementType.TRANSFER:
            if not (self.source_warehouse and self.destination_warehouse):
                raise ValidationError("Transfer must have both source and destination warehouses.")
            if self.source_warehouse == self.destination_warehouse:
                raise ValidationError("Source and destination warehouses must differ for transfer.")
        elif self.movement_type == MovementType.IN and not self.destination_warehouse:
            raise ValidationError("Inbound must have destination warehouse.")
        elif self.movement_type == MovementType.OUT and not self.source_warehouse:
            raise ValidationError("Outbound must have source warehouse.")

    @transaction.atomic
    def approve(self, user=None, run_async=False):
        """
        Move from DRAFT -> APPROVED and dispatch processing to MovementProcessor.
        Approve only changes state and records who approved; actual work is done by MovementProcessor.
        If run_async True, it's up to MovementProcessor to queue the job (Celery).
        """
        if self.status != MovementStatus.DRAFT:
            raise ValueError("Only DRAFT movements can be approved.")
        self.status = MovementStatus.APPROVED
        self.approved_by = user or self.approved_by
        self.approved_at = timezone.now()
        self.save(update_fields=['status', 'approved_by', 'approved_at'])

        # Dispatch to MovementProcessor (service) — it will handle idempotency and atomicity
        from .services.processor import MovementProcessor
        MovementProcessor.process(self, run_async=run_async)
        return self


class MovementSegment(models.Model):
    movement = models.ForeignKey(ProductMovement, on_delete=models.CASCADE, related_name="segments")
    sequence = models.PositiveIntegerField(default=0)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="movement_segments")
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit = models.CharField(max_length=50)

    from_warehouse = models.ForeignKey(
        Warehouse, on_delete=models.SET_NULL, null=True, blank=True, related_name="segment_outgoing"
    )
    to_warehouse = models.ForeignKey(
        Warehouse, on_delete=models.SET_NULL, null=True, blank=True, related_name="segment_incoming"
    )

    transport_mode = models.CharField(max_length=100, blank=True, null=True)
    carrier_name = models.CharField(max_length=255, blank=True, null=True)
    tracking_number = models.CharField(max_length=255, blank=True, null=True)
    departure_time = models.DateTimeField(blank=True, null=True)
    arrival_time = models.DateTimeField(blank=True, null=True)

    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)

    related_inventory_transactions = models.ManyToManyField('inventory_transaction_module.InventoryTransaction',
                                                            blank=True,
                                                            related_name='movement_segments')

    class Meta:
        verbose_name = "Movement Segment"
        verbose_name_plural = "Movement Segments"
        ordering = ['movement', 'sequence']

    def __str__(self):
        return f"{self.movement.reference_no} - {self.product.name} ({self.quantity} {self.unit})"

    def mark_processed(self, tx_list=None):
        self.processed = True
        self.processed_at = timezone.now()
        self.save(update_fields=['processed', 'processed_at'])
        if tx_list:
            self.related_inventory_transactions.add(*[t.pk for t in tx_list])


class MovementCost(models.Model):
    COST_TYPES = [
        ("VEHICLE_RENT", "Vehicle Rent"),
        ("DRIVER_FEE", "Driver Fee"),
        ("FUEL", "Fuel Cost"),
        ("INSURANCE", "Insurance"),
        ("CUSTOMS", "Customs Duty"),
        ("HANDLING", "Loading/Unloading"),
        ("OTHER", "Other"),
    ]

    segment = models.ForeignKey(MovementSegment, on_delete=models.CASCADE, related_name="costs")
    cost_type = models.CharField(max_length=50, choices=COST_TYPES)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Movement Cost"
        verbose_name_plural = "Movement Costs"

    def __str__(self):
        return f"{self.segment.id} - {self.get_cost_type_display()} - {self.amount}"
