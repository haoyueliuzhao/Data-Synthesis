from __future__ import annotations

import itertools
import os
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BACKENDS = tuple(
    value.strip().rstrip("/")
    for value in os.environ.get(
        "QWEN_BACKENDS",
        "http://127.0.0.1:8010,http://127.0.0.1:8011,"
        "http://127.0.0.1:8012,http://127.0.0.1:8013",
    ).split(",")
    if value.strip()
)
COUNTER = itertools.count()
COUNTER_LOCK = threading.Lock()
BACKEND_INFLIGHT = {backend: 0 for backend in BACKENDS}
HOP_HEADERS = {"connection", "content-length", "host", "transfer-encoding"}


def _select_backends(method: str) -> tuple[str, ...]:
    with COUNTER_LOCK:
        if method == "POST":
            minimum = min(BACKEND_INFLIGHT.values())
            candidates = tuple(
                backend for backend in BACKENDS if BACKEND_INFLIGHT[backend] == minimum
            )
            backend = candidates[next(COUNTER) % len(candidates)]
            BACKEND_INFLIGHT[backend] += 1
            return (backend,)
        start = next(COUNTER) % len(BACKENDS)
        return tuple(BACKENDS[(start + offset) % len(BACKENDS)] for offset in range(len(BACKENDS)))


def _release_backend(method: str, backend: str) -> None:
    if method != "POST":
        return
    with COUNTER_LOCK:
        BACKEND_INFLIGHT[backend] -= 1
        if BACKEND_INFLIGHT[backend] < 0:
            raise RuntimeError("replica proxy in-flight accounting underflow")


class ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802
        self._proxy()

    def do_POST(self) -> None:  # noqa: N802
        self._proxy()

    def _proxy(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else None
        last_error: Exception | None = None
        for backend in _select_backends(self.command):
            headers = {
                key: value
                for key, value in self.headers.items()
                if key.lower() not in HOP_HEADERS
            }
            request = urllib.request.Request(
                backend + self.path,
                data=body,
                headers=headers,
                method=self.command,
            )
            try:
                with urllib.request.urlopen(request, timeout=840) as response:
                    payload = response.read()
                    self.send_response(response.status)
                    for key, value in response.headers.items():
                        if key.lower() not in HOP_HEADERS:
                            self.send_header(key, value)
                    self.send_header("Content-Length", str(len(payload)))
                    self.send_header("X-VTDO-Backend", backend)
                    self.end_headers()
                    self.wfile.write(payload)
                    return
            except urllib.error.HTTPError as error:
                payload = error.read()
                if error.code < 500:
                    self.send_response(error.code)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.send_header("X-VTDO-Backend", backend)
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                last_error = error
            except (OSError, TimeoutError) as error:
                last_error = error
            finally:
                _release_backend(self.command, backend)
        payload = (f'{{"detail":"all local backends unavailable:{last_error!s}"}}').encode()
        self.send_response(503)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8020), ProxyHandler)
    server.daemon_threads = True
    server.serve_forever()
