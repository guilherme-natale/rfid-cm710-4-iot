FROM python:3.11-slim

LABEL maintainer="RFID CM710-4 Project"
LABEL description="RFID Consumer - Consumes from RabbitMQ and stores in InfluxDB"

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY consumer.py .

EXPOSE 9101

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import socket; s = socket.socket(); s.connect(('localhost', 9101)); s.close()" || exit 1

CMD ["python", "-u", "consumer.py"]
