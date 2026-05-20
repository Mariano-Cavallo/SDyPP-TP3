import os
import pika
import time
import io
import pickle
from PIL import Image
import numpy as np
from prometheus_client import Counter, Gauge, Histogram, start_http_server

PEDAZOS_PUBLICADOS = Counter("sobel_centralizador_pedazos_publicados_total", "Pedazos enviados a workers")
PEDAZOS_PENDIENTES = Gauge("sobel_centralizador_pedazos_pendientes", "Pedazos sin resultado aún")
TIEMPO_TOTAL = Histogram("sobel_centralizador_tiempo_total_seconds", "Tiempo total del pipeline completo")

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
            print(f"[Centralizador] Conectado a RabbitMQ en {host}")
            return connection
        except Exception as e:
            print(f"[Centralizador] Intento {intento + 1} fallido: {e}. Reintentando en {delay}s...")
            time.sleep(delay)
            delay = min(delay * 2, max_delay)

    raise Exception("No se pudo conectar a RabbitMQ después de 15 intentos")


def configurar_colas(channel):
    # DLX + DLQ (mismo setup que el worker para que RabbitMQ no tenga conflictos de definición)
    channel.exchange_declare(exchange=DLX_EXCHANGE, exchange_type="direct", durable=True)
    channel.queue_declare(queue=DLQ_QUEUE, durable=True)
    channel.queue_bind(queue=DLQ_QUEUE, exchange=DLX_EXCHANGE, routing_key=PEDAZOS_QUEUE)

    channel.queue_declare(
        queue=PEDAZOS_QUEUE,
        durable=True,
        arguments={
            "x-dead-letter-exchange": DLX_EXCHANGE,
            "x-dead-letter-routing-key": PEDAZOS_QUEUE,
        }
    )

    channel.queue_declare(queue=RESULTADOS_QUEUE, durable=True)

    # Exchange fanout pub/sub
    channel.exchange_declare(exchange=NOTIFICATIONS_EXCHANGE, exchange_type="fanout", durable=True)

    # Suscribirse al fanout para recibir notificaciones de workers completados
    result = channel.queue_declare(queue="", exclusive=True)
    notif_queue = result.method.queue
    channel.queue_bind(queue=notif_queue, exchange=NOTIFICATIONS_EXCHANGE)
    print(f"[Centralizador] Suscripto al exchange '{NOTIFICATIONS_EXCHANGE}' en cola temporal '{notif_queue}'")

    return notif_queue


def partir_imagen(path, n, overlap):
    img = Image.open(path).convert("L")
    array = np.array(img)
    altura = array.shape[0]

    tamanio_pedazo = altura // n
    pedazos = []

    for i in range(n):
        inicio = i * tamanio_pedazo
        fin = (i + 1) * tamanio_pedazo

        inicio_con_overlap = max(0, inicio - overlap)
        fin_con_overlap = min(altura, fin + overlap)

        pedazo = array[inicio_con_overlap:fin_con_overlap]

        pedazos.append({
            "id": i,
            "pedazo": pedazo,
            "inicio_real": inicio,
            "fin_real": fin,
            "inicio_con_overlap": inicio_con_overlap,
            "fin_con_overlap": fin_con_overlap,
            "overlap_inferior": fin - fin_con_overlap,
            "overlap_superior": inicio - inicio_con_overlap
        })

    print(f"[Centralizador] Imagen partida en {n} pedazos con overlap={overlap}. Shape: {array.shape}")
    return pedazos


def publicar_pedazos(channel, pedazos):
    total = len(pedazos)
    for pedazo_info in pedazos:
        buffer = io.BytesIO()
        np.save(buffer, pedazo_info["pedazo"])
        datos_bytes = buffer.getvalue()

        mensaje = {
            "pedazo_id": pedazo_info["id"],
            "total_pedazos": total,
            "datos": datos_bytes,
            "inicio_real": pedazo_info["inicio_real"],
            "fin_real": pedazo_info["fin_real"],
            "overlap_inferior": pedazo_info["overlap_inferior"],
            "overlap_superior": pedazo_info["overlap_superior"]
        }

        channel.basic_publish(
            exchange="",
            routing_key=PEDAZOS_QUEUE,
            body=pickle.dumps(mensaje),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        PEDAZOS_PUBLICADOS.inc()
        print(f"[Centralizador] Publicado pedazo {pedazo_info['id'] + 1}/{total}")


def unir_resultados(pedazos_recibidos, overlap):
    pedazos_ordenados = sorted(pedazos_recibidos.values(), key=lambda x: x["inicio_real"])

    resultados_recortados = []
    for pedazo_info in pedazos_ordenados:
        pedazo = pedazo_info["resultado"]
        inicio = overlap
        fin = len(pedazo) - overlap
        pedazo_recortado = pedazo[inicio:fin]
        resultados_recortados.append(pedazo_recortado)

    return np.vstack(resultados_recortados)


def main():
    start_http_server(8001)
    print("[Centralizador] Métricas Prometheus en :8001/metrics")

    N = int(os.environ.get("N_WORKERS", 4))
    IMAGE_PATH = os.environ.get("IMAGE_PATH", "/app/imagenes/input.jpg")
    OUTPUT_PATH = os.environ.get("OUTPUT_PATH", "/app/output_dir/output.jpg")
    OVERLAP = int(os.environ.get("OVERLAP", 15))

    connection = conectar_con_backoff()
    channel = connection.channel()

    configurar_colas(channel)

    pedazos = partir_imagen(IMAGE_PATH, N, OVERLAP)
    PEDAZOS_PENDIENTES.set(N)

    inicio_total = time.time()
    publicar_pedazos(channel, pedazos)
    print("[Centralizador] Todos los pedazos publicados. Esperando resultados...")

    pedazos_faltantes = set(range(N))
    pedazos_recibidos = {}
    ultimo_progreso = time.time()

    while len(pedazos_faltantes) > 0:
        method, properties, body = channel.basic_get(queue=RESULTADOS_QUEUE)
        if body is None:
            tiempo_sin_progreso = time.time() - ultimo_progreso
            if tiempo_sin_progreso > 10:
                print(f"[Centralizador] Sin resultados por 10s. Reenviando {len(pedazos_faltantes)} pedazos...")
                for pedazo_id in pedazos_faltantes:
                    pedazo_info = pedazos[pedazo_id]
                    buffer = io.BytesIO()
                    np.save(buffer, pedazo_info["pedazo"])
                    mensaje = {
                        "pedazo_id": pedazo_info["id"],
                        "total_pedazos": N,
                        "datos": buffer.getvalue(),
                        "inicio_real": pedazo_info["inicio_real"],
                        "fin_real": pedazo_info["fin_real"],
                        "overlap_inferior": pedazo_info["overlap_inferior"],
                        "overlap_superior": pedazo_info["overlap_superior"]
                    }
                    channel.basic_publish(
                        exchange="",
                        routing_key=PEDAZOS_QUEUE,
                        body=pickle.dumps(mensaje),
                        properties=pika.BasicProperties(delivery_mode=2)
                    )
                ultimo_progreso = time.time()
            time.sleep(0.1)
        else:
            resultado = pickle.loads(body)
            pedazo_id = resultado["pedazo_id"]

            buffer = io.BytesIO(resultado["datos"])
            pedazo_resultado = np.load(buffer)

            pedazos_recibidos[pedazo_id] = {
                "resultado": pedazo_resultado,
                "inicio_real": resultado["inicio_real"],
                "fin_real": resultado["fin_real"],
                "overlap_inferior": resultado["overlap_inferior"],
                "overlap_superior": resultado["overlap_superior"]
            }
            pedazos_faltantes.discard(pedazo_id)
            PEDAZOS_PENDIENTES.set(len(pedazos_faltantes))
            ultimo_progreso = time.time()
            print(f"[Centralizador] Recibido pedazo {pedazo_id}. Faltan: {len(pedazos_faltantes)}")

    TIEMPO_TOTAL.observe(time.time() - inicio_total)

    array_resultado = unir_resultados(pedazos_recibidos, OVERLAP)
    print("[Centralizador] Ensamblando imagen final...")
    img_resultado = Image.fromarray(array_resultado)
    img_resultado.save(OUTPUT_PATH)
    print(f"[Centralizador] Imagen guardada en {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
