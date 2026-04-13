from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'order_id', 'client_id', 'total', 'status', 'transaction_reference', 'created_at')
    search_fields = ('transaction_reference', 'order_id', 'client_id')
    list_filter = ('status', 'created_at')
