# TP-Link Router Exporter

Prometheus exporter for TP-Link routers using the [tplinkrouterc6u](https://github.com/AlexandrErohin/TP-Link-Archer-C6U) library.

Tested with TP-Link Archer AX55, but should work with other models supported by the library.

## Metrics

### Router Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `tplink_router_info` | Gauge | Router information (WAN IP, LAN IP, connection type as labels) |
| `tplink_cpu_usage_ratio` | Gauge | CPU usage (0-1) |
| `tplink_memory_usage_ratio` | Gauge | Memory usage (0-1) |
| `tplink_clients_total` | Gauge | Total connected clients |
| `tplink_wifi_clients_total` | Gauge | WiFi clients count |
| `tplink_wired_clients_total` | Gauge | Wired clients count |
| `tplink_guest_clients_total` | Gauge | Guest network clients |
| `tplink_iot_clients_total` | Gauge | IoT network clients |
| `tplink_wifi_enabled` | Gauge | WiFi enabled state (labels: band, network_type) |

### Per-Device Metrics

All device metrics include labels: `mac`, `hostname`, `ip`, `connection_type`

| Metric | Type | Description |
|--------|------|-------------|
| `tplink_device_active` | Gauge | Device active state (1/0) |
| `tplink_device_signal_dbm` | Gauge | WiFi signal strength in dBm |
| `tplink_device_download_speed_bytes` | Gauge | Current download speed (bytes/s) |
| `tplink_device_upload_speed_bytes` | Gauge | Current upload speed (bytes/s) |
| `tplink_device_packets_sent_total` | Counter | Total packets sent |
| `tplink_device_packets_received_total` | Counter | Total packets received |

### Scrape Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `tplink_scrape_success` | Gauge | Whether the last scrape succeeded (1/0) |
| `tplink_scrape_duration_seconds` | Gauge | Duration of the last scrape |

## Installation

### Docker

```bash
docker run -d \
  --name tplink-router-exporter \
  -p 9120:9120 \
  ghcr.io/ldziedziul/tplink-router-exporter \
  --host 192.168.0.1 \
  --password ${TPLINK_PASSWORD}
```

### Docker Compose

```yaml
services:
  tplink-router-exporter:
    image: ghcr.io/ldziedziul/tplink-router-exporter
    container_name: tplink-router-exporter
    restart: unless-stopped
    ports:
      - "9120:9120"
    command:
      - --host=192.168.0.1
      - --password=${TPLINK_PASSWORD}
```

### Python

```bash
pip install tplinkrouterc6u prometheus-client

python tplink_router_exporter.py --host 192.168.0.1 --password ${TPLINK_PASSWORD}
```

## Usage

```
usage: tplink_router_exporter.py [-h] [--host HOST] --password PASSWORD
                                 [--username USERNAME] [--https] [--verify-ssl]
                                 [--port PORT] [--listen LISTEN] [--debug]

options:
  -h, --help            show this help message and exit
  --host, -H HOST       Router IP address or hostname (default: 192.168.0.1)
  --password, -p PASSWORD
                        Router admin password (local password, not TP-Link ID)
  --username, -u USERNAME
                        Router admin username (default: admin)
  --https               Use HTTPS connection to router
  --verify-ssl          Verify SSL certificate (only with --https)
  --port PORT           Port to expose metrics on (default: 9120)
  --listen LISTEN       Address to listen on (default: 0.0.0.0)
  --debug               Enable debug logging
```

## Prometheus Configuration

```yaml
scrape_configs:
  - job_name: 'tplink'
    static_configs:
      - targets: ['localhost:9120']
    scrape_interval: 30s
```

## Notes

- Use the **local router password**, not your TP-Link ID password
- The router only allows one admin session at a time - avoid opening the web UI while the exporter is running
- Recommended scrape interval: 30s or higher to avoid overwhelming the router

## License

MIT
