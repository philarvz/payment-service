from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import OpenApiResponse, extend_schema
import logging

from .models import Payment
from .serializers import ErrorResponseSerializer, PaymentResponseSerializer, ProcessPaymentSerializer
from .services import ExternalServiceException, OrderServiceClient


logger = logging.getLogger('payment_service')


class ProcessPaymentView(APIView):
    """
    POST /api/payments/process/

    Recibe un pedido y datos simulados de tarjeta para procesar el cobro.
    """

    @extend_schema(
        request=ProcessPaymentSerializer,
        responses={
            201: OpenApiResponse(response=PaymentResponseSerializer, description='Pago aprobado y pedido actualizado a PAGADO'),
            202: OpenApiResponse(response=PaymentResponseSerializer, description='Pago aprobado, pero no se pudo actualizar el pedido'),
            400: OpenApiResponse(response=ErrorResponseSerializer, description='Datos inválidos'),
            402: OpenApiResponse(response=PaymentResponseSerializer, description='Pago rechazado'),
            404: OpenApiResponse(response=ErrorResponseSerializer, description='Pedido no encontrado'),
            409: OpenApiResponse(response=ErrorResponseSerializer, description='Conflicto de usuario o estado del pedido'),
            503: OpenApiResponse(response=ErrorResponseSerializer, description='Servicio externo no disponible'),
        },
        tags=['Payments'],
        description='Procesa un pago consultando el total real en Order Service y luego actualiza el estado del pedido a PAGADO.',
    )
    def post(self, request):
        serializer = ProcessPaymentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Datos inválidos', 'detail': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload = serializer.validated_data
        order_client = OrderServiceClient()

        try:
            order_data = order_client.get_order(payload['order_id'])

            order_user_id = (
                order_data.get('usuario_id')
                or order_data.get('user_id')
                or order_data.get('id_usuario')
                or order_data.get('client_id')
            )
            if order_user_id and int(order_user_id) != payload['client_id']:
                return Response(
                    {'error': 'El pedido no pertenece al cliente indicado.'},
                    status=status.HTTP_409_CONFLICT,
                )

            current_status = str(order_data.get('estado') or order_data.get('status') or '').upper()
            if current_status in ('PAGADO', 'PAID'):
                return Response(
                    {'error': 'El pedido ya se encuentra pagado.'},
                    status=status.HTTP_409_CONFLICT,
                )
            if current_status in ('ENVIADO', 'SHIPPED'):
                return Response(
                    {'error': 'El pedido ya fue enviado y no puede cobrarse.'},
                    status=status.HTTP_409_CONFLICT,
                )

            total = order_client.extract_total(order_data)
            approved = self._simulate_charge(payload['card_number'], payload['cvv'])

            payment = Payment.objects.create(
                order_id=payload['order_id'],
                client_id=payload['client_id'],
                total=total,
                card_last4=payload['card_number'][-4:],
                card_expiry=payload['expiry_date'],
                status='APPROVED' if approved else 'DECLINED',
                transaction_reference=Payment.generate_reference(),
                response_message='Transacción aprobada' if approved else 'Transacción rechazada por el banco emisor',
            )

            response_serializer = PaymentResponseSerializer(payment)

            if not approved:
                return Response(response_serializer.data, status=status.HTTP_402_PAYMENT_REQUIRED)

            try:
                order_client.update_order_status(payment.order_id)
            except ExternalServiceException as exc:
                logger.warning(f"Payment approved but order update failed: {exc.message}")
                payment.response_message = 'Transacción aprobada, pendiente de sincronizar estado del pedido'
                payment.save(update_fields=['response_message', 'updated_at'])
                return Response(PaymentResponseSerializer(payment).data, status=status.HTTP_202_ACCEPTED)

            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except ExternalServiceException as exc:
            return Response(
                {
                    'error': exc.message,
                    'service': exc.service_name,
                },
                status=exc.status_code or status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as exc:
            logger.error(f"Unexpected payment processing error: {str(exc)}", exc_info=True)
            return Response(
                {'error': 'Error interno del servidor', 'detail': str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @staticmethod
    def _simulate_charge(card_number, cvv):
        # Regla simple de simulación:
        # - CVV 000 => rechazo
        # - Cualquier otro CVV válido => aprobado
        if cvv == '000':
            return False
        return bool(card_number)
