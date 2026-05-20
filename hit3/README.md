# Hit 3 — Procesamiento distribuido en GKE con RabbitMQ

## Descripción

Migración del sistema de procesamiento de imágenes Sobel a Google Kubernetes Engine. Se implementan patrones avanzados de mensajería con RabbitMQ: Dead Letter Exchange (DLX), Dead Letter Queue (DLQ), reintentos con backoff exponencial y notificaciones pub/sub mediante fanout exchange.

## Arquitectura

```
Centralizador → [sobel.pedazos] → Workers (x4)
                                       ↓ (error)
                               [sobel.dlx] → [sobel.dlq] → DLQ Consumer
                                       ↓ (éxito)
                               [sobel.resultados] → Centralizador
                               [sobel.notifications fanout] → suscriptores
```

## Componentes

| Componente | Replicas | Descripción |
|---|---|---|
| `worker` | 4 | Aplica filtro Sobel a fragmentos de imagen |
| `centralizador` | 1 | Divide imagen, distribuye fragmentos y ensambla resultado |
| `dlq-consumer` | 1 | Reintenta mensajes fallidos hasta MAX_RETRIES veces |
| `rabbitmq` | 1 | Broker de mensajes (StatefulSet) |

## Patrones implementados

- **DLX / DLQ**: los mensajes que fallan son enviados automáticamente a `sobel.dlq` mediante el dead letter exchange `sobel.dlx`.
- **Reintentos con backoff exponencial**: los workers y el centralizador reintentan la conexión a RabbitMQ con delays crecientes (1s → 2s → 4s → ... → 30s).
- **Pub/Sub (fanout)**: al completar el procesamiento, el centralizador publica una notificación en el exchange `sobel.notifications` para todos los suscriptores interesados.

## Infraestructura (Terraform)

Cluster GKE en `us-central1` con dos node pools:

| Pool | Nodos | Rol |
|---|---|---|
| `infra-pool` | 1 × `e2-medium` | RabbitMQ, Prometheus, Grafana |
| `app-pool` | 1 × `e2-medium` | Workers, centralizador, dlq-consumer |

Estado almacenado en GCS: `sdpp-tp3-tfstate/hit3/state`.

## Métricas expuestas (Prometheus)

| Métrica | Tipo | Descripción |
|---|---|---|
| `sobel_pedazos_procesados_total` | Counter | Pedazos procesados exitosamente |
| `sobel_pedazos_fallidos_total` | Counter | Pedazos que fallaron |
| `sobel_tiempo_procesamiento_seconds` | Histogram | Tiempo de procesamiento por pedazo |
| `sobel_centralizador_pedazos_publicados_total` | Counter | Pedazos enviados a workers |
| `sobel_centralizador_pedazos_pendientes` | Gauge | Pedazos sin resultado aún |

## CI/CD

El pipeline `deploy-gke.yml` se activa automáticamente al hacer push con cambios en `hit3/`. Construye las imágenes Docker, las publica en Artifact Registry y aplica los manifests de Kubernetes.
