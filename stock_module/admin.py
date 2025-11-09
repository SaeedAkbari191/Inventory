from django.contrib import admin

from stock_module.models import Stock, StockLedger

# Register your models here.


admin.site.register(Stock)
admin.site.register(StockLedger)
