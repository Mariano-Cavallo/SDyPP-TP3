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

def random_bool():
    numero = random.random()  
    return numero > 0.5

def main():
    
    print("Hola pude abrir el producer")
    connection = conectar()
    channel = connection.channel()

    # Declara la cola (si no existe, la crea)
    channel.queue_declare(
        queue="tareas",
        arguments={
            "x-dead-letter-exchange": "dlx"
        }
    )
    
    for i in range(1, 20):
        bool = random_bool()
        channel.basic_publish(
            exchange="",  # exchange vacío = modo directo a la cola
            routing_key="tareas",  # nombre de la cola destino
            body=json.dumps({"tarea": f"Tarea {i}", "error": f"{bool}"}),
                properties=pika.BasicProperties(
                content_type="application/json"
                )
        )
        print(f"Enviado: Tarea {i}")
        #time.sleep(0.5)  # pequeña pausa para que se vea el envío

    connection.close()
    print("Producer terminó.")


if __name__ == "__main__":
    main()
