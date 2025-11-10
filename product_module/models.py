from django.db import models
import uuid
from django.utils.text import slugify


class Supplier(models.Model):
    name = models.CharField(max_length=200, unique=True, verbose_name="Name")
    contact_info = models.TextField(blank=True, null=True, verbose_name="Contact Info")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")

    class Meta:
        verbose_name = "Supplier"
        verbose_name_plural = "Suppliers"

    def __str__(self):
        return self.name


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
    name = models.CharField(max_length=255, unique=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, related_name='products', null=True, blank=True)
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='products')
    sku = models.CharField(default="", null=False, blank=True, max_length=100, unique=True)
    slug = models.SlugField(default="", null=False, blank=True, max_length=200, unique=True, db_index=True)
    base_unit = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.sku:
            self.sku = f"PRD-{uuid.uuid4().hex[:8].upper()}"
        self.slug = slugify(self.name)

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"
        ordering = ['name']


class ProductConversion(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='conversions')
    from_unit = models.CharField(max_length=100)
    to_unit = models.CharField(max_length=100)
    factor = models.DecimalField(max_digits=12, decimal_places=4)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Product Conversion"
        verbose_name_plural = "Product Conversions"
        unique_together = ('product', 'from_unit', 'to_unit')

    def __str__(self):
        return f"{self.product.name}: 1 {self.from_unit} = {self.factor} {self.to_unit}"
