# Hit 4 — Observabilidad con Prometheus y Grafana

## Descripción

Stack de observabilidad para el sistema Sobel desplegado en GKE. Incluye recolección de métricas con Prometheus, visualización con Grafana y alertas configuradas mediante PrometheusRules.

## Componentes

| Componente | Descripción |
|---|---|
| `kube-prometheus-stack` | Chart de Helm que incluye Prometheus Operator, Grafana y Alertmanager |
| `ServiceMonitor` | Configura el scraping de métricas de los workers y centralizador |
| `PrometheusRule` | Define alertas sobre el estado del sistema |

## Instalación

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm install kube-prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace \
  -f hit4/helm/kube-prometheus-stack-values.yaml
```

## Acceso a Grafana

Grafana queda expuesto mediante un Service de tipo `LoadBalancer`. Para obtener la IP:

```bash
kubectl get svc -n monitoring kube-prometheus-grafana
```

Credenciales por defecto: `admin` / `admin123`.

## Dashboard

El dashboard **Sobel Workers** muestra:

| Panel | Métrica |
|---|---|
| Pedazos procesados | `sobel_pedazos_procesados_total` |
| Pedazos fallidos | `sobel_pedazos_fallidos_total` |
| Tiempo de procesamiento p95 | `sobel_tiempo_procesamiento_seconds` |

## Alertas configuradas

| Alerta | Condición |
|---|---|
| `WorkerDown` | Ningún worker disponible por más de 1 minuto |
| `HighErrorRate` | Tasa de pedazos fallidos superior al 10% |
| `QueueHigh` | Cola de pedazos con más de 100 mensajes |
| `DLQNotEmpty` | DLQ con mensajes pendientes |

## Configuración

- Prometheus y Grafana se despliegan en el nodo `infra-pool` mediante `nodeSelector: role=infra`.
- Retención de métricas: 15 días.
- El ServiceMonitor scrapeá los pods en el namespace `sobel` cada 15 segundos.
