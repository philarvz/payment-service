# Payment Service API - Equipo 4

Microservicio de pagos para el ecosistema e-commerce orientado a servicios.

## Objetivo

Simular la pasarela de cobro del sistema y coordinarse con la API de Pedidos (Equipo 3):

1. Consulta el pedido para conocer el monto real a cobrar.
2. Procesa el pago (simulado).
3. Si el pago es exitoso, actualiza el pedido a estado `PAGADO`.

---

## Stack técnico

- Django
- Django REST Framework (DRF)
- `requests` para consumir APIs externas
- `drf-spectacular` para Swagger/OpenAPI
- MySQL (base de datos existente: `pagos`)

Formato de intercambio: **JSON**.

---

## Estructura del proyecto

```text
payment_service/
├── ecommerce/
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── payment_service/
│   ├── migrations/
│   │   └── 0001_initial.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── serializers.py
│   ├── services.py
│   ├── urls.py
│   └── views.py
├── .env.example
├── manage.py
├── requirements.txt
└── README.md
```

---

## Instalación y ejecución

### 1) Entrar al proyecto

```bash
cd /Users/pilih/Documents/proyecto-api/payment_service
```

### 2) Crear y activar entorno virtual (recomendado)

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3) Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4) Configurar variables de entorno

```bash
cp .env.example .env
```

Editar `.env`:

```env
SECRET_KEY=django-insecure-change-this-key
DEBUG=True

DB_NAME=pagos
DB_USER=root
DB_PASSWORD=
DB_HOST=localhost
DB_PORT=3306

ORDER_SERVICE_URL=http://localhost:8001
ORDER_SERVICE_TOKEN=
```

> `DB_NAME` debe apuntar a tu base MySQL ya existente: **pagos**.

### 5) Ejecutar migraciones

```bash
python manage.py migrate
```

### 6) Levantar servidor

```bash
python manage.py runserver 0.0.0.0:8003
```

Servicio disponible en:

- API: `http://localhost:8003`
- Swagger UI: `http://localhost:8003/api/schema/swagger-ui/`
- ReDoc: `http://localhost:8003/api/schema/redoc/`
- OpenAPI JSON: `http://localhost:8003/api/schema/`

---

## Endpoint principal

## POST `/api/payments/process/`

Procesa un cobro simulado.

### Request

```json
{
  "order_id": 10,
  "client_id": 42,
  "card_number": "4242424242424242",
  "expiry_date": "12/30",
  "cvv": "123"
}
```

### Validaciones

- `card_number`: debe pasar validación Luhn.
- `expiry_date`: formato `MM/YY` y no vencida.
- `cvv`: 3 o 4 dígitos.
- Antes de cobrar, consulta Order Service para obtener el total real.

### Respuestas posibles

#### 201 Created (pago aprobado y pedido actualizado)

```json
{
  "id": 1,
  "order_id": 10,
  "client_id": 42,
  "total": "1197.00",
  "card_last4": "4242",
  "card_expiry": "12/30",
  "status": "APPROVED",
  "transaction_reference": "PAY-20260413-AB12CD34EF",
  "response_message": "Transacción aprobada",
  "created_at": "2026-04-13T18:10:00.000000-06:00"
}
```

#### 202 Accepted (pago aprobado, pero falló actualización del pedido)

```json
{
  "id": 2,
  "order_id": 10,
  "client_id": 42,
  "total": "1197.00",
  "card_last4": "4242",
  "card_expiry": "12/30",
  "status": "APPROVED",
  "transaction_reference": "PAY-20260413-1234ABCD56",
  "response_message": "Transacción aprobada, pendiente de sincronizar estado del pedido",
  "created_at": "2026-04-13T18:12:00.000000-06:00"
}
```

#### 402 Payment Required (pago rechazado)

```json
{
  "id": 3,
  "order_id": 10,
  "client_id": 42,
  "total": "1197.00",
  "card_last4": "4242",
  "card_expiry": "12/30",
  "status": "DECLINED",
  "transaction_reference": "PAY-20260413-XY78ZT56MN",
  "response_message": "Transacción rechazada por el banco emisor",
  "created_at": "2026-04-13T18:15:00.000000-06:00"
}
```

#### 4xx / 5xx (error)

```json
{
  "error": "Mensaje descriptivo",
  "detail": "Detalle opcional",
  "service": "Order Service"
}
```

---

## Integración con Equipo 3 (Order Service)

Este servicio consume:

1. **GET** `/api/orders/{id}/` para obtener datos del pedido y calcular total.
2. **PATCH** `/api/orders/{id}/status/` para marcar pedido como pagado.

### Compatibilidad implementada

- Lee respuestas con forma directa o envueltas en `data`.
- Lee estado desde `estado` o `status`.
- Intenta actualizar estado con:
  - `{ "estado": "PAGADO" }`
  - fallback: `{ "status": "Pagado" }`

### Autenticación hacia Equipo 3

Si Order Service requiere Bearer token, configurar:

```env
ORDER_SERVICE_TOKEN=<token>
```

El header se enviará automáticamente como:

`Authorization: Bearer <token>`

---

## Reglas de simulación de pago

- Si `cvv` es `000` ⇒ pago rechazado.
- En cualquier otro caso válido ⇒ pago aprobado.

---

## Modelo de datos (tabla `payment_service_payment`)

- `id`
- `order_id`
- `client_id`
- `total`
- `card_last4`
- `card_expiry`
- `status` (`APPROVED` | `DECLINED`)
- `transaction_reference`
- `response_message`
- `created_at`
- `updated_at`

> No se almacenan número completo de tarjeta ni CVV.

---

## Prueba rápida con cURL

```bash
curl -X POST "http://localhost:8003/api/payments/process/" \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": 10,
    "client_id": 42,
    "card_number": "4242424242424242",
    "expiry_date": "12/30",
    "cvv": "123"
  }'
```

---

## Notas para otros equipos

- Consumir solo JSON.
- Revisar códigos HTTP (`201`, `202`, `402`, `409`, `503`).
- Integrar por contrato de endpoint y no por acceso a base de datos.
- Para desarrollo local en red, reemplazar `localhost` por IP local del equipo.
