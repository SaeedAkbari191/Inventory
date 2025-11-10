from django.db import models
from user_module.models import User
from django.db.models import Max


class Warehouse(models.Model):
    name = models.CharField(max_length=200, unique=True, verbose_name="Warehouse Name")
    code = models.CharField(max_length=50, unique=True, verbose_name="Code", blank=True, null=False, default="")
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
            last_code = (
                    Warehouse.objects.aggregate(max_num=models.Max("id")).get("max_num") or 0
            )
            next_number = last_code + 1
            self.code = f"WH-{next_number:04d}"
        super().save(*args, **kwargs)


class Section(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="sections")
    name = models.CharField(max_length=100, verbose_name="Section Name")
    code = models.CharField(max_length=50, verbose_name="Code", blank=True, null=False, default="")

    class Meta:
        verbose_name = "Section"
        verbose_name_plural = "Sections"
        unique_together = ("warehouse", "code")
        constraints = [
            models.UniqueConstraint(fields=['warehouse', 'name'], name='unique_section_name_per_warehouse')
        ]
        ordering = ["warehouse", "name"]

    def __str__(self):
        return f"{self.warehouse.name} - {self.name} {self.code}"

    def save(self, *args, **kwargs):
        if not self.code:
            last_section = (
                    Section.objects.filter(warehouse=self.warehouse).aggregate(max_id=Max("id")).get("max_id") or 0)
            next_num = last_section + 1
            self.code = f"SEC-{self.warehouse.code}-{next_num:02d}"
        super().save(*args, **kwargs)


class Shelf(models.Model):
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="shelves")
    name = models.CharField(max_length=100, verbose_name="Shelf Name")
    code = models.CharField(max_length=50, verbose_name="Code", blank=True, null=False, default="")
    description = models.TextField(blank=True, null=True, verbose_name="Description")

    class Meta:
        verbose_name = "Shelf"
        verbose_name_plural = "Shelves"
        unique_together = ("section", "code")
        ordering = ["section", "name"]
        constraints = [
            models.UniqueConstraint(fields=['section', 'name'], name='unique_shelf_name_per_section')
        ]

    def __str__(self):
        return f"{self.section.warehouse.name} - {self.section.name} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.code:
            last_shelf = (
                    Shelf.objects.filter(section=self.section)
                    .aggregate(max_id=Max("id"))
                    .get("max_id") or 0
            )
            next_num = last_shelf + 1
            self.code = f"SH-{self.section.warehouse.code}-{self.section.code.split('-')[-1]}-{next_num:02d}"
        super().save(*args, **kwargs)
