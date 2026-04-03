import socket

def get_local_ip() -> str:
    """Returns the local IPv4 address of the machine on the local network."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(2.0)
            # connect to an external server but doesn't actually send any data on DGRAM
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        # Fallback if offline
        return "127.0.0.1"
