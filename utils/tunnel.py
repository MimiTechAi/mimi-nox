import subprocess
import threading
import re
import time
import atexit

class TunnelManager:
    _instance = None
    
    def __init__(self):
        self.public_url = None
        self.process = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = TunnelManager()
            atexit.register(cls._instance.cleanup)
        return cls._instance

    def cleanup(self):
        if self.process:
            print("🛑 Terminating Tunnel subprocess to prevent zombies...")
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None

    def start_tunnel(self, port: int):
        if self.process is not None:
            return
            
        print(f"🌍 Starting public remote tunnel for port {port}...")
        self.process = subprocess.Popen(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-R", f"80:localhost:{port}", "nokey@localhost.run", "-T"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        def monitor():
            for line in self.process.stdout:
                # Suche nach https://(.*).lhr.life
                match = re.search(r"https://[a-zA-Z0-9-]+\.lhr\.life", line)
                if match:
                    self.public_url = match.group(0)
                    print(f"✅ Public Tunnel established: {self.public_url}")

        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()

tunnel_manager = TunnelManager.get_instance()
