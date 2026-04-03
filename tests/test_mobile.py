import pytest
import re
from fastapi.testclient import TestClient
from server.main import create_app
from unittest.mock import patch

@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)

def test_mobile_qr_payload_format(client):
    with patch("server.routes.mobile.get_local_ip", return_value="10.0.0.99"):
        response = client.get("/api/mobile/qr")
        assert response.status_code == 200
        data = response.json()
        
        target_url = data["url"]
        qr_base64 = data["qr_base64"]
        
        # Test URL format
        match = re.fullmatch(r"http://\d{1,3}(?:\.\d{1,3}){3}:\d+", target_url)
        assert match is not None, f"URL {target_url} does not match expected format"
        
        # The exact test dummy domain for TestClient defaults to 80 (testserver) or fallback 8765
        assert target_url in ("http://10.0.0.99:80", "http://10.0.0.99:8765")
        
        # Verify base64 starts as a valid PNG payload or is decently sized
        assert len(qr_base64) > 100 
        assert qr_base64.startswith("iVBORw0K") # Typical PNG base64 header
