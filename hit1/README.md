#  Prerrequisitos cumplidos

en la carpeta "pantalla" esta la evidencia de los checkpoints para la entrega del hit1

# HIT1 - Procesamiento Distribuido de Imágenes con Filtro Sobel

Sistema distribuido que aplica un filtro de detección de bordes (Sobel) a imágenes dividiendo el trabajo entre múltiples workers mediante RabbitMQ.

## ¿Qué hace el Centralizador?

El `centralizador` es el componente principal que:

1. **Divide la imagen**: Parte la imagen original en `N` pedazos (donde N es la cantidad de workers) con un overlap configurable entre pedazos para evitar artefactos en los bordes.
2. **Distribuye el trabajo**: Publica cada pedazo en la cola `pedazos` de RabbitMQ para que los workers los procesen.
3. **Recibe resultados**: Escucha la cola `resultados` y recolecta los pedazos procesados por los workers.
4. **Maneja timeouts**: Si no recibe resultados en 10 segundos, reenvía los pedazos faltantes automáticamente.
5. **Reensambla la imagen**: Une todos los pedazos procesados recortando el overlap y reconstruye la imagen final.
6. **Guarda el resultado**: Guarda la imagen con bordes detectados en la ruta configurada.

## ¿Qué hacen los Workers?

Los `workers` son procesos que:

1. **Consumen pedazos**: Escuchan la cola `pedazos` de RabbitMQ y reciben fragmentos de la imagen.
2. **Procesan con Sobel**: Aplican el filtro de detección de bordes Sobel a cada pedazo usando convolución 3x3.
3. **Devuelven resultados**: Envían el pedazo procesado de vuelta al centralizador a través de la cola `resultados`.
4. **Confirmación de mensajes**: Usan ACK manual para asegurar que el mensaje fue procesado correctamente.

## Configuración de Variables de Entorno

El archivo `.env` en la raíz del directorio `hit1` define las siguientes variables:

| Variable | Descripción | Valor por defecto |
|----------|-------------|-------------------|
| `N_WORKERS` | Cantidad de workers que procesarán la imagen | `4` |
| `IMAGE_PATH` | Ruta de la imagen de entrada | `/app/imagenes/perro.jpg` |
| `OUTPUT_PATH` | Ruta donde se guardará la imagen procesada | `/app/output_dir/perroBordes.jpg` |
| `OVERLAP` | Cantidad de píxeles de superposición entre pedazos | `15` |

Ejemplo de `.env`:
```
N_WORKERS=4
IMAGE_PATH=/app/imagenes/perro.jpg
OUTPUT_PATH=/app/output_dir/perroBordes.jpg
OVERLAP=15
```

## Cómo correrlo en otra máquina con Docker Compose

### Requisitos previos
- Docker instalado
- Docker Compose instalado

### Pasos

1. **Copiar el directorio completo**

a otra máquina

2. **Configurar las variables de entorno** 

editando el archivo `.env` según la imagen que quieras procesar (asegurate de que la imagen esté en la carpeta `imagenes/`).

3. **Ejecutar Docker Compose** desde el directorio `hit1`:
   ```bash
   cd hit1
   docker compose up --build
   ```

   Esto iniciará:
   - RabbitMQ con interfaz de administración en `http://localhost:15672`
   - El centralizador (que procesa y divide la imagen)
   - N workers (según `N_WORKERS` en el `.env`)

4. **Ver el resultado**: La imagen procesada se guardará en la ruta definida en `OUTPUT_PATH` (dentro del volumen montado en `./imagenes`).

### Notas
- Los puertos expuestos son `5672` para RabbitMQ y `15672` para la interfaz web.
- Las imágenes se montan como volumen en `/app/imagenes` (solo lectura) y el directorio de salida en `/app/output_dir`.
- El sistema escalea horizontalmente: solo cambiá `N_WORKERS` en el `.env` y Docker Compose creará esa cantidad de workers automáticamente.
