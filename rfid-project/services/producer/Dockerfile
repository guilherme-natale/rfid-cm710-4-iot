FROM python:3.11-slim

LABEL maintainer="RFID CM710-4 Project"
LABEL description="RFID Producer - Monitors log file and publishes to RabbitMQ"

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY producer.py .

# Expose metrics port
EXPOSE 9100

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import socket; s = socket.socket(); s.connect(('localhost', 9100)); s.close()" || exit 1

CMD ["python", "-u", "producer.py"]
