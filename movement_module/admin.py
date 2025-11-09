# movement_module/admin.py
from django.contrib import admin
from .models import ProductMovement, MovementSegment, MovementCost


class MovementSegmentInline(admin.TabularInline):
    model = MovementSegment
    extra = 1


class MovementCostInline(admin.TabularInline):
    model = MovementCost
    extra = 0


@admin.register(ProductMovement)
class ProductMovementAdmin(admin.ModelAdmin):
    list_display = ('reference_no', 'movement_type', 'status', 'created_at', 'processed')
    inlines = [MovementSegmentInline]
    actions = ['approve_selected']

    def approve_selected(self, request, queryset):
        for mov in queryset.filter(status='DRAFT'):
            mov.approve(user=request.user, run_async=False)

    approve_selected.short_description = "Approve selected movements"


@admin.register(MovementSegment)
class MovementSegmentAdmin(admin.ModelAdmin):
    list_display = ('movement', 'product', 'quantity', 'processed')
    inlines = [MovementCostInline]


@admin.register(MovementCost)
class MovementCostAdmin(admin.ModelAdmin):
    list_display = ('segment', 'cost_type', 'amount', 'created_at')
