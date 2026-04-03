import pytest
from unittest.mock import patch
from utils.network import get_local_ip

def test_get_local_ip_success():
    class MockSocket:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
        def settimeout(self, timeout):
            pass
        def connect(self, addr):
            pass
        def getsockname(self):
            return ("10.0.0.5", 12345)
            
    with patch("socket.socket", return_value=MockSocket()):
        ip = get_local_ip()
        assert ip == "10.0.0.5"

def test_get_local_ip_fallback():
    class ExtMockSocket:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
        def settimeout(self, timeout):
            pass
        def connect(self, addr):
            raise Exception("Network Unreachable")
        def getsockname(self):
            return ("10.0.0.5", 12345)
            
    with patch("socket.socket", return_value=ExtMockSocket()):
        ip = get_local_ip()
        assert ip == "127.0.0.1"
