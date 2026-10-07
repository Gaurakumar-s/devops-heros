"""Tiny demo service for Session 20: /health, /work (burns CPU), /metrics (Prometheus)."""
import os, time, hashlib, threading, logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger("demo-app")

REQUESTS = Counter("demo_app_requests_total", "HTTP requests", ["path", "status"])
LATENCY = Histogram("demo_app_request_seconds", "Request latency", ["path"])
HEALTHY = Gauge("demo_app_healthy", "1 if the app considers itself healthy")
HEALTHY.set(1)

class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="text/plain"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        start = time.time()
        path = self.path.split("?")[0]
        if path == "/metrics":
            self._send(200, generate_latest(), CONTENT_TYPE_LATEST)
            return
        if path == "/health":
            ok = HEALTHY._value.get() == 1
            self._send(200 if ok else 503, b"ok\n" if ok else b"unhealthy\n")
            REQUESTS.labels(path, "200" if ok else "503").inc()
        elif path == "/work":
            d = b"x"
            for _ in range(200000):
                d = hashlib.sha256(d).digest()
            self._send(200, b"done\n")
            REQUESTS.labels(path, "200").inc()
        elif path == "/break":
            HEALTHY.set(0); log.error("health switched to UNHEALTHY by request")
            self._send(200, b"app marked unhealthy\n"); REQUESTS.labels(path, "200").inc()
        elif path == "/fix":
            HEALTHY.set(1); log.info("health restored")
            self._send(200, b"app marked healthy\n"); REQUESTS.labels(path, "200").inc()
        else:
            self._send(404, b"not found\n"); REQUESTS.labels(path, "404").inc()
        LATENCY.labels(path).observe(time.time() - start)
        log.info("%s %s %.3fs", self.command, path, time.time() - start)

    def log_message(self, *a):
        pass

if __name__ == "__main__":
    log.info("demo-app listening on :8000")
    ThreadingHTTPServer(("0.0.0.0", 8000), H).serve_forever()
