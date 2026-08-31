"""Native Windows desktop entry point for AIRI Vietnamese Speech."""
from __future__ import annotations

import threading
import time

import uvicorn

from server.main import APP_NAME, app


def run_server(server: uvicorn.Server) -> None:
    server.run()


if __name__ == "__main__":
    try:
        import webview
    except ImportError as exc:
        raise SystemExit("pywebview is missing. Run start-ui.bat once to install it.") from exc

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=23333, log_level="warning"))
    thread = threading.Thread(target=run_server, args=(server,), daemon=True)
    thread.start()
    deadline = time.monotonic() + 12
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.1)
    if not server.started:
        raise SystemExit("Local server could not start. Port 23333 may already be in use.")
    try:
        webview.create_window(APP_NAME, "http://127.0.0.1:23333/", width=1180, height=860, min_size=(820, 650))
        webview.start()
    finally:
        server.should_exit = True
        thread.join(timeout=5)
