#!/bin/bash
set -euo pipefail
LOG=/var/log/rabbitmq.log
exec >> $LOG 2>&1

echo "[$(date)] === Bootstrap RabbitMQ iniciando ==="

apt-get update -y
apt-get install -y docker.io

systemctl start docker
systemctl enable docker

docker run -d \
  --name rabbitmq \
  --restart unless-stopped \
  -p 5672:5672 \
  -p 15672:15672 \
  -e RABBITMQ_SERVER_ADDITIONAL_ERL_ARGS="-rabbit loopback_users []" \
  rabbitmq:3.13-management

echo "[$(date)] === RabbitMQ desplegado ==="
