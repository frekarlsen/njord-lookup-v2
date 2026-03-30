FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure data directory exists and json files are placed correctly
RUN mkdir -p /app/data && \
    cp /app/equipment.json /app/data/equipment.json 2>/dev/null || true && \
    cp /app/switchboards.json /app/data/switchboards.json 2>/dev/null || true

# Entrypoint script to handle volume mount (json files might not be in volume yet)
RUN echo '#!/bin/sh\n\
if [ ! -f /app/data/equipment.json ]; then\n\
  cp /app/equipment.json /app/data/equipment.json 2>/dev/null || true\n\
fi\n\
if [ ! -f /app/data/switchboards.json ]; then\n\
  cp /app/switchboards.json /app/data/switchboards.json 2>/dev/null || true\n\
fi\n\
exec "$@"' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

EXPOSE 5000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "app:app"]
