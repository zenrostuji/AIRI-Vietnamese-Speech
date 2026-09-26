"""Native Windows desktop entry point for AIRI Vietnamese Speech."""
from __future__ import annotations

import json
import threading
import time
from urllib.error import URLError
from urllib.request import urlopen

import uvicorn

from server.main import APP_NAME, app


def run_server(server: uvicorn.Server) -> None:
    server.run()


def existing_server() -> bool:
    """Reuse our server when the launcher is clicked twice."""
    try:
        with urlopen("http://127.0.0.1:23333/health", timeout=1) as response:
            payload = json.load(response)
        return payload.get("service") == APP_NAME
    except (OSError, URLError, ValueError):
        return False


if __name__ == "__main__":
    try:
        import webview
    except ImportError as exc:
        raise SystemExit("pywebview is missing. Run start-ui.bat once to install it.") from exc

    owns_server = not existing_server()
    server = None
    thread = None
    if owns_server:
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=23333, log_level="warning"))
        thread = threading.Thread(target=run_server, args=(server,), daemon=True)
        thread.start()
        deadline = time.monotonic() + 15
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.1)
        if not server.started:
            raise SystemExit("Không thể mở server ở cổng 23333. Hãy đóng ứng dụng đang dùng cổng này rồi thử lại.")
    try:
        webview.create_window(APP_NAME, "http://127.0.0.1:23333/", width=1180, height=860, min_size=(820, 650))
        webview.start()
    finally:
        if owns_server and server is not None and thread is not None:
            server.should_exit = True
            thread.join(timeout=5)
