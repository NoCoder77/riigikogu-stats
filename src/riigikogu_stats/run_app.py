"""Launcher for the Riigikogu Stats app. When run as a PyInstaller bundle, loads .env from the exe directory and serves the built UI."""
from __future__ import annotations

import io
import os
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path

from dotenv import load_dotenv

from .api.app import app


def _pause_on_error() -> None:
    """Keep console window open so user can read the error (Windows exe)."""
    # Frozen GUI exe: stdin is None; input() raises RuntimeError. Use sleep path when stdin unavailable.
    if sys.stdin is None:
        try:
            print("\n(Window will close in 15 seconds.)")
        except Exception:
            pass
        time.sleep(15)
        return
    try:
        input("Press Enter to close...")
    except (EOFError, RuntimeError):
        # No stdin or input(): lost sys.stdin
        try:
            print("\n(Window will close in 15 seconds.)")
        except Exception:
            pass
        time.sleep(15)


def _main() -> None:
    frozen = getattr(sys, "frozen", False)
    # Fix for frozen exe (console=False): stdout/stderr are None; uvicorn's logging calls .isatty() on them.
    if frozen and (sys.stdout is None or sys.stderr is None):
        _safe_stream = io.StringIO()
        if sys.stdout is None:
            sys.stdout = _safe_stream
        if sys.stderr is None:
            sys.stderr = _safe_stream
    _launcher_port: list[int] = [8000]  # port for server; browser thread reads after delay
    if frozen:
        exe_dir = Path(sys.executable).parent
        if not (os.environ.get("DATABASE_URL") or "").strip():
            # Prefer existing DB next to the exe; otherwise use a persistent app-data path
            # so replacing the exe folder does not wipe data.
            beside_exe = exe_dir / "riigikogu.db"
            if beside_exe.is_file():
                db_path = beside_exe
            else:
                app_data = Path(os.environ.get("LOCALAPPDATA") or exe_dir) / "RiigikoguStats"
                app_data.mkdir(parents=True, exist_ok=True)
                db_path = app_data / "riigikogu.db"
            os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
        load_dotenv(exe_dir / ".env")
        # UI is mounted in app.py from _get_ui_static_dir()

    if frozen:

        def open_browser() -> None:
            time.sleep(1.5)
            webbrowser.open(f"http://127.0.0.1:{_launcher_port[0]}")
        threading.Thread(target=open_browser, daemon=True).start()

    import uvicorn
    PORTS = list(range(8000, 8011))  # 8000..8010
    last_port = PORTS[-1]
    for port in PORTS:
        _launcher_port[0] = port
        try:
            uvicorn.run(app, host="127.0.0.1", port=port)
            break  # normal server shutdown
        except SystemExit as e:
            if e.code == 1 and port < last_port:
                print(f"Port {port} in use, trying {port + 1}...")
                continue
            # give up or non-port failure
            print("\nServer exited with code 1. No free port in 8000–8010.\n")
            traceback.print_exc()
            _pause_on_error()
            raise
        except Exception:
            traceback.print_exc()
            _pause_on_error()
            raise
        except BaseException as e:
            if type(e).__name__ == "SystemExit" and str(e) == "1":
                print("\nServer exited with code 1. Port may be in use.\n")
            traceback.print_exc()
            _pause_on_error()
            raise


if __name__ == "__main__":
    _main()
