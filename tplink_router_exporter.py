#!/usr/bin/env python3
"""
TP-Link Router Prometheus Exporter

Exports metrics from TP-Link routers (e.g., Archer AX55) for Prometheus.
Uses the tplinkrouterc6u library for router communication.

Usage:
    python tplink_exporter.py --host 192.168.0.1 --password yourpassword
    python tplink_exporter.py --host 192.168.0.1 --password yourpassword --port 9120
"""

import argparse
import logging
import sys
import time
from typing import Optional

try:
    from prometheus_client import (
        Gauge,
        Info,
        Counter,
        CollectorRegistry,
        generate_latest,
        CONTENT_TYPE_LATEST,
    )
    from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily
except ImportError:
    print("Error: prometheus_client package not installed.")
    print("Install with: pip install prometheus-client")
    sys.exit(1)

try:
    from tplinkrouterc6u import TplinkRouterProvider, Connection
    from tplinkrouterc6u.common.exception import ClientException
except ImportError:
    print("Error: tplinkrouterc6u package not installed.")
    print("Install with: pip install tplinkrouterc6u")
    sys.exit(1)

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Connection type labels for metrics
CONNECTION_LABELS = {
    Connection.HOST_2G: "wifi_2g",
    Connection.HOST_5G: "wifi_5g",
    Connection.HOST_6G: "wifi_6g",
    Connection.GUEST_2G: "guest_2g",
    Connection.GUEST_5G: "guest_5g",
    Connection.GUEST_6G: "guest_6g",
    Connection.IOT_2G: "iot_2g",
    Connection.IOT_5G: "iot_5g",
    Connection.IOT_6G: "iot_6g",
    Connection.WIRED: "wired",
}


def get_connection_label(conn_type: Optional[Connection]) -> str:
    """Get Prometheus-friendly connection type label."""
    if conn_type is None:
        return "unknown"
    return CONNECTION_LABELS.get(conn_type, "unknown")


class TPLinkCollector:
    """Custom Prometheus collector for TP-Link router metrics."""

    def __init__(self, host: str, password: str, username: str = "admin", verify_ssl: bool = False):
        self.host = host
        self.password = password
        self.username = username
        self.verify_ssl = verify_ssl
        self._last_scrape_success = False
        self._last_scrape_duration = 0.0

    def _get_router_status(self):
        """Connect to router and get status."""
        if not self.host.startswith(("http://", "https://")):
            host = f"http://{self.host}"
        else:
            host = self.host

        router = TplinkRouterProvider.get_client(host, self.password, self.username)
        if hasattr(router, '_verify_ssl'):
            router._verify_ssl = self.verify_ssl

        try:
            router.authorize()
            status = router.get_status()
            return status
        finally:
            try:
                router.logout()
            except Exception:
                pass

    def collect(self):
        """Collect metrics from the router."""
        start_time = time.time()

        # Scrape metrics
        scrape_success = GaugeMetricFamily(
            'tplink_scrape_success',
            'Whether the last scrape was successful (1 = success, 0 = failure)'
        )
        scrape_duration = GaugeMetricFamily(
            'tplink_scrape_duration_seconds',
            'Duration of the last scrape in seconds'
        )

        try:
            status = self._get_router_status()
            self._last_scrape_success = True
        except Exception as e:
            logger.error(f"Failed to scrape router: {e}")
            self._last_scrape_success = False
            self._last_scrape_duration = time.time() - start_time
            scrape_success.add_metric([], 0)
            scrape_duration.add_metric([], self._last_scrape_duration)
            yield scrape_success
            yield scrape_duration
            return

        # Router info
        router_info = GaugeMetricFamily(
            'tplink_router_info',
            'Router information',
            labels=['wan_ip', 'lan_ip', 'connection_type']
        )
        router_info.add_metric(
            [
                status.wan_ipv4_addr or '',
                status.lan_ipv4_addr or '',
                status.conn_type or ''
            ],
            1
        )
        yield router_info

        # CPU usage
        if status.cpu_usage is not None:
            cpu_usage = GaugeMetricFamily(
                'tplink_cpu_usage_ratio',
                'Router CPU usage (0-1)'
            )
            cpu_usage.add_metric([], status.cpu_usage)
            yield cpu_usage

        # Memory usage
        if status.mem_usage is not None:
            mem_usage = GaugeMetricFamily(
                'tplink_memory_usage_ratio',
                'Router memory usage (0-1)'
            )
            mem_usage.add_metric([], status.mem_usage)
            yield mem_usage

        # Client counts
        clients_total = GaugeMetricFamily(
            'tplink_clients_total',
            'Total number of connected clients'
        )
        clients_total.add_metric([], status.clients_total or 0)
        yield clients_total

        wifi_clients = GaugeMetricFamily(
            'tplink_wifi_clients_total',
            'Number of WiFi clients'
        )
        wifi_clients.add_metric([], status.wifi_clients_total or 0)
        yield wifi_clients

        wired_clients = GaugeMetricFamily(
            'tplink_wired_clients_total',
            'Number of wired clients'
        )
        wired_clients.add_metric([], status.wired_total or 0)
        yield wired_clients

        guest_clients = GaugeMetricFamily(
            'tplink_guest_clients_total',
            'Number of guest network clients'
        )
        guest_clients.add_metric([], status.guest_clients_total or 0)
        yield guest_clients

        if status.iot_clients_total is not None:
            iot_clients = GaugeMetricFamily(
                'tplink_iot_clients_total',
                'Number of IoT network clients'
            )
            iot_clients.add_metric([], status.iot_clients_total)
            yield iot_clients

        # WiFi enabled states
        wifi_enabled = GaugeMetricFamily(
            'tplink_wifi_enabled',
            'WiFi network enabled state (1 = enabled, 0 = disabled)',
            labels=['band', 'network_type']
        )
        wifi_enabled.add_metric(['2.4ghz', 'host'], 1 if status.wifi_2g_enable else 0)
        if status.wifi_5g_enable is not None:
            wifi_enabled.add_metric(['5ghz', 'host'], 1 if status.wifi_5g_enable else 0)
        if status.wifi_6g_enable is not None:
            wifi_enabled.add_metric(['6ghz', 'host'], 1 if status.wifi_6g_enable else 0)
        wifi_enabled.add_metric(['2.4ghz', 'guest'], 1 if status.guest_2g_enable else 0)
        if status.guest_5g_enable is not None:
            wifi_enabled.add_metric(['5ghz', 'guest'], 1 if status.guest_5g_enable else 0)
        if status.guest_6g_enable is not None:
            wifi_enabled.add_metric(['6ghz', 'guest'], 1 if status.guest_6g_enable else 0)
        yield wifi_enabled

        # Per-device metrics
        device_labels = ['mac', 'hostname', 'ip', 'connection_type']

        device_active = GaugeMetricFamily(
            'tplink_device_active',
            'Device active state (1 = active, 0 = inactive)',
            labels=device_labels
        )
        device_signal = GaugeMetricFamily(
            'tplink_device_signal_dbm',
            'Device WiFi signal strength in dBm',
            labels=device_labels
        )
        device_down_speed = GaugeMetricFamily(
            'tplink_device_download_speed_bytes',
            'Device current download speed in bytes/s',
            labels=device_labels
        )
        device_up_speed = GaugeMetricFamily(
            'tplink_device_upload_speed_bytes',
            'Device current upload speed in bytes/s',
            labels=device_labels
        )
        device_packets_sent = CounterMetricFamily(
            'tplink_device_packets_sent_total',
            'Total packets sent by device',
            labels=device_labels
        )
        device_packets_received = CounterMetricFamily(
            'tplink_device_packets_received_total',
            'Total packets received by device',
            labels=device_labels
        )

        for device in status.devices:
            labels = [
                device.macaddr or 'unknown',
                device.hostname or 'unknown',
                device.ipaddr or 'unknown',
                get_connection_label(device.type)
            ]

            device_active.add_metric(labels, 1 if device.active else 0)

            if device.signal is not None:
                device_signal.add_metric(labels, device.signal)

            if device.down_speed is not None:
                device_down_speed.add_metric(labels, device.down_speed)

            if device.up_speed is not None:
                device_up_speed.add_metric(labels, device.up_speed)

            if device.packets_sent is not None:
                device_packets_sent.add_metric(labels, device.packets_sent)

            if device.packets_received is not None:
                device_packets_received.add_metric(labels, device.packets_received)

        yield device_active
        yield device_signal
        yield device_down_speed
        yield device_up_speed
        yield device_packets_sent
        yield device_packets_received

        # Scrape success metrics
        self._last_scrape_duration = time.time() - start_time
        scrape_success.add_metric([], 1)
        scrape_duration.add_metric([], self._last_scrape_duration)
        yield scrape_success
        yield scrape_duration


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler for Prometheus metrics endpoint."""

    collector = None

    def log_message(self, format, *args):
        """Override to use logger instead of stderr."""
        logger.debug("%s - %s", self.address_string(), format % args)

    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)

        if parsed.path == '/metrics':
            self._serve_metrics()
        elif parsed.path == '/':
            self._serve_index()
        elif parsed.path == '/health':
            self._serve_health()
        else:
            self.send_error(404, 'Not Found')

    def _serve_metrics(self):
        """Serve Prometheus metrics."""
        registry = CollectorRegistry()
        registry.register(self.collector)

        try:
            output = generate_latest(registry)
            self.send_response(200)
            self.send_header('Content-Type', CONTENT_TYPE_LATEST)
            self.send_header('Content-Length', len(output))
            self.end_headers()
            self.wfile.write(output)
        except Exception as e:
            logger.error(f"Error generating metrics: {e}")
            self.send_error(500, str(e))

    def _serve_index(self):
        """Serve index page."""
        html = b"""<!DOCTYPE html>
<html>
<head><title>TP-Link Exporter</title></head>
<body>
<h1>TP-Link Router Prometheus Exporter</h1>
<p><a href="/metrics">Metrics</a></p>
<p><a href="/health">Health</a></p>
</body>
</html>"""
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Length', len(html))
        self.end_headers()
        self.wfile.write(html)

    def _serve_health(self):
        """Serve health check endpoint."""
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')


def run_server(host: str, port: int, collector: TPLinkCollector):
    """Run the HTTP server."""
    MetricsHandler.collector = collector
    server = HTTPServer((host, port), MetricsHandler)
    logger.info(f"Starting TP-Link exporter on http://{host}:{port}")
    logger.info(f"Metrics available at http://{host}:{port}/metrics")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.shutdown()


def main():
    parser = argparse.ArgumentParser(
        description="Prometheus exporter for TP-Link routers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --host 192.168.0.1 --password mypassword
  %(prog)s --host 192.168.0.1 --password mypassword --port 9120
  %(prog)s --host 192.168.0.1 --password mypassword --listen 0.0.0.0

Note: Use the local router password, not your TP-Link ID password.
        """
    )
    parser.add_argument(
        "--host", "-H",
        default="192.168.0.1",
        help="Router IP address or hostname (default: 192.168.0.1)"
    )
    parser.add_argument(
        "--password", "-p",
        required=True,
        help="Router admin password (local password, not TP-Link ID)"
    )
    parser.add_argument(
        "--username", "-u",
        default="admin",
        help="Router admin username (default: admin)"
    )
    parser.add_argument(
        "--https",
        action="store_true",
        help="Use HTTPS connection to router"
    )
    parser.add_argument(
        "--verify-ssl",
        action="store_true",
        help="Verify SSL certificate (only with --https)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9120,
        help="Port to expose metrics on (default: 9120)"
    )
    parser.add_argument(
        "--listen",
        default="0.0.0.0",
        help="Address to listen on (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Build router host URL
    router_host = args.host
    if args.https and not router_host.startswith("https://"):
        router_host = f"https://{router_host}"

    collector = TPLinkCollector(
        host=router_host,
        password=args.password,
        username=args.username,
        verify_ssl=args.verify_ssl
    )

    run_server(args.listen, args.port, collector)


if __name__ == "__main__":
    main()
