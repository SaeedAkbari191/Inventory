# # movement_module/services.py
# from django.db import transaction, IntegrityError
# from django.utils import timezone
# from decimal import Decimal
#
# from .models import ProductMovement, MovementSegment
# from inventory_transaction_module.models import InventoryTransaction
# from stock_module.models import Stock, StockLedger
# from product_module.models import ProductConversion
#
#
# # فرض: StockUpdater.apply(tx) وجود دارد و اتمیک بودن و select_for_update را در خودش انجام می‌دهد.
# # اگر ندارید، من تابع adjust stock را نیز می‌نویسم پایین.
#
# class MovementProcessor:
#     """
#     پردازش یک ProductMovement:
#     - برای هر segment، تولید InventoryTransactionها
#     - تبدیل واحدها (اگر لازم)
#     - ذخیره تراکنش‌ها
#     - اعمال روی Stock با قفل
#     - ایجاد رکوردهای StockLedger
#     - mark_processed برای segment و movement
#     """
#
#     @staticmethod
#     def convert_to_base(product, qty, unit):
#         """تبدیل qty از واحد داده شده به base_unit محصول (در صورت نیاز)."""
#         if not unit or unit == product.base_unit:
#             return qty
#         # پیدا کردن conversion مستقیم
#         conv = ProductConversion.objects.filter(product=product, from_unit=unit, to_unit=product.base_unit).first()
#         if conv:
#             return (Decimal(qty) * conv.factor).quantize(Decimal('0.0001'))
#         # اگر نبود، ممکنه conversion معکوس باشد یا چند مرحله‌ای — برای شروع فرض مستقیم
#         raise ValueError(f"No conversion found from {unit} to {product.base_unit} for product {product.pk}")
#
#     @staticmethod
#     def _create_and_apply_tx(tx):
#         """ذخیره InventoryTransaction و اعمال آن روی Stock و Ledger"""
#         tx.save()
#         # فرض: StockUpdater.apply(tx) موجود است. اگر نیست، از internal adjust استفاده کنید.
#         from inventory_transaction_module.services.stock_updater import StockUpdater
#         StockUpdater.apply(tx)  # idempotent و atomic درون خودش باشد
#         return tx
#
#     @classmethod
#     def process_movement(cls, movement: ProductMovement, run_async=False):
#         if movement.status != movement.MovementStatus.__class__ and movement.status != movement.status:
#             pass  # placeholder (we use business checks below)
#
#         # idempotency: اگر از قبل پردازش شده بود، برگرد
#         if movement.processed:
#             return []
#
#         # اکتیو کردن validation
#         movement.clean()
#
#         created_txs = []
#         # پردازش داخل یک تراکنش دیتابیسی
#         with transaction.atomic():
#             # Lock segments rows to avoid concurrent processing
#             segments = movement.segments.select_for_update().filter(processed=False).order_by('sequence')
#
#             for seg in segments:
#                 # تبدیل واحد به base_unit
#                 qty_in_base = cls.convert_to_base(seg.product, seg.quantity, seg.unit)
#
#                 # بسازیم لیست تراکنش‌ها بر اساس نوع حرکت (TRANSFER -> OUT + IN)
#                 if movement.movement_type == MovementType.OUT:
#                     tx = InventoryTransaction.objects.create(
#                         transaction_type='OUT',
#                         product=seg.product,
#                         quantity=qty_in_base,
#                         unit=seg.product.base_unit,
#                         source_warehouse=seg.from_warehouse or movement.source_warehouse,
#                         destination_warehouse=None,
#                         created_by=movement.approved_by,
#                     )
#                     cls._create_and_apply_tx(tx)
#                     created_txs.append(tx)
#
#                 elif movement.movement_type == MovementType.IN:
#                     tx = InventoryTransaction.objects.create(
#                         transaction_type='IN',
#                         product=seg.product,
#                         quantity=qty_in_base,
#                         unit=seg.product.base_unit,
#                         source_warehouse=None,
#                         destination_warehouse=seg.to_warehouse or movement.destination_warehouse,
#                         created_by=movement.approved_by,
#                     )
#                     cls._create_and_apply_tx(tx)
#                     created_txs.append(tx)
#
#                 elif movement.movement_type == MovementType.TRANSFER:
#                     out_tx = InventoryTransaction.objects.create(
#                         transaction_type='OUT',
#                         product=seg.product,
#                         quantity=qty_in_base,
#                         unit=seg.product.base_unit,
#                         source_warehouse=seg.from_warehouse or movement.source_warehouse,
#                         destination_warehouse=seg.to_warehouse or movement.destination_warehouse,
#                         created_by=movement.approved_by,
#                     )
#                     cls._create_and_apply_tx(out_tx)
#
#                     in_tx = InventoryTransaction.objects.create(
#                         transaction_type='IN',
#                         product=seg.product,
#                         quantity=qty_in_base,
#                         unit=seg.product.base_unit,
#                         source_warehouse=seg.from_warehouse or movement.source_warehouse,
#                         destination_warehouse=seg.to_warehouse or movement.destination_warehouse,
#                         created_by=movement.approved_by,
#                     )
#                     cls._create_and_apply_tx(in_tx)
#
#                     created_txs.extend([out_tx, in_tx])
#
#                 # لینک تراکنش‌ها به segment
#                 seg.related_inventory_transactions.add(
#                     *created_txs[-2:] if movement.movement_type == MovementType.TRANSFER else [created_txs[-1]])
#                 seg.processed = True
#                 seg.processed_at = timezone.now()
#                 seg.save(update_fields=['processed', 'processed_at'])
#
#             # همه‌ی segmentها پردازش شد؟
#             if movement.segments.filter(processed=False).exists():
#                 # هنوز segment ناتمامی هست — نمی‌خواهیم movement کامل علامتگذاری کنیم
#                 pass
#             else:
#                 movement.processed = True
#                 movement.completed_at = timezone.now()
#                 movement.status = MovementStatus.COMPLETED
#                 movement.save(update_fields=['processed', 'completed_at', 'status'])
#
#         return created_txs
