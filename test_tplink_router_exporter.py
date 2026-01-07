#!/usr/bin/env python3
"""Tests for the TP-Link Prometheus exporter."""

import unittest
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO

from tplinkrouterc6u import Connection

from tplink_router_exporter import (
    TPLinkCollector,
    MetricsHandler,
    get_connection_label,
)


class TestConnectionLabel(unittest.TestCase):
    """Tests for get_connection_label function."""

    def test_wifi_2g(self):
        self.assertEqual(get_connection_label(Connection.HOST_2G), "wifi_2g")

    def test_wifi_5g(self):
        self.assertEqual(get_connection_label(Connection.HOST_5G), "wifi_5g")

    def test_wired(self):
        self.assertEqual(get_connection_label(Connection.WIRED), "wired")

    def test_guest_2g(self):
        self.assertEqual(get_connection_label(Connection.GUEST_2G), "guest_2g")

    def test_none(self):
        self.assertEqual(get_connection_label(None), "unknown")


class MockDevice:
    """Mock device for testing."""

    def __init__(
        self,
        macaddr="AA:BB:CC:DD:EE:FF",
        hostname="test-device",
        ipaddr="192.168.0.100",
        conn_type=Connection.HOST_5G,
        signal=-50,
        down_speed=1000,
        up_speed=500,
        packets_sent=1000,
        packets_received=2000,
        active=True,
    ):
        self.macaddr = macaddr
        self.hostname = hostname
        self.ipaddr = ipaddr
        self.type = conn_type
        self.signal = signal
        self.down_speed = down_speed
        self.up_speed = up_speed
        self.packets_sent = packets_sent
        self.packets_received = packets_received
        self.active = active


class MockStatus:
    """Mock router status for testing."""

    def __init__(self):
        self.wan_ipv4_addr = "1.2.3.4"
        self.lan_ipv4_addr = "192.168.0.1"
        self.conn_type = "dhcp"
        self.cpu_usage = 0.25
        self.mem_usage = 0.45
        self.clients_total = 5
        self.wifi_clients_total = 3
        self.wired_total = 2
        self.guest_clients_total = 0
        self.iot_clients_total = 0
        self.wifi_2g_enable = True
        self.wifi_5g_enable = True
        self.wifi_6g_enable = None
        self.guest_2g_enable = False
        self.guest_5g_enable = False
        self.guest_6g_enable = None
        self.devices = [
            MockDevice(),
            MockDevice(
                macaddr="11:22:33:44:55:66",
                hostname="wired-device",
                ipaddr="192.168.0.101",
                conn_type=Connection.WIRED,
                signal=None,
            ),
        ]


class TestTPLinkCollector(unittest.TestCase):
    """Tests for TPLinkCollector class."""

    def test_init(self):
        """Test collector initialization."""
        collector = TPLinkCollector(
            host="192.168.0.1",
            password="testpass",
            username="admin",
        )
        self.assertEqual(collector.host, "192.168.0.1")
        self.assertEqual(collector.password, "testpass")
        self.assertEqual(collector.username, "admin")

    @patch("tplink_router_exporter.TplinkRouterProvider")
    def test_collect_success(self, mock_provider):
        """Test successful metric collection."""
        # Setup mock
        mock_router = MagicMock()
        mock_provider.get_client.return_value = mock_router
        mock_router.get_status.return_value = MockStatus()

        collector = TPLinkCollector(
            host="192.168.0.1",
            password="testpass",
        )

        # Collect metrics
        metrics = list(collector.collect())

        # Verify we got metrics
        self.assertTrue(len(metrics) > 0)

        # Check for expected metric names
        metric_names = [m.name for m in metrics]
        self.assertIn("tplink_router_info", metric_names)
        self.assertIn("tplink_cpu_usage_ratio", metric_names)
        self.assertIn("tplink_memory_usage_ratio", metric_names)
        self.assertIn("tplink_clients_total", metric_names)
        self.assertIn("tplink_wifi_clients_total", metric_names)
        self.assertIn("tplink_wired_clients_total", metric_names)
        self.assertIn("tplink_device_active", metric_names)
        self.assertIn("tplink_scrape_success", metric_names)

        # Check scrape success
        scrape_success = next(m for m in metrics if m.name == "tplink_scrape_success")
        self.assertEqual(scrape_success.samples[0].value, 1)

    @patch("tplink_router_exporter.TplinkRouterProvider")
    def test_collect_failure(self, mock_provider):
        """Test metric collection on router failure."""
        mock_router = MagicMock()
        mock_provider.get_client.return_value = mock_router
        mock_router.authorize.side_effect = Exception("Connection failed")

        collector = TPLinkCollector(
            host="192.168.0.1",
            password="testpass",
        )

        # Collect metrics
        metrics = list(collector.collect())

        # Should still return scrape metrics
        metric_names = [m.name for m in metrics]
        self.assertIn("tplink_scrape_success", metric_names)
        self.assertIn("tplink_scrape_duration_seconds", metric_names)

        # Scrape should indicate failure
        scrape_success = next(m for m in metrics if m.name == "tplink_scrape_success")
        self.assertEqual(scrape_success.samples[0].value, 0)


class TestMetricsHandler(unittest.TestCase):
    """Tests for MetricsHandler class."""

    def _make_request(self, path):
        """Create a mock request handler for testing."""
        handler = Mock(spec=MetricsHandler)
        handler.path = path
        handler.wfile = BytesIO()
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        handler.send_error = Mock()
        return handler

    def test_health_endpoint(self):
        """Test health endpoint returns OK."""
        handler = self._make_request("/health")
        MetricsHandler._serve_health(handler)
        handler.send_response.assert_called_with(200)

    def test_index_endpoint(self):
        """Test index page is served."""
        handler = self._make_request("/")
        MetricsHandler._serve_index(handler)
        handler.send_response.assert_called_with(200)


if __name__ == "__main__":
    unittest.main()
