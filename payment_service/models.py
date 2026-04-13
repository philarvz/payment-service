from django.db import models
from django.utils import timezone
import uuid


class Payment(models.Model):
    STATUS_CHOICES = [
        ('APPROVED', 'Aprobado'),
        ('DECLINED', 'Rechazado'),
    ]

    order_id = models.IntegerField(db_index=True)
    client_id = models.IntegerField(db_index=True)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    card_last4 = models.CharField(max_length=4)
    card_expiry = models.CharField(max_length=5)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    transaction_reference = models.CharField(max_length=40, unique=True, db_index=True)
    response_message = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment {self.transaction_reference} - Order {self.order_id}"

    @staticmethod
    def generate_reference():
        date_part = timezone.now().strftime('%Y%m%d')
        random_part = uuid.uuid4().hex[:10].upper()
        return f"PAY-{date_part}-{random_part}"
