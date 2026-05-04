import pika
import os
import time
import pickle
import numpy as np
import io


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
    magnitud = magnitud / magnitud.max() * 255

    return magnitud.astype(np.uint8)


def procesar_mensaje(ch, method, properties, body):
    try:
        data = pickle.loads(body)
        pedazo_id = data["pedazo_id"]
        datos_bytes = data["datos"]

        print(f"Recibido pedazo {pedazo_id}")
        time.sleep(1)  # Simular tiempo de procesamiento

        buffer = io.BytesIO(datos_bytes)
        pedazo_imagen = np.load(buffer)

        # Aplicar el filtro de Sobel
        pedazo_resultado = sobel(pedazo_imagen)

        # enviar resultado de vuelta al centralizador
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

        ch.basic_publish(
            exchange="", routing_key="resultados", body=pickle.dumps(respuesta)
        )

        ch.basic_ack(delivery_tag=method.delivery_tag)  # ack del mensaje

    except Exception as e:
        print(f"Error procesando mensaje: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def main():
    print("Hola pude abrir el consumer")
    connection = conectar()
    channel = connection.channel()
    channel.basic_qos(prefetch_count=1)

    # Declara la cola (si no existe, la crea)
    channel.queue_declare(queue="pedazos", durable=True)

    channel.basic_consume(
        queue="pedazos", on_message_callback=procesar_mensaje, auto_ack=False
    )

    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print("Interrumpido")
        channel.stop_consuming()
        connection.close()


if __name__ == "__main__":
    main()
