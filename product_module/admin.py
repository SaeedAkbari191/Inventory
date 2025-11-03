from django.contrib import admin

from product_module.models import Product, ProductConversion, Brand, Category, Supplier

# Register your models here.

admin.site.register(Brand)
admin.site.register(Category)
admin.site.register(Product)
admin.site.register(ProductConversion)
admin.site.register(Supplier)
