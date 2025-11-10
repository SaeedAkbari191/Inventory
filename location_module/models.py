from django.db import models
from user_module.models import User


class Warehouse(models.Model):
    name = models.CharField(max_length=200, unique=True, verbose_name="Warehouse Name")
    code = models.CharField(max_length=50, unique=True, verbose_name="Code")
    address = models.TextField(blank=True, null=True, verbose_name="Address")
    manager = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="managed_warehouses"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Warehouse"
        verbose_name_plural = "Warehouses"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def save(self, *args, **kwargs):
        if not self.code:
            last = Warehouse.objects.order_by("-id").first()
            next_id = 1 if not last else last.id + 1
            self.code = f"WH-{next_id:04d}"
        super().save(*args, **kwargs)


class Section(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="sections")
    name = models.CharField(max_length=100, verbose_name="Section Name")
    code = models.CharField(max_length=50, verbose_name="Code")

    class Meta:
        verbose_name = "Section"
        verbose_name_plural = "Sections"
        unique_together = ("warehouse", "code")
        ordering = ["warehouse", "name"]

    def __str__(self):
        return f"{self.warehouse.name} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.code:
            last_section = Section.objects.filter(warehouse=self.warehouse).order_by("-id").first()
            next_number = 1 if not last_section else last_section.id + 1
            self.code = f"SEC-{next_number:02d}"
        super().save(*args, **kwargs)


class Shelf(models.Model):
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="shelves")
    name = models.CharField(max_length=100, verbose_name="Shelf Name")
    code = models.CharField(max_length=50, verbose_name="Code")
    description = models.TextField(blank=True, null=True, verbose_name="Description")

    class Meta:
        verbose_name = "Shelf"
        verbose_name_plural = "Shelves"
        unique_together = ("section", "code")
        ordering = ["section", "name"]

    def __str__(self):
        return f"{self.section.warehouse.name} - {self.section.name} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.code:
            last_shelf = Shelf.objects.filter(section=self.section).order_by("-id").first()
            next_number = 1 if not last_shelf else last_shelf.id + 1
            self.code = f"SH-{next_number:02d}"
        super().save(*args, **kwargs)
