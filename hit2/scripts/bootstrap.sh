#!/bin/bash
# bootstrap.sh — ejecutado automáticamente al arrancar la VM

set -euo pipefail
LOG=/var/log/sobel.log
exec >> $LOG 2>&1

echo "[$(date)] === Bootstrap worker-${worker_index} iniciando ==="

# ── 1. Instalar Docker ──
apt-get update -y
apt-get install -y docker.io

systemctl start docker
systemctl enable docker

# ── 2. Bajar imagen ──
docker pull ${docker_image}

# ── 3. Correr el contenedor como servicio (restart automático si falla) ──
docker run -d \
  --name sobel-worker-${worker_index} \
  --restart unless-stopped \
  -e RABBITMQ_HOST="${rabbitmq_host}" \
  -e RABBITMQ_PORT="${rabbitmq_port}" \
  -e WORKER_ID="${worker_index}" \
  ${docker_image}

echo "[$(date)] === Worker-${worker_index} desplegado ==="