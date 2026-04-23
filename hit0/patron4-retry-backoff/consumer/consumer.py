import pika
import os
import time
import json
import random


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
    data = json.loads(body.decode())

    retry = data.get("retry", 0)

    print(f"Intento {retry} → {data}")

    fallo = random.random() > 0.3

    if not fallo:
        print("Procesado OK")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    if retry >= 4:
        print("Enviando a DLQ")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        return

    retry += 1
    data["retry"] = retry
    delay = 2 ** (retry - 1) * 1000

    print(f"Reintento en {delay} ms")

    ch.basic_publish(
        exchange="",
        routing_key="tareas_retry",
        body=json.dumps(data),
        properties=pika.BasicProperties(
            expiration=str(delay), content_type="application/json"
        ),
    )

    ch.basic_ack(delivery_tag=method.delivery_tag)
    return


def main():
    print("Hola pude abrir el consumer")
    connection = conectar()
    channel = connection.channel()
    channel.basic_qos(prefetch_count=1)

    channel.exchange_declare(exchange="dlx", exchange_type="fanout")

    channel.queue_declare(queue="tareas", arguments={"x-dead-letter-exchange": "dlx"})

    channel.queue_declare(
        queue="tareas_retry",
        arguments={"x-dead-letter-exchange": "", "x-dead-letter-routing-key": "tareas"},
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
