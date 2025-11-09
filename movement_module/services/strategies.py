# movement_module/services/strategies.py
from decimal import Decimal
from django.utils import timezone
from django.db import transaction

from inventory_transaction_module.models import InventoryTransaction
from inventory_transaction_module.services.stock_updater import StockUpdater
from product_module.models import ProductConversion

# یک رجیستری ساده برای ثبت استراتژی‌ها
STRATEGY_REGISTRY = {}

def register_strategy(movement_type):
    def decorator(cls):
        STRATEGY_REGISTRY[movement_type] = cls()
        return cls
    return decorator

def get_strategy_for(movement_type):
    strategy = STRATEGY_REGISTRY.get(movement_type)
    if not strategy:
        raise ValueError(f"No movement strategy registered for '{movement_type}'")
    return strategy

class BaseMovementStrategy:
    """
    Interface: هر استراتژی باید متد process(movement) پیاده‌سازی کند.
    """
    def process(self, movement):
        raise NotImplementedError

    def convert_to_base(self, product, qty, unit):
        """
        تلاش برای تبدیل واحد به base_unit محصول؛ در صورت عدم وجود، خطا می‌اندازد.
        """
        if not unit or unit == getattr(product, 'base_unit', None):
            return Decimal(qty)
        conv = ProductConversion.objects.filter(product=product, from_unit=unit, to_unit=product.base_unit).first()
        if conv:
            return (Decimal(qty) * conv.factor).quantize(Decimal('0.0001'))
        # اگر conversion پیدا نشد، خطا بده — policy: باید conversion تعریف شود
        raise ValueError(f"No conversion from {unit} to {product.base_unit} for product {product.pk}")


@register_strategy('IN')
class InboundMovementStrategy(BaseMovementStrategy):
    """
    برای هر segment: ایجاد یک InventoryTransaction نوع IN (destination)، سپس StockUpdater.apply
    """
    def process(self, movement):
        created_txs = []
        # پردازش segmentها مستقل؛ هر segment یک یا چند تراکنش تولید می‌کند (معمولاً یک IN)
        for seg in movement.segments.select_for_update().filter(processed=False).order_by('sequence'):
            qty_base = self.convert_to_base(seg.product, seg.quantity, seg.unit)
            tx = InventoryTransaction(
                transaction_type='IN',
                product=seg.product,
                quantity=qty_base,
                unit=seg.product.base_unit,
                source_warehouse=None,
                destination_warehouse=seg.to_warehouse or movement.destination_warehouse,
                created_by=movement.approved_by,
                reference_number=movement.reference_no,
            )
            tx.save()
            StockUpdater.apply(tx)  # StockUpdater باید اتمیک و idempotent باشد
            created_txs.append(tx)
            seg.mark_processed(tx_list=[tx])
        return created_txs


@register_strategy('OUT')
class OutboundMovementStrategy(BaseMovementStrategy):
    """
    برای هر segment: ایجاد یک InventoryTransaction نوع OUT (source)، سپس StockUpdater.apply
    """
    def process(self, movement):
        created_txs = []
        for seg in movement.segments.select_for_update().filter(processed=False).order_by('sequence'):
            qty_base = self.convert_to_base(seg.product, seg.quantity, seg.unit)
            tx = InventoryTransaction(
                transaction_type='OUT',
                product=seg.product,
                quantity=qty_base,
                unit=seg.product.base_unit,
                source_warehouse=seg.from_warehouse or movement.source_warehouse,
                destination_warehouse=None,
                created_by=movement.approved_by,
                reference_number=movement.reference_no,
            )
            tx.save()
            StockUpdater.apply(tx)
            created_txs.append(tx)
            seg.mark_processed(tx_list=[tx])
        return created_txs


@register_strategy('TRANSFER')
class TransferMovementStrategy(BaseMovementStrategy):
    """
    برای هر segment: تولید دو تراکنش (OUT از مبدأ و IN به مقصد)، سپس apply هر دو.
    """
    def process(self, movement):
        created_txs = []
        for seg in movement.segments.select_for_update().filter(processed=False).order_by('sequence'):
            qty_base = self.convert_to_base(seg.product, seg.quantity, seg.unit)

            out_tx = InventoryTransaction(
                transaction_type='OUT',
                product=seg.product,
                quantity=qty_base,
                unit=seg.product.base_unit,
                source_warehouse=seg.from_warehouse or movement.source_warehouse,
                destination_warehouse=seg.to_warehouse or movement.destination_warehouse,
                created_by=movement.approved_by,
                reference_number=movement.reference_no,
            )
            out_tx.save()
            StockUpdater.apply(out_tx)

            in_tx = InventoryTransaction(
                transaction_type='IN',
                product=seg.product,
                quantity=qty_base,
                unit=seg.product.base_unit,
                source_warehouse=seg.from_warehouse or movement.source_warehouse,
                destination_warehouse=seg.to_warehouse or movement.destination_warehouse,
                created_by=movement.approved_by,
                reference_number=movement.reference_no,
            )
            in_tx.save()
            StockUpdater.apply(in_tx)

            created_txs.extend([out_tx, in_tx])
            seg.mark_processed(tx_list=[out_tx, in_tx])
        return created_txs
