from django.contrib import admin
from .models import ProductMovement, MovementSegment, MovementCost

# Register your models here.
admin.site.register(ProductMovement)
admin.site.register(MovementSegment)
admin.site.register(MovementCost)
