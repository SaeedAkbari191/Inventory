from .strategies import InboundStrategy, OutboundStrategy, TransferStrategy


class StockUpdater:
    """High-level manager that applies stock update strategies dynamically."""

    STRATEGY_MAP = {
        'IN': InboundStrategy,
        'OUT': OutboundStrategy,
        'TRANSFER': TransferStrategy,
    }

    @classmethod
    def apply(cls, transaction_obj):
        """Apply the right stock update strategy based on transaction type."""
        strategy_class = cls.STRATEGY_MAP.get(transaction_obj.transaction_type)
        if not strategy_class:
            raise ValueError(f"Unsupported transaction type: {transaction_obj.transaction_type}")
        strategy = strategy_class(transaction_obj)
        strategy.execute()
