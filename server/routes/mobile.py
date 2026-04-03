"""server/routes/mobile.py – GET /api/mobile/qr"""

import io
import base64
import time
import qrcode
from fastapi import APIRouter, Request
from pydantic import BaseModel

from utils.network import get_local_ip
from utils.tunnel import tunnel_manager

router = APIRouter(tags=["Mobile"])

# Global state for connection tracking
_device_connected = False

class MobileQRResponse(BaseModel):
    url: str
    qr_base64: str

@router.get("/mobile/qr", response_model=MobileQRResponse)
def get_mobile_qr(request: Request) -> MobileQRResponse:
    """Returns the local or public URL and a base64 encoded QR code for mobile pairing."""
    global _device_connected
    _device_connected = False  # Reset on new pairing request
    port = request.url.port or 8765
    
    # Trigger public SSH tunnel lazily
    tunnel_manager.start_tunnel(port)
    
    # Wait up to 3 seconds for it to assign a URL
    for _ in range(30):
        if tunnel_manager.public_url:
            break
        time.sleep(0.1)
        
    target_url = tunnel_manager.public_url
    if not target_url:
        ip = get_local_ip()
        target_url = f"http://{ip}:{port}"
    
    # Mobile users get the clean chat-only page
    mobile_url = f"{target_url}/mobile.html"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(mobile_url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    qr_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    
    return MobileQRResponse(url=mobile_url, qr_base64=qr_base64)


@router.post("/mobile/ping")
def mobile_ping():
    """Triggered by the PWA when it opens on a smartphone."""
    global _device_connected
    _device_connected = True
    return {"status": "ok"}


@router.get("/mobile/status")
def mobile_status():
    """Polled by the Desktop UI while the QR code is open."""
    global _device_connected
    return {"connected": _device_connected}
