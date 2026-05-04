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
def partir_imagen(path, n, overlap):
    img = Image.open(path).convert("L")
    array = np.array(img)
    altura = array.shape[0]
    
    tamanio_pedazo = altura // n
    pedazos = []
    
    for i in range(n):
        inicio = i * tamanio_pedazo
        fin = (i + 1) * tamanio_pedazo
        
        # Agregar superposición (excepto en los extremos)
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
        
    print(f"Imagen partida en {n} pedazos con overlap={overlap}. Shape original: {array.shape}")
    return pedazos


# crear N workers y mandar cada parte a cada worker


def publicar_pedazos(channel, pedazos):
    total = len(pedazos)

    for pedazo_info in pedazos:

        # serializar el array a bytes
        buffer = io.BytesIO()
        np.save(buffer, pedazo_info["pedazo"])
        datos_bytes = buffer.getvalue()

        # armar el mensaje completo
        mensaje = {
            "pedazo_id": pedazo_info["id"],
            "total_pedazos": total,
            "datos": datos_bytes,
            "inicio_real": pedazo_info["inicio_real"],
            "fin_real": pedazo_info["fin_real"],
            "overlap_inferior": pedazo_info["overlap_inferior"],
            "overlap_superior": pedazo_info["overlap_superior"]
        }

        # serializar el mensaje completo
        channel.basic_publish(
            exchange="", routing_key="pedazos", body=pickle.dumps(mensaje)
        )
        print(f"Publicado pedazo {pedazo_info['id'] + 1}/{total}")


def reenviar_pedazos_faltantes(channel, pedazos_faltantes, pedazos):
    total = len(pedazos_faltantes)

    for pedazo_id in pedazos_faltantes:
        pedazo_info = pedazos[pedazo_id]
        
        # serializar el array a bytes
        buffer = io.BytesIO()
        np.save(buffer, pedazo_info["pedazo"])
        datos_bytes = buffer.getvalue()

        # armar el mensaje completo
        mensaje = {
            "pedazo_id": pedazo_info["id"],
            "total_pedazos": total,
            "datos": datos_bytes,
            "inicio_real": pedazo_info["inicio_real"],
            "fin_real": pedazo_info["fin_real"],
            "overlap_inferior": pedazo_info["overlap_inferior"],
            "overlap_superior": pedazo_info["overlap_superior"]
        }

        # serializar el mensaje completo
        channel.basic_publish(
            exchange="", routing_key="pedazos", body=pickle.dumps(mensaje)
        )


def unir_resultados(pedazos_recibidos, overlap):
    # ordenar los pedazos por su inicio_real (posición original)
    pedazos_ordenados = sorted(pedazos_recibidos.values(), key=lambda x: x["inicio_real"])
    
    # Recortar la superposición de cada pedazo y unirlos
    resultados_recortados = []
    for pedazo_info in pedazos_ordenados:
        pedazo = pedazo_info["resultado"]
        overlap_superior = pedazo_info["overlap_superior"]
        overlap_inferior = pedazo_info["overlap_inferior"]
        
        # Recortar la superposición
        inicio = overlap  # skip pixels from overlap with previous
        fin = len(pedazo) - overlap  # skip pixels from overlap with next
        
        pedazo_recortado = pedazo[inicio:fin]
        resultados_recortados.append(pedazo_recortado)
    
    resultado_final = np.vstack(resultados_recortados)
    return resultado_final


# 1. Conectarse a RabbitMQ
def main():
    # estas variables estan en el .env
    N = int(os.environ.get("N_WORKERS", 4))
    IMAGE_PATH = os.environ.get("IMAGE_PATH", "/app/imagenes/input.jpg")
    OUTPUT_PATH = os.environ.get("OUTPUT_PATH", "/app/output_dir/output.jpg")
    OVERLAP = int(os.environ.get("OVERLAP", 15))

    connection = conectar()
    channel = connection.channel()

    # declarar las dos colas
    channel.queue_declare(queue="pedazos", durable=True)
    channel.queue_declare(queue="resultados", durable=True)

    pedazos = partir_imagen(IMAGE_PATH, N, OVERLAP)
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
            overlap_inferior = resultado["overlap_inferior"]
            overlap_superior = resultado["overlap_superior"]

            # convertir de vuelta a array
            buffer = io.BytesIO(datos_bytes)
            pedazo_resultado = np.load(buffer)

            pedazos_recibidos[pedazo_id] = {
                "resultado": pedazo_resultado,
                "inicio_real": resultado["inicio_real"],
                "fin_real": resultado["fin_real"],
                "overlap_inferior": overlap_inferior,
                "overlap_superior": overlap_superior
            }
            pedazos_faltantes.remove(pedazo_id)

            # print(f"Recibido resultado del pedazo {pedazo_id}. Faltan: {len(pedazos_faltantes)}")

    array_resultado = unir_resultados(pedazos_recibidos, OVERLAP)
    print("Todos los resultados recibidos. Imagen procesada.")
    img_resultado = Image.fromarray(array_resultado)
    img_resultado.save(OUTPUT_PATH)
    print(f"Imagen guardada en {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
