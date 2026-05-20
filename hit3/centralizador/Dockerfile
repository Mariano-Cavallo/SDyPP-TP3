FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY centralizador.py .

RUN mkdir -p /app/imagenes /app/output_dir

EXPOSE 8001

CMD ["python", "centralizador.py"]
