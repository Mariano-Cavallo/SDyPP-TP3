# TP0 - Patrones de Mensajería con RabbitMQ

Este proyecto implementa y demuestra 4 patrones de mensajería utilizando RabbitMQ.
## Estructura del Proyecto

```
hit0/
├── patron1-message-queue/     # Patrón 1: Cola de Mensajes (Point-to-Point)
├── patron2-pubsub-fanout/     # Patrón 2: Publicación/Suscripción (Fanout)
├── patron3-dlq/               # Patrón 3: Dead Letter Queue
└── patron4-retry-backoff/     # Patrón 4: Reintentos con Backoff Exponencial
```

## Requisitos

- Docker
- Docker Compose

## Cómo ejecutar los servicios

Cada patrón tiene su propio `docker-compose.yml`. Para ejecutar cada servicio:

### Patrón 1: Message Queue

```bash
cd patron1-message-queue
docker compose up --build
```

**Servicios:** RabbitMQ, Producer, Consumer

### Patrón 2: Pub/Sub Fanout

```bash
cd patron2-pubsub-fanout
docker compose up --build
```

**Servicios:** RabbitMQ, Producer, Consumer (pueden levantarse múltiples consumers)

### Patrón 3: Dead Letter Queue

```bash
cd patron3-dlq
docker compose up --build
```

**Servicios:** RabbitMQ, Producer, Consumer, ConsumerDLQ

### Patrón 4: Retry with Backoff

```bash
cd patron4-retry-backoff
docker compose up --build
```

**Servicios:** RabbitMQ, Producer, Consumer, ConsumerDLQ

## Diagramas de Arquitectura

### Patrón 1: Message Queue (Cola de Mensajes)

```
┌──────────┐     publish      ┌──────────┐     consume     ┌──────────┐
│ Producer │ ───────────────► │          │ ───────────────► │ Consumer │
└──────────┘                  │  Queue   │                  └──────────┘
                              │          │     consume     ┌──────────┐
                              └──────────┘ ───────────────► │ Consumer │
                                                     │      └──────────┘
                                                     │      ┌──────────┐
                                                     └─────►│ Consumer │
                                                            └──────────┘
```

**Características:**
- Comunicación punto a punto (un mensaje va a un solo consumer)
- Múltiples consumers pueden consumir de la misma cola (competing consumers)
- La cola distribuye los mensajes entre los consumers disponibles
- La cola almacena los mensajes hasta ser procesados

---

### Patrón 2: Pub/Sub Fanout (Publicación/Suscripción)

```
┌──────────┐                    ┌──────────────┐
│ Producer │                    │   Exchange   │
└──────────┘                    │   (Fanout)   │
      │ publish                 └──────────────┘
      ▼                          │             │
┌──────────┐               ┌─────┴─────┐ ┌─────┴─────┐
│ RabbitMQ │               │  Queue 1  │ │  Queue 2  │
└──────────┘               └─────┬─────┘ └─────┬─────┘
                                 │             │
                                 ▼             ▼
                           ┌──────────┐   ┌──────────┐
                           │ Consumer │   │ Consumer │
                           │    1     │   │    2     │
                           └──────────┘   └──────────┘
```

**Características:**
- Un mensaje se envía a múltiples consumers
- El exchange fanout broadcasta a todas las colas vinculadas
- Cada consumer tiene su propia cola exclusiva

---

### Patrón 3: Dead Letter Queue (Cola de Mensajes Muertos)

```
┌──────────┐     publish      ┌──────────┐     consume     ┌──────────┐
│ Producer │ ───────────────► │          │ ───────────────► │ Consumer │
└──────────┘                  │  Queue   │                  └──────────┘
                              │          │     consume     ┌──────────┐
                              └──────────┘ ───────────────► │ Consumer │
                                                     │      └──────────┘
                                   nack               │      ┌──────────┐
                                   (requeue=False)    └─────►│ Consumer │
                                                            └──────────┘
                                   ▼
                             ┌──────────┐
                             │   DLX    │
                             │ (Exchange)│
                             └────┬─────┘
                                  │
                                  ▼
                            ┌──────────┐     consume     ┌──────────┐
                            │   DLQ    │ ───────────────► │Consumer  │
                            │ (errores)│                  │   DLQ    │
                            └──────────┘                  └──────────┘
```
┌──────────┐     publish      ┌──────────┐     consume      ┌──────────┐
│ Producer │ ───────────────► │  Queue   │ ───────────────► │ Consumer │
└──────────┘                  └──────────┘                  └────┬─────┘
                                   │                             │
                                   │ nack (requeue=False)        │
                                   ▼                             │
                             ┌──────────┐                        │
                             │   DLX    │ ◄──────────────────────┘
                             │(Exchange)│
                             └────┬─────┘
                                  │
                                  ▼
                            ┌──────────┐     consume      ┌──────────┐
                            │   DLQ    │ ───────────────► │ Consumer │
                            │ (errores)│                  │   DLQ    │
                            └──────────┘                  └──────────┘
```

**Características:**
- Los mensajes que fallan se envían a una cola de errores (DLQ)
- Utiliza un Dead Letter Exchange (DLX) para redirigir mensajes
- Permite aislar y analizar mensajes problemáticos

---

### Patrón 4: Retry with Backoff (Reintentos con Retroceso)

```
┌──────────┐     publish      ┌──────────┐     consume     ┌──────────┐
│ Producer │ ───────────────► │          │ ───────────────► │ Consumer │
└──────────┘                  │  Queue   │                  └──────────┘
                              │          │     consume     ┌──────────┐
                              └──────────┘ ───────────────► │ Consumer │
                                                     │      └──────────┘
                                   ▲                  │      ┌──────────┐
                                   │                  └─────►│ Consumer │
                                   │                         └──────────┘
                                   │ retry < max
                                   │ (con delay)
                                   ▼
                             ┌──────────┐                  ┌──────────┐
                             │   DLX    │                  │ Retry    │
                             │ (Exchange)│◄────────────────│  Queue   │
                             └────┬─────┘                  └──────────┘
                                  │
                                  │ retry >= max
                                  ▼
                            ┌──────────┐     consume     ┌──────────┐
                            │   DLQ    │ ───────────────► │Consumer  │
                            │ (errores)│                  │   DLQ    │
                            └──────────┘                  └──────────┘
```
┌──────────┐     publish      ┌──────────┐     consume      ┌──────────┐
│ Producer │ ───────────────► │  Queue   │ ───────────────► │ Consumer │
└──────────┘                  └──────────┘                  └────┬─────┘
                                   ▲                             │
                                   │                             │ retry < max
                                   │                             │ (con delay)
                                   │                             ▼
                             ┌──────────┐                  ┌──────────┐
                             │   DLX    │                  │  Retry   │
                             │(Exchange)│◄──────────────── │  Queue   │
                             └────┬─────┘                  └──────────┘
                                  │
                                  │ retry >= max
                                  ▼
                            ┌──────────┐     consume      ┌──────────┐
                            │   DLQ    │ ───────────────► │ Consumer │
                            │(errores) │                  │   DLQ    │
                            └──────────┘                  └──────────┘
```

**Características:**
- Reintenta procesar mensajes fallidos con backoff exponencial
- Delay: 2^(retry-1) * 1000 ms
- Máximo 4 reintentos antes de enviar a DLQ
- Utiliza colas con TTL para el retraso

---

## Diferencias entre los Patrones

| Característica | Patrón 1: Message Queue | Patrón 2: Pub/Sub Fanout | Patrón 3: DLQ | Patrón 4: Retry Backoff |
|----------------|-------------------------|--------------------------|---------------|-------------------------|
| **Tipo de comunicación** | Punto a punto (competing consumers) | Broadcast (uno a muchos) | Punto a punto (competing consumers) | Punto a punto (competing consumers) |
| **Destinatarios** | Múltiples consumers compiten por mensajes | Múltiples consumers (cada uno recibe todos los mensajes) | Múltiples consumers compiten por mensajes | Múltiples consumers compiten por mensajes |
| **Manejo de errores** | No (requeue simple) | No (requeue simple) | Sí (envía a DLQ) | Sí (reintenta + DLQ) |
| **Reintentos** | No | No | No | Sí (con backoff exponencial) |
| **Dead Letter Queue** | No | No | Sí | Sí |
| **Exchange utilizado** | Direct (vacío) | Fanout | Direct + DLX | Direct + DLX |
| **Persistencia de errores** | No | No | Sí (en DLQ) | Sí (en DLQ) |

---

## ¿Cuándo usar cada patrón?

### Patrón 1: Message Queue
**Usar cuando:**
- Necesitas comunicación punto a punto simple
- El orden de procesamiento no es crítico
- Un mensaje debe ser procesado por exactamente un consumer
- Tareas de procesamiento asíncrono básico

**Ejemplo:** Procesamiento de pedidos, envío de emails transaccionales

---

### Patrón 2: Pub/Sub Fanout
**Usar cuando:**
- Necesitas notificar a múltiples servicios sobre un evento
- El productor no necesita saber quiénes consumen el mensaje
- Replicación de datos o eventos de dominio
- Notificaciones en tiempo real a múltiples sistemas

**Ejemplo:** Notificar cambios de estado a varios microservicios, actualizar cachés distribuidas, eventos de auditoría

---

### Patrón 3: Dead Letter Queue
**Usar cuando:**
- Necesitas auditabilidad de mensajes fallidos
- Los mensajes erróneos no deben perderse
- Quieres separar el procesamiento normal del manejo de errores
- Necesitas analizar por qué fallan ciertos mensajes

**Ejemplo:** Procesamiento de pagos fallidos, validación de datos, integración con sistemas externos propensos a errores

---

### Patrón 4: Retry with Backoff
**Usar cuando:**
- Los fallos son transitorios (ej. timeout de red, servicio temporalmente no disponible)
- Necesitas resiliencia ante fallos temporales
- Quieres evitar sobrecargar el sistema con reintentos inmediatos
- Tienes una API o servicio externo que puede fallar intermitentemente

**Ejemplo:** Llamadas a APIs externas, procesamiento de imágenes (este TP), conexiones a bases de datos temporales

---

## Procesamiento Distribuido de Imágenes (Hits Siguientes)

Estos patrones servirán como base para el procesamiento distribuido de imágenes:

- **Message Queue**: Distribuir tareas de procesamiento de imágenes entre workers
- **Pub/Sub**: Notificar a múltiples servicios cuando una imagen está lista
- **DLQ**: Manejar imágenes corruptas o formatos no soportados
- **Retry Backoff**: Reintentar procesamiento ante fallos temporales de almacenamiento o red

---

## Acceso a RabbitMQ Management

Para todos los patrones, el panel de administración de RabbitMQ está disponible en:

```
http://localhost:15672
```

Credenciales por defecto: `guest` / `guest`
