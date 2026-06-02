"""
plaxis_connect.py — Kết nối tới PLAXIS 2D đang mở qua Remote Scripting.

Yêu cầu:
  1. PLAXIS 2D đã mở + có file project loaded
  2. Expert > Configure remote scripting server → Start server (port 10000)
  3. Password set trong dialog đó
  4. Set env var PLAXIS_PASSWORD trước khi chạy (an toàn):
        $env:PLAXIS_PASSWORD = '+g=GW5R>A9WY?He7'      # PowerShell
        set PLAXIS_PASSWORD=+g=GW5R>A9WY?He7           # CMD

Chạy: `python scripts/plaxis_connect.py`
      → in trạng thái Input + Output server + project info
"""
from __future__ import annotations
import os
import sys
from typing import Optional

try:
    from plxscripting.easy import new_server
except ImportError as e:
    print(f"plxscripting chưa cài: {e}")
    print("  pip install plxscripting")
    sys.exit(1)

PASSWORD = os.environ.get("PLAXIS_PASSWORD", "")
PORT_INPUT = int(os.environ.get("PLAXIS_PORT_INPUT", "10000"))
PORT_OUTPUT = int(os.environ.get("PLAXIS_PORT_OUTPUT", "10001"))
HOST = os.environ.get("PLAXIS_HOST", "localhost")


def connect_input(host: str = HOST, port: int = PORT_INPUT,
                   password: Optional[str] = None) -> tuple:
    """Trả về (s_i, g_i) — server object + global namespace của PLAXIS Input."""
    pwd = password if password is not None else PASSWORD
    if not pwd:
        print("CẢNH BÁO: PLAXIS_PASSWORD trống — set env var trước khi chạy.")
    s_i, g_i = new_server(host, port, password=pwd)
    return s_i, g_i


def connect_output(host: str = HOST, port: int = PORT_OUTPUT,
                    password: Optional[str] = None) -> tuple:
    """Trả về (s_o, g_o) — server object + global namespace của PLAXIS Output."""
    pwd = password if password is not None else PASSWORD
    s_o, g_o = new_server(host, port, password=pwd)
    return s_o, g_o


def test_connection() -> None:
    """In trạng thái kết nối + info project hiện tại."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
    print("=" * 60)
    print(f"PLAXIS 2D Remote Scripting — Connect Test")
    print("=" * 60)
    print(f"Host          : {HOST}")
    print(f"Port (Input)  : {PORT_INPUT}")
    print(f"Port (Output) : {PORT_OUTPUT}")
    print(f"Password set  : {'YES (' + str(len(PASSWORD)) + ' chars)' if PASSWORD else 'NO — set env var PLAXIS_PASSWORD'}")
    print("-" * 60)

    # 1. Test Input
    try:
        s_i, g_i = connect_input()
        print(f"INPUT  Kết nối OK")
        # In thông tin project
        try:
            proj_name = g_i.ProjectInformation.Title.value
            proj_id = g_i.ProjectInformation.ProjectID.value
            print(f"       Project       : {proj_name}")
            print(f"       Project ID    : {proj_id}")
        except Exception as e:
            print(f"       (Không đọc được ProjectInformation: {e})")
        # Số boreholes
        try:
            n_bh = len(g_i.Boreholes)
            print(f"       Boreholes     : {n_bh}")
        except Exception:
            pass
        # Số soil materials
        try:
            n_mat = len(g_i.SoilMaterials)
            print(f"       SoilMaterials : {n_mat}")
        except Exception:
            pass
        # Số phases
        try:
            n_ph = len(g_i.Phases)
            print(f"       Phases        : {n_ph}")
        except Exception:
            pass
        s_i.close()
    except Exception as e:
        print(f"INPUT  Kết nối FAIL: {type(e).__name__}: {e}")
        print(f"       Kiểm tra: Server đã bấm Start trong Configure remote scripting chưa?")
        return

    # 2. Test Output (có thể chưa mở Output viewer)
    try:
        s_o, g_o = connect_output()
        print(f"OUTPUT Kết nối OK")
        s_o.close()
    except Exception as e:
        print(f"OUTPUT Kết nối FAIL: {type(e).__name__}: {e}")
        print(f"       (Output Viewer chưa mở — bình thường nếu chưa Calculate)")

    print("=" * 60)


if __name__ == "__main__":
    test_connection()
