from decimal import Decimal
import logging

import requests
from django.conf import settings
from requests.exceptions import ConnectionError, RequestException, Timeout


logger = logging.getLogger('payment_service')


class ExternalServiceException(Exception):
    def __init__(self, message, status_code=None, service_name=None):
        self.message = message
        self.status_code = status_code
        self.service_name = service_name
        super().__init__(self.message)


class OrderServiceClient:
    """Cliente HTTP para consumir la API de Pedidos (Equipo 3)."""

    def __init__(self):
        self.base_url = settings.ORDER_SERVICE_URL.rstrip('/')
        self.timeout = 10

    def _headers(self):
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }
        if settings.ORDER_SERVICE_TOKEN:
            headers['Authorization'] = f"Bearer {settings.ORDER_SERVICE_TOKEN}"
        return headers

    def _unwrap_order_data(self, payload):
        if isinstance(payload, dict) and 'data' in payload and isinstance(payload['data'], dict):
            return payload['data']
        return payload

    def get_order(self, order_id):
        url = f"{self.base_url}/api/orders/{order_id}/"

        try:
            logger.info(f"Requesting order {order_id} from Order Service: {url}")
            response = requests.get(url, timeout=self.timeout, headers=self._headers())

            if response.status_code == 404:
                raise ExternalServiceException(
                    f"El pedido {order_id} no existe",
                    status_code=404,
                    service_name='Order Service',
                )

            if response.status_code != 200:
                raise ExternalServiceException(
                    f"Error al consultar el pedido: {response.status_code}",
                    status_code=response.status_code,
                    service_name='Order Service',
                )

            body = response.json()
            return self._unwrap_order_data(body)

        except Timeout:
            raise ExternalServiceException(
                'El servicio de pedidos no responde (timeout)',
                status_code=503,
                service_name='Order Service',
            )
        except ConnectionError:
            raise ExternalServiceException(
                'No se pudo conectar con el servicio de pedidos',
                status_code=503,
                service_name='Order Service',
            )
        except RequestException as exc:
            raise ExternalServiceException(
                f'Error al comunicarse con el servicio de pedidos: {str(exc)}',
                status_code=503,
                service_name='Order Service',
            )

    def update_order_status(self, order_id):
        url = f"{self.base_url}/api/orders/{order_id}/status/"

        payload_attempts = [
            {'estado': 'PAGADO'},
            {'status': 'Pagado'},
        ]

        last_status = None
        for payload in payload_attempts:
            try:
                logger.info(f"Updating order {order_id} status in Order Service")
                response = requests.patch(url, json=payload, timeout=self.timeout, headers=self._headers())
                last_status = response.status_code
                if response.status_code in (200, 204):
                    return response.json() if response.content else {}
            except RequestException:
                continue

        raise ExternalServiceException(
            f'No se pudo actualizar el estado del pedido (status: {last_status})',
            status_code=last_status or 503,
            service_name='Order Service',
        )

    @staticmethod
    def extract_total(order_data):
        if 'total' in order_data:
            return Decimal(str(order_data['total']))
        if 'monto_total' in order_data:
            return Decimal(str(order_data['monto_total']))
        if 'amount' in order_data:
            return Decimal(str(order_data['amount']))

        products = order_data.get('productos') or order_data.get('items') or []
        if not isinstance(products, list) or not products:
            raise ExternalServiceException(
                'No se pudo calcular el total del pedido.',
                status_code=400,
                service_name='Order Service',
            )

        total = Decimal('0.00')
        for product in products:
            quantity = Decimal(str(product.get('cantidad', product.get('quantity', 1))))
            unit_price = product.get('precio_unitario', product.get('price'))
            if unit_price is None:
                raise ExternalServiceException(
                    'Producto sin precio en la orden.',
                    status_code=400,
                    service_name='Order Service',
                )
            total += quantity * Decimal(str(unit_price))

        return total.quantize(Decimal('0.01'))
