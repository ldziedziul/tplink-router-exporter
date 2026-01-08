FROM python:3.14-alpine AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --target=/build/packages -r requirements.txt

# Final image
FROM python:3.14-alpine

LABEL org.opencontainers.image.title="TP-Link Router Exporter"
LABEL org.opencontainers.image.description="Prometheus exporter for TP-Link routers"
LABEL org.opencontainers.image.source="https://github.com/ldziedziul/tplink-router-exporter"

WORKDIR /app

COPY --from=builder /build/packages /usr/local/lib/python3.14/site-packages/

COPY tplink_router_exporter.py .

# Default port
EXPOSE 9120

# Run as non-root user
RUN adduser -D -u 1000 exporter
USER exporter

ENTRYPOINT ["python", "tplink_router_exporter.py"]