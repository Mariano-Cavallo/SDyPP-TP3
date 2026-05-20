# Hit 2 — Workers en VMs GCE con Terraform

## Descripción

Aprovisionamiento de workers Sobel sobre máquinas virtuales de Google Compute Engine mediante Terraform. Cada VM levanta automáticamente un contenedor Docker al iniciar, conectándose a un servidor RabbitMQ externo para recibir y procesar fragmentos de imagen.

## Arquitectura

```
GitHub Actions → Terraform → GCE VMs (sobel-worker-0, sobel-worker-1)
                                  ↓
                          Docker (marianocavallo/sobel-worker)
                                  ↓
                          RabbitMQ (externo, configurable)
```

## Infraestructura

| Recurso | Descripción |
|---|---|
| `google_compute_network` | Red VPC dedicada para los workers |
| `google_compute_firewall` | SSH (configurable por CIDR) + puerto 8080 interno |
| `google_compute_instance` | 2 VMs `e2-medium` con Debian 12 |
| `google_service_account` | SA con permisos de logging |

## Variables principales

| Variable | Default | Descripción |
|---|---|---|
| `worker_count` | 2 | Cantidad de VMs a crear |
| `machine_type` | `e2-medium` | Tipo de máquina GCP |
| `docker_image` | `marianocavallo/sobel-worker:latest` | Imagen Docker del worker |
| `rabbitmq_host` | — | Host del servidor RabbitMQ (requerido) |
| `rabbitmq_port` | 5672 | Puerto AMQP |

## Despliegue

El despliegue se realiza automáticamente vía GitHub Actions (`terraform-apply.yml`) al realizar push con cambios en `hit2/terraform/`.

Requiere los siguientes secrets en el repositorio:
- `GCP_SA_KEY`: clave JSON de la cuenta de servicio GCP
- `GCP_PROJECT_ID`: ID del proyecto
- `TF_STATE_BUCKET`: bucket GCS para el estado de Terraform
- `RABBITMQ_HOST`: hostname o IP del servidor RabbitMQ externo

## Estado del Terraform

El estado se almacena en GCS: `sdpp-tp3-tfstate/hit2/state`.
