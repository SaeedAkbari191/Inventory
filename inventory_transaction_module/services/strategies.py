from django.db import transaction
from stock_module.models import Stock, StockLedger


class BaseStrategy:
    """Base class for all stock update strategies."""

    def __init__(self, transaction_obj):
        self.tx = transaction_obj

    def execute(self):
        raise NotImplementedError("Each strategy must implement execute().")

    def _record_ledger(self, stock, change, user=None, note=None):
        """Create ledger entry for stock movement."""
        StockLedger.objects.create(
            stock=stock,
            transaction=self.tx,
            change=change,
            prev_quantity=stock.quantity,
            new_quantity=stock.quantity + change,
            created_by=user,
            note=note
        )


class InboundStrategy(BaseStrategy):
    """Handles inbound transactions (receiving goods into a warehouse)."""

    def execute(self):
        with transaction.atomic():
            stock, _ = Stock.objects.select_for_update().get_or_create(
                product=self.tx.product,
                warehouse=self.tx.destination_warehouse,
                defaults={'quantity': 0, 'unit': self.tx.unit}
            )
            prev_qty = stock.quantity
            stock.quantity += self.tx.quantity
            stock.save(update_fields=['quantity'])
            self._record_ledger(stock, self.tx.quantity, self.tx.created_by, "Inbound Transaction")


class OutboundStrategy(BaseStrategy):
    """Handles outbound transactions (shipping goods out of a warehouse)."""

    def execute(self):
        with transaction.atomic():
            stock = Stock.objects.select_for_update().get(
                product=self.tx.product,
                warehouse=self.tx.source_warehouse
            )
            if stock.quantity < self.tx.quantity:
                raise ValueError("Not enough stock to remove.")
            prev_qty = stock.quantity
            stock.quantity -= self.tx.quantity
            stock.save(update_fields=['quantity'])
            self._record_ledger(stock, -self.tx.quantity, self.tx.created_by, "Outbound Transaction")


class TransferStrategy(BaseStrategy):
    """Handles transfer between warehouses in one atomic operation."""

    def execute(self):
        with transaction.atomic():
            # Outbound (source)
            source_stock = Stock.objects.select_for_update().get_or_create(
                product=self.tx.product,
                warehouse=self.tx.source_warehouse,
                defaults={'quantity': 0, 'unit': self.tx.unit}
            )[0]
            if source_stock.quantity < self.tx.quantity:
                raise ValueError("Not enough stock to transfer.")

            # Inbound (destination)
            dest_stock, _ = Stock.objects.select_for_update().get_or_create(
                product=self.tx.product,
                warehouse=self.tx.destination_warehouse,
                defaults={'quantity': 0, 'unit': self.tx.unit}
            )

            # Adjust quantities
            source_stock.quantity -= self.tx.quantity
            dest_stock.quantity += self.tx.quantity

            source_stock.save(update_fields=['quantity'])
            dest_stock.save(update_fields=['quantity'])

            # Ledger entries
            self._record_ledger(source_stock, -self.tx.quantity, self.tx.created_by, "Transfer OUT")
            self._record_ledger(dest_stock, self.tx.quantity, self.tx.created_by, "Transfer IN")
