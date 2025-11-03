from django.db import models


# Create your models here.
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

class Product(models.Model):
    name = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.CASCADE ,related_name='products')
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE ,related_name='products')
    sku = models.CharField(max_length=100 , unique=True)
    base_unit=models.CharField(max_length=100)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class ProductConversion(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE ,related_name='conversions')
    from_unit=models.CharField(max_length=100)
    to_unit=models.CharField(max_length=100)
    factor=models.DecimalField(max_digits=12, decimal_places=4)

    def __str__(self):
        return f'{self.product.name}: {self.from_unit}-> {self.to_unit} '
