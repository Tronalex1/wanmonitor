FROM python:3.11-slim

# Install ping utility (needed for ICMP probes)
RUN apt-get update \
 && apt-get install -y --no-install-recommends iputils-ping \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose the port Koyeb will set via $PORT (default 8000)
EXPOSE 8000

# Single worker + 8 threads keeps the background monitor thread alive
CMD ["sh", "-c", "gunicorn --workers 1 --threads 8 --timeout 120 --bind 0.0.0.0:${PORT:-8000} app:app"]
