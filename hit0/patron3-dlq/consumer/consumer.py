import pika
import os
import time
import json


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


def procesar_mensaje(ch, method, properties, body):
    try:
        data = json.loads(body.decode())
        print(f"Recibido: {data}")

        time.sleep(2)  # simula tiempo de procesamiento
        if data.get("error") == "True":
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        else:    
            ch.basic_ack(delivery_tag=method.delivery_tag)  # ack del mensaje

    except Exception as e:
        print(f"Error procesando mensaje: {e}")


def main():
    print("Hola pude abrir el consumer")
    connection = conectar()
    channel = connection.channel()
    channel.basic_qos(prefetch_count=1)
    
    channel.exchange_declare(exchange="dlx", exchange_type="fanout")

    channel.queue_declare(
        queue="tareas",
        arguments={
            "x-dead-letter-exchange": "dlx"
        }
    )
    

    channel.basic_consume(
        queue="tareas", on_message_callback=procesar_mensaje, auto_ack=False
    )

    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print("Interrumpido")
        channel.stop_consuming()
        connection.close()


if __name__ == "__main__":
    main()
