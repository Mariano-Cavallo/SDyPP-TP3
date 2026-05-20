FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY centralizador.py .

RUN mkdir -p /app/imagenes /app/output_dir

# Generar imagen de prueba para el pipeline Sobel
RUN python3 -c "\
from PIL import Image, ImageDraw; \
img = Image.new('L', (512, 512), 50); \
draw = ImageDraw.Draw(img); \
[draw.rectangle([i*60, i*60, i*60+50, i*60+50], fill=220) for i in range(8)]; \
draw.ellipse([150, 150, 360, 360], fill=200); \
img.save('/app/imagenes/input.jpg')"

EXPOSE 8001

CMD ["python", "centralizador.py"]
