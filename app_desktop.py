#!/usr/bin/env python3
"""桌面版：独立窗口运行，不依赖浏览器标签页。PyInstaller 入口。"""
from __future__ import annotations

import multiprocessing
import socket
import sys
import threading
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.paths import app_root, user_data_root
from src.logger import setup_logging

setup_logging(log_dir=user_data_root() / "logs")

ROOT = app_root()

PORT = 8765
HOST = "127.0.0.1"


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((HOST, port)) != 0


def _kill_port(port: int) -> None:
    import subprocess

    try:
        out = subprocess.check_output(
            f'netstat -ano | findstr ":{port} " | findstr LISTENING',
            shell=True,
            text=True,
        )
        for line in out.strip().splitlines():
            parts = line.split()
            if parts:
                subprocess.run(
                    ["taskkill", "/F", "/PID", parts[-1]],
                    capture_output=True,
                )
    except Exception:
        pass


def run_server() -> None:
    import uvicorn
    from app.main import app

    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="warning",
    )


def main() -> None:
    import webview

    if not _port_free(PORT):
        _kill_port(PORT)
        time.sleep(0.8)

    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    for _ in range(40):
        if not _port_free(PORT):
            break
        time.sleep(0.15)
    else:
        print("[ERROR] Server failed to start")
        sys.exit(1)

    webview.create_window(
        "不挂科神器",
        f"http://{HOST}:{PORT}",
        width=1120,
        height=740,
        min_size=(900, 560),
        text_select=True,
    )
    webview.start()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
