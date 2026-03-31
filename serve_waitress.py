from __future__ import annotations

import os
import socket

from dotenv import load_dotenv
from waitress import serve

from app import create_app


load_dotenv()

app = create_app()


def _to_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _get_local_ip() -> str:
    """
    Jaribu kupata LAN IP ya machine hii ili iwe rahisi kuwapa wenzako URL ya kuingia.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Haitumi data kweli, ni trick ya kupata outbound local IP
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        sock.close()


if __name__ == "__main__":
    host = os.getenv("WAITRESS_HOST", "0.0.0.0").strip() or "0.0.0.0"
    port = _to_int(os.getenv("WAITRESS_PORT", "8000"), 8000)
    threads = _to_int(os.getenv("WAITRESS_THREADS", "8"), 8)

    local_ip = _get_local_ip()

    print("=" * 72)
    print("AFYA ERP is starting with Waitress")
    print(f"Host    : {host}")
    print(f"Port    : {port}")
    print(f"Threads : {threads}")
    print("-" * 72)
    print(f"Local   : http://127.0.0.1:{port}")
    print(f"LAN     : http://{local_ip}:{port}")
    print("=" * 72)

    serve(
        app,
        host=host,
        port=port,
        threads=threads,
    )