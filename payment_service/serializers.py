from datetime import datetime
from rest_framework import serializers

from .models import Payment


class ProcessPaymentSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(min_value=1)
    client_id = serializers.IntegerField(min_value=1)
    card_number = serializers.CharField(min_length=13, max_length=19)
    expiry_date = serializers.CharField(max_length=5, help_text='Formato MM/YY')
    cvv = serializers.CharField(min_length=3, max_length=4, write_only=True)

    def validate_card_number(self, value):
        clean_value = value.replace(' ', '').replace('-', '')
        if not clean_value.isdigit():
            raise serializers.ValidationError('El número de tarjeta solo debe contener dígitos.')

        if not self._passes_luhn(clean_value):
            raise serializers.ValidationError('Número de tarjeta inválido.')

        return clean_value

    def validate_expiry_date(self, value):
        try:
            expiry = datetime.strptime(value, '%m/%y')
            now = datetime.now()
            expiry_month_end = datetime(expiry.year, expiry.month, 1)
            if expiry_month_end.year < now.year or (
                expiry_month_end.year == now.year and expiry_month_end.month < now.month
            ):
                raise serializers.ValidationError('La tarjeta está vencida.')
        except ValueError as exc:
            raise serializers.ValidationError('La fecha de expiración debe tener formato MM/YY.') from exc

        return value

    def validate_cvv(self, value):
        if not value.isdigit():
            raise serializers.ValidationError('El CVV solo debe contener dígitos.')
        return value

    @staticmethod
    def _passes_luhn(card_number):
        digits = [int(d) for d in card_number]
        checksum = 0
        parity = len(digits) % 2

        for i, digit in enumerate(digits):
            if i % 2 == parity:
                digit *= 2
                if digit > 9:
                    digit -= 9
            checksum += digit

        return checksum % 10 == 0


class PaymentResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            'id',
            'order_id',
            'client_id',
            'total',
            'card_last4',
            'card_expiry',
            'status',
            'transaction_reference',
            'response_message',
            'created_at',
        ]


class ErrorResponseSerializer(serializers.Serializer):
    error = serializers.CharField()
    detail = serializers.CharField(required=False)
    service = serializers.CharField(required=False)
