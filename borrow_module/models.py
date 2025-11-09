from decimal import Decimal
from django.db import models, transaction
from django.utils import timezone
from django.conf import settings

from product_module.models import Product
from location_module.models import Warehouse, Section, Shelf
from inventory_transaction_module.models import InventoryTransaction
from inventory_transaction_module.services.stock_updater import StockUpdater


class BorrowStatus(models.TextChoices):
    OUT = "OUT", "Out (Loaned)"
    RETURNED = "RETURNED", "Returned"
    OVERDUE = "OVERDUE", "Overdue"
    CANCELLED = "CANCELLED", "Cancelled"


class BorrowRecord(models.Model):
    """
    رکورد امانت (قرضی) — یک رکورد نشان می‌دهد چه کسی چه کالایی را از کجا برده، چه مقدار،
    کی باید برگردد و وضعیت بازگشت چگونه است.
    """
    reference_no = models.CharField(max_length=128, unique=True, null=True, blank=True)
    borrower = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="borrow_records")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="borrow_records")
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit = models.CharField(max_length=50)

    # از کدام انبار خارج شده (مبدأ)
    source_warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name="borrow_outgoing")
    source_section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name="borrow_outgoing_sections")
    source_shelf = models.ForeignKey(Shelf, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name="borrow_outgoing_shelves")

    # در صورت ثبت بازگشت، اینجا اطلاعات مقصد (معمولاً همان انبار مبدا)
    return_warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name="borrow_returns")
    return_section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name="borrow_return_sections")
    return_shelf = models.ForeignKey(Shelf, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name="borrow_return_shelves")

    status = models.CharField(max_length=20, choices=BorrowStatus.choices, default=BorrowStatus.OUT, db_index=True)

    issued_at = models.DateTimeField(default=timezone.now)
    expected_return_at = models.DateTimeField(null=True, blank=True)
    actual_returned_at = models.DateTimeField(null=True, blank=True)

    # لینک به تراکنش خروجی که هنگام صدور borrow ساخته می‌شود
    outgoing_tx = models.ForeignKey(InventoryTransaction, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="borrow_outgoing")
    # لینک به تراکنش ورودی که هنگام بازگشت ساخته می‌شود
    return_tx = models.ForeignKey(InventoryTransaction, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="borrow_return")

    note = models.TextField(blank=True, null=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="borrow_created_by")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Borrow Record"
        verbose_name_plural = "Borrow Records"
        ordering = ["-issued_at"]
        indexes = [
            models.Index(fields=['reference_no']),
            models.Index(fields=['borrower']),
        ]

    def __str__(self):
        return f"Borrow {self.reference_no or self.pk} | {self.product.name} x {self.quantity} ({self.status})"

    def clean(self):
        # ساده: اگر وضعیت OUT است باید source_warehouse داشته باشد
        if self.status == BorrowStatus.OUT and not self.source_warehouse:
            raise ValueError("Borrow must have a source_warehouse when issued.")

    @transaction.atomic
    def issue(self, user=None):
        """
        اجرا برای صدور امانت:
         - ایجاد یک InventoryTransaction نوع OUT (خروج از انبار)
         - فراخوانی StockUpdater.apply(tx) برای به‌روزرسانی stock
         - لینک tx به outgoing_tx و ذخیره رکورد
        """
        if self.outgoing_tx:
            # idempotency: اگر از قبل تراکنش خروجی وجود دارد از دوباره‌کاری جلوگیری کن
            return self.outgoing_tx

        self.clean()
        # تبدیل واحد به base_unit اگر لازم — استفاده از ProductConversion در StockUpdater/strategies انجام خواهد شد
        tx = InventoryTransaction.objects.create(
            transaction_type='OUT',
            product=self.product,
            quantity=self.quantity,
            unit=self.unit,
            source_warehouse=self.source_warehouse,
            source_section=self.source_section,
            source_shelf=self.source_shelf,
            destination_warehouse=None,
            created_by=user or self.created_by,
            reference_number=self.reference_no or f"BORR-{self.pk or 'TEMP'}",
            note=f"Borrow issued to {self.borrower}"
        )

        # apply stock change (StockUpdater idempotent باید باشد)
        StockUpdater.apply(tx)

        # لینک و ذخیره
        self.outgoing_tx = tx
        self.status = BorrowStatus.OUT
        self.created_by = self.created_by or user
        self.save(update_fields=['outgoing_tx', 'status', 'created_by'])
        return tx

    @transaction.atomic
    def mark_returned(self, user=None, returned_at=None, return_warehouse=None, return_section=None, return_shelf=None):
        """
        پردازش بازگشت کالا:
         - ایجاد یک InventoryTransaction نوع IN برای بازگشت
         - اجرای StockUpdater.apply برای اضافه کردن به موجودی
         - تنظیم وضعیت و تاریخ بازگشت
         - لینک return_tx
        """
        if self.status == BorrowStatus.RETURNED and self.return_tx:
            return self.return_tx

        # default برگرداندن به همان انبار مبدأ اگر مشخص نشده
        dest_wh = return_warehouse or self.return_warehouse or self.source_warehouse
        dest_sec = return_section or self.return_section or self.source_section
        dest_shelf = return_shelf or self.return_shelf or self.source_shelf

        tx = InventoryTransaction.objects.create(
            transaction_type='IN',
            product=self.product,
            quantity=self.quantity,
            unit=self.unit,
            source_warehouse=None,
            destination_warehouse=dest_wh,
            destination_section=dest_sec,
            destination_shelf=dest_shelf,
            created_by=user or self.created_by,
            reference_number=self.reference_no or f"BORR-{self.pk or 'TEMP'}-RET",
            note=f"Borrow returned by {self.borrower}"
        )

        StockUpdater.apply(tx)

        self.return_tx = tx
        self.status = BorrowStatus.RETURNED
        self.actual_returned_at = returned_at or timezone.now()
        self.save(update_fields=['return_tx', 'status', 'actual_returned_at'])
        return tx

    def cancel(self, user=None):
        """
        لغو رکورد امانی قبل از صدور (اگر outgoing_tx وجود نداشته باشد).
        """
        if self.outgoing_tx:
            raise ValueError("Cannot cancel borrow that already produced outgoing transaction.")
        self.status = BorrowStatus.CANCELLED
        self.save(update_fields=['status'])
