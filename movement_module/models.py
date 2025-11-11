# movement_module/models.py
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
    reference_no = models.CharField(max_length=128, unique=True, blank=True, default="")
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
        # validate business rules before approving
        self.clean()

        # set approved state (atomic context not required here because process will use its own transaction)
        self.status = MovementStatus.APPROVED
        self.approved_by = user or self.approved_by
        self.approved_at = timezone.now()
        self.save(update_fields=['status', 'approved_by', 'approved_at'])

        # Dispatch to MovementProcessor (service) — it will handle idempotency and transaction atomicity.
        from .services.processor import MovementProcessor
        # Do not swallow exceptions: let caller/admin see why processing failed.
        MovementProcessor.process(self, run_async=run_async)
        return self

    def save(self, *args, **kwargs):
        # generate reference_no only when movement_type is present
        if not self.reference_no and self.movement_type:
            prefix_map = {
                'IN': 'MOV-IN',
                'OUT': 'MOV-OUT',
                'TRANSFER': 'MOV-TRF',
            }
            prefix = prefix_map.get(self.movement_type, 'MOV-UNK')

            last_movement = (
                ProductMovement.objects
                .filter(reference_no__startswith=prefix)
                .order_by('-id')
                .first()
            )
            if last_movement and '-' in last_movement.reference_no:
                try:
                    last_number = int(last_movement.reference_no.split('-')[-1])
                except Exception:
                    last_number = 0
            else:
                last_number = 0
            new_number = last_number + 1
            self.reference_no = f"{prefix}-{new_number:05d}"

        super().save(*args, **kwargs)


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

    def clean(self):
        # basic validation for each segment
        if self.quantity is None or self.quantity <= 0:
            raise ValidationError("Quantity must be a positive number.")
        # Check warehouse presence depending on movement type (segment-level fallback to movement-level)
        mtype = getattr(self.movement, "movement_type", None)
        if mtype == MovementType.OUT:
            if not (self.from_warehouse or self.movement.source_warehouse):
                raise ValidationError("Outbound segment must have a source warehouse (either segment or movement).")
        if mtype == MovementType.IN:
            if not (self.to_warehouse or self.movement.destination_warehouse):
                raise ValidationError("Inbound segment must have a destination warehouse (either segment or movement).")
        if mtype == MovementType.TRANSFER:
            src = self.from_warehouse or self.movement.source_warehouse
            dst = self.to_warehouse or self.movement.destination_warehouse
            if not (src and dst):
                raise ValidationError("Transfer segment must have both source and destination warehouses.")
            if src == dst:
                raise ValidationError("Source and destination warehouses must differ for transfer segments.")

    def save(self, *args, **kwargs):
        # auto-assign sequence if zero or not provided: next number within same movement
        if not self.sequence:
            last = MovementSegment.objects.filter(movement=self.movement).order_by('-sequence').first()
            self.sequence = 1 if not last else last.sequence + 1
        # run clean to ensure validation both in admin and programmatic creation
        self.clean()
        super().save(*args, **kwargs)

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
