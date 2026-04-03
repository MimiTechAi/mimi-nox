import pytest
from fastapi.testclient import TestClient
from server.main import create_app

@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)

def test_cors_allow_all(client):
    # Simulate a request from a mobile device on the local network connecting to the mobile endpoint
    headers = {
        "Origin": "http://192.168.178.50:8765",
        "Access-Control-Request-Method": "GET",
    }
    
    # Pre-flight OPTIONS request
    response = client.options("/api/mobile/qr", headers=headers)
    assert response.status_code == 200
    
    # Check explicitly that global CORS applies and doesn't restrict
    cors_allow_origin = response.headers.get("access-control-allow-origin")
    assert cors_allow_origin == "*" or cors_allow_origin == "http://192.168.178.50:8765"
    
    cors_allow_methods = response.headers.get("access-control-allow-methods")
    assert cors_allow_methods and ("*" in cors_allow_methods or "GET" in cors_allow_methods)
