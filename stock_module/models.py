from django.db import models
from product_module.models import Product
from location_module.models import Warehouse, Section, Shelf


class Stock(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True)
    shelf = models.ForeignKey(Shelf, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit = models.CharField(max_length=50)

    class Meta:
        unique_together = ('product', 'warehouse', 'section', 'shelf')

    def __str__(self):
        return f"{self.product.name} - {self.warehouse.name}: {self.quantity} {self.unit}"

    def increase(self, qty):
        self.quantity += qty
        self.save(update_fields=['quantity'])

    def decrease(self, qty):
        self.quantity -= qty
        self.save(update_fields=['quantity'])
