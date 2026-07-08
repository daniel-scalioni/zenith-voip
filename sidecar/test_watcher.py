import os
import socket
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import watcher


class TestGetExternalIp(unittest.TestCase):
    def test_returns_mock_ip_when_set(self):
        result = watcher.get_external_ip("http://ignored", mock_ip="1.2.3.4")
        self.assertEqual(result, "1.2.3.4")

    def test_returns_ip_from_http_endpoint(self):
        mock_resp = MagicMock()
        mock_resp.text = "  189.112.222.244\n"
        mock_resp.raise_for_status = MagicMock()
        with patch("watcher.requests.get", return_value=mock_resp):
            result = watcher.get_external_ip("http://endpoint.example", mock_ip=None)
        self.assertEqual(result, "189.112.222.244")

    def test_falls_back_to_getsockname_on_http_failure(self):
        import requests as req
        fake_ip = "200.100.50.25"

        def fake_socket(*args, **kwargs):
            sock = MagicMock()
            sock.__enter__ = lambda s: s
            sock.__exit__ = MagicMock(return_value=False)
            sock.getsockname.return_value = (fake_ip, 0)
            return sock

        with patch("watcher.requests.get", side_effect=req.exceptions.RequestException("timeout")):
            with patch("watcher.socket.socket", fake_socket):
                result = watcher.get_external_ip("http://endpoint.example", mock_ip=None)
        self.assertEqual(result, fake_ip)

    def test_returns_none_when_all_methods_fail(self):
        import requests as req

        def bad_socket(*args, **kwargs):
            raise OSError("no route")

        with patch("watcher.requests.get", side_effect=req.exceptions.RequestException("fail")):
            with patch("watcher.socket.socket", bad_socket):
                result = watcher.get_external_ip("http://endpoint.example", mock_ip=None)
        self.assertIsNone(result)


class TestWriteVarsXml(unittest.TestCase):
    def test_creates_file_with_both_directives(self):
        ip = "189.112.222.244"
        with tempfile.TemporaryDirectory() as tmp:
            watcher.write_vars_xml(ip, tmp)
            path = os.path.join(tmp, "vars-external-ip.xml")
            self.assertTrue(os.path.exists(path))
            content = open(path).read()
            self.assertIn(f'data="external_sip_ip={ip}"', content)
            self.assertIn(f'data="external_rtp_ip={ip}"', content)

    def test_overwrites_on_ip_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            watcher.write_vars_xml("1.1.1.1", tmp)
            watcher.write_vars_xml("2.2.2.2", tmp)
            content = open(os.path.join(tmp, "vars-external-ip.xml")).read()
            self.assertIn("2.2.2.2", content)
            self.assertNotIn("1.1.1.1", content)


if __name__ == "__main__":
    unittest.main()
