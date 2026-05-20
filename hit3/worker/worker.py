import pika
import os
import time
import pickle
import numpy as np
import io
from prometheus_client import Counter, Histogram, start_http_server

PEDAZOS_PROCESADOS = Counter("sobel_pedazos_procesados_total", "Total de pedazos procesados exitosamente")
PEDAZOS_FALLIDOS = Counter("sobel_pedazos_fallidos_total", "Total de pedazos que fallaron")
TIEMPO_PROCESAMIENTO = Histogram("sobel_tiempo_procesamiento_seconds", "Tiempo de procesamiento por pedazo")

DLX_EXCHANGE = "sobel.dlx"
NOTIFICATIONS_EXCHANGE = "sobel.notifications"
PEDAZOS_QUEUE = "sobel.pedazos"
RESULTADOS_QUEUE = "sobel.resultados"
DLQ_QUEUE = "sobel.dlq"


def conectar_con_backoff():
    """Retry con exponential backoff: 1s → 2s → 4s → 8s → ... → max 30s"""
    host = os.environ.get("RABBITMQ_HOST", "localhost")
    delay = 1
    max_delay = 30

    for intento in range(15):
        try:
            params = pika.ConnectionParameters(
                host=host,
                heartbeat=600,
                blocked_connection_timeout=300
            )
            connection = pika.BlockingConnection(params)
            print(f"[Worker] Conectado a RabbitMQ en {host}")
            return connection
        except Exception as e:
            print(f"[Worker] Intento {intento + 1} fallido: {e}. Reintentando en {delay}s...")
            time.sleep(delay)
            delay = min(delay * 2, max_delay)

    raise Exception("No se pudo conectar a RabbitMQ después de 15 intentos")


def configurar_colas(channel):
    # Exchange receptor de mensajes muertos (DLX)
    channel.exchange_declare(exchange=DLX_EXCHANGE, exchange_type="direct", durable=True)

    # Dead Letter Queue: recibe pedazos que fallaron
    channel.queue_declare(queue=DLQ_QUEUE, durable=True)
    channel.queue_bind(queue=DLQ_QUEUE, exchange=DLX_EXCHANGE, routing_key=PEDAZOS_QUEUE)

    # Cola principal con DLX: si hay nack sin requeue, el mensaje va al DLX automáticamente
    channel.queue_declare(
        queue=PEDAZOS_QUEUE,
        durable=True,
        arguments={
            "x-dead-letter-exchange": DLX_EXCHANGE,
            "x-dead-letter-routing-key": PEDAZOS_QUEUE,
        }
    )

    # Cola de resultados para el centralizador
    channel.queue_declare(queue=RESULTADOS_QUEUE, durable=True)

    # Exchange fanout para notificaciones pub/sub (joiner, dashboard, monitores)
    channel.exchange_declare(exchange=NOTIFICATIONS_EXCHANGE, exchange_type="fanout", durable=True)


def sobel(pedazo):
    pedazo = pedazo.astype(np.float32)

    kernel_x = np.array([[-1, 0, 1],
                         [-2, 0, 2],
                         [-1, 0, 1]])

    kernel_y = np.array([[1, 2, 1],
                         [0, 0, 0],
                         [-1, -2, -1]])

    grad_x = np.zeros_like(pedazo)
    grad_y = np.zeros_like(pedazo)

    for i in range(1, pedazo.shape[0] - 1):
        for j in range(1, pedazo.shape[1] - 1):
            region = pedazo[i - 1:i + 2, j - 1:j + 2]
            grad_x[i, j] = np.sum(region * kernel_x)
            grad_y[i, j] = np.sum(region * kernel_y)

    magnitud = np.sqrt(grad_x**2 + grad_y**2)
    if magnitud.max() > 0:
        magnitud = magnitud / magnitud.max() * 255

    return magnitud.astype(np.uint8)


def procesar_mensaje(ch, method, properties, body):
    inicio = time.time()
    pedazo_id = None
    try:
        data = pickle.loads(body)
        pedazo_id = data["pedazo_id"]
        datos_bytes = data["datos"]

        print(f"[Worker] Procesando pedazo {pedazo_id}")

        buffer = io.BytesIO(datos_bytes)
        pedazo_imagen = np.load(buffer)

        pedazo_resultado = sobel(pedazo_imagen)

        buffer_resultado = io.BytesIO()
        np.save(buffer_resultado, pedazo_resultado)

        respuesta = {
            "pedazo_id": pedazo_id,
            "datos": buffer_resultado.getvalue(),
            "inicio_real": data["inicio_real"],
            "fin_real": data["fin_real"],
            "overlap_inferior": data["overlap_inferior"],
            "overlap_superior": data["overlap_superior"]
        }

        # Resultado directo al centralizador
        ch.basic_publish(
            exchange="",
            routing_key=RESULTADOS_QUEUE,
            body=pickle.dumps(respuesta),
            properties=pika.BasicProperties(delivery_mode=2)
        )

        # Notificación fanout pub/sub: todos los suscriptores reciben el evento
        notificacion = {
            "pedazo_id": pedazo_id,
            "estado": "completado",
            "timestamp": time.time(),
            "worker_id": os.environ.get("HOSTNAME", "unknown")
        }
        ch.basic_publish(
            exchange=NOTIFICATIONS_EXCHANGE,
            routing_key="",
            body=pickle.dumps(notificacion)
        )

        ch.basic_ack(delivery_tag=method.delivery_tag)

        duracion = time.time() - inicio
        PEDAZOS_PROCESADOS.inc()
        TIEMPO_PROCESAMIENTO.observe(duracion)
        print(f"[Worker] Pedazo {pedazo_id} procesado en {duracion:.2f}s")

    except Exception as e:
        print(f"[Worker] Error procesando pedazo {pedazo_id}: {e}")
        PEDAZOS_FALLIDOS.inc()
        # nack sin requeue → va al DLX → queda en DLQ para el dlq-consumer
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def main():
    start_http_server(8000)
    print("[Worker] Métricas Prometheus en :8000/metrics")

    connection = conectar_con_backoff()
    channel = connection.channel()
    channel.basic_qos(prefetch_count=1)

    configurar_colas(channel)

    channel.basic_consume(
        queue=PEDAZOS_QUEUE,
        on_message_callback=procesar_mensaje,
        auto_ack=False
    )

    print("[Worker] Listo, esperando pedazos...")
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
        connection.close()


if __name__ == "__main__":
    main()
