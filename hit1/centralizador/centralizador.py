import os
import pika
import time
import io
import pickle
from PIL import Image
import numpy as np


def conectar():
    host = os.environ.get("RABBITMQ_HOST", "localhost")

    for intento in range(10):
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=host))
            print(f"Conectado a RabbitMQ en {host}")
            return connection
        except Exception as e:
            print(f"Intento {intento + 1} fallido: {e}. Reintentando en 2s...")
            time.sleep(2)

    raise Exception("No se pudo conectar a RabbitMQ después de 10 intentos")


# partir el array en partes para mandar por RabbitMQ
def partir_imagen(path, n):
    img = Image.open(path).convert("L")  # escala de grises
    array = np.array(img)
    pedazos = np.array_split(array, n, axis=0)
    print(f"Imagen partida en {n} pedazos. Shape original: {array.shape}")
    return pedazos


# crear N workers y mandar cada parte a cada worker


def publicar_pedazos(channel, pedazos):
    total = len(pedazos)

    for i, pedazo in enumerate(pedazos):

        # serializar el array a bytes
        buffer = io.BytesIO()
        np.save(buffer, pedazo)
        datos_bytes = buffer.getvalue()

        # armar el mensaje completo
        mensaje = {"pedazo_id": i, "total_pedazos": total, "datos": datos_bytes}

        # serializar el mensaje completo
        channel.basic_publish(
            exchange="", routing_key="pedazos", body=pickle.dumps(mensaje)
        )
        print(f"Publicado pedazo {i + 1}/{total}")


def reenviar_pedazos_faltantes(channel, pedazos_faltantes, pedazos):
    total = len(pedazos_faltantes)

    for i in pedazos_faltantes:
        # serializar el array a bytes
        buffer = io.BytesIO()
        np.save(buffer, pedazos[i])
        datos_bytes = buffer.getvalue()

        # armar el mensaje completo
        mensaje = {"pedazo_id": i, "datos": datos_bytes}

        # serializar el mensaje completo
        channel.basic_publish(
            exchange="", routing_key="pedazos", body=pickle.dumps(mensaje)
        )


def unir_resultados(pedazos_recibidos):
    # ordenar los pedazos por su ID
    pedazos_ordenados = [pedazos_recibidos[i] for i in sorted(pedazos_recibidos.keys())]
    # unirlos verticalmente (axis=0)
    resultado_final = np.vstack(pedazos_ordenados)
    return resultado_final


# 1. Conectarse a RabbitMQ
def main():
    # estas variables estan en el .env
    N = int(os.environ.get("N_WORKERS", 4))
    IMAGE_PATH = os.environ.get("IMAGE_PATH", "/app/imagenes/input.jpg")
    OUTPUT_PATH = os.environ.get("OUTPUT_PATH", "/app/output_dir/output.jpg")

    connection = conectar()
    channel = connection.channel()

    # declarar las dos colas
    channel.queue_declare(queue="")
    channel.queue_declare(queue="resultados")

    pedazos = partir_imagen(IMAGE_PATH, N)
    publicar_pedazos(channel, pedazos)

    print("Todos los pedazos publicados. Esperando resultados...")
    # acá después viene la lógica de escuchar "resultados"

    pedazos_faltantes = set(range(N))
    pedazos_recibidos = {}
    ultimo_progreso = time.time()

    while len(pedazos_faltantes) > 0:
        method, properties, body = channel.basic_get(queue="resultados")
        if body is None:
            tiempo_sin_progreso = time.time() - ultimo_progreso
            if tiempo_sin_progreso > 10:
                print(
                    "No se han recibido resultados en los últimos 10 segundos. Reenviando pedazos faltantes..."
                )
                reenviar_pedazos_faltantes(channel, pedazos_faltantes, pedazos)
                ultimo_progreso = time.time()
        else:
            resultado = pickle.loads(body)
            pedazo_id = resultado["pedazo_id"]
            datos_bytes = resultado["datos"]

            # convertir de vuelta a array
            buffer = io.BytesIO(datos_bytes)
            pedazo_resultado = np.load(buffer)

            pedazos_recibidos[pedazo_id] = pedazo_resultado
            pedazos_faltantes.remove(pedazo_id)

            # print(f"Recibido resultado del pedazo {pedazo_id}. Faltan: {len(pedazos_faltantes)}")

    array_resultado = unir_resultados(pedazos_recibidos)
    print("Todos los resultados recibidos. Imagen procesada.")
    img_resultado = Image.fromarray(array_resultado)
    img_resultado.save(OUTPUT_PATH)
    print(f"Imagen guardada en {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
