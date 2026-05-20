import pika
import os
import time
import pickle

DLX_EXCHANGE = "sobel.dlx"
PEDAZOS_QUEUE = "sobel.pedazos"
DLQ_QUEUE = "sobel.dlq"


def conectar_con_backoff():
    """Retry con exponential backoff: 1s → 2s → 4s → 8s → ... → max 30s"""
    host = os.environ.get("RABBITMQ_HOST", "localhost")
    delay = 1
    max_delay = 30

    for intento in range(15):
        try:
            params = pika.ConnectionParameters(host=host, heartbeat=600)
            connection = pika.BlockingConnection(params)
            print(f"[DLQ] Conectado a RabbitMQ en {host}")
            return connection
        except Exception as e:
            print(f"[DLQ] Intento {intento + 1} fallido: {e}. Reintentando en {delay}s...")
            time.sleep(delay)
            delay = min(delay * 2, max_delay)

    raise Exception("No se pudo conectar a RabbitMQ después de 15 intentos")


def manejar_dlq(ch, method, properties, body):
    """
    Decide si reenviar el pedazo fallido a la cola principal o descartarlo.
    El header 'x-death' que agrega RabbitMQ indica cuántas veces ya fue a la DLQ.
    """
    try:
        data = pickle.loads(body)
        pedazo_id = data.get("pedazo_id", "desconocido")

        # RabbitMQ agrega x-death con el conteo de muertes
        x_death = (properties.headers or {}).get("x-death", [])
        retry_count = x_death[0].get("count", 0) if x_death else 0

        max_reintentos = int(os.environ.get("MAX_RETRIES", 3))

        print(f"[DLQ] Pedazo {pedazo_id} recibido. Muertes previas: {retry_count}/{max_reintentos}")

        if retry_count < max_reintentos:
            print(f"[DLQ] Reenviando pedazo {pedazo_id} a la cola principal...")
            ch.basic_publish(
                exchange="",
                routing_key=PEDAZOS_QUEUE,
                body=body,
                properties=pika.BasicProperties(delivery_mode=2)
            )
        else:
            print(f"[DLQ] Pedazo {pedazo_id} superó {max_reintentos} reintentos. Descartando definitivamente.")

        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print(f"[DLQ] Error manejando mensaje de DLQ: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def main():
    connection = conectar_con_backoff()
    channel = connection.channel()
    channel.basic_qos(prefetch_count=1)

    channel.exchange_declare(exchange=DLX_EXCHANGE, exchange_type="direct", durable=True)
    channel.queue_declare(queue=DLQ_QUEUE, durable=True)
    channel.queue_bind(queue=DLQ_QUEUE, exchange=DLX_EXCHANGE, routing_key=PEDAZOS_QUEUE)

    channel.basic_consume(
        queue=DLQ_QUEUE,
        on_message_callback=manejar_dlq,
        auto_ack=False
    )

    print("[DLQ] Consumidor de Dead Letter Queue activo. Esperando mensajes fallidos...")
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
        connection.close()


if __name__ == "__main__":
    main()
