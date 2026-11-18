"""Launch the Streamlit console alongside the interactive reporting CLI.

Streamlit must run in its own process: it owns an HTTP server and its runtime
must not be imported into the CLI's input loop. Both processes inherit the same
environment, working directory, and project-local configuration.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from threading import Thread
import time
from urllib.error import URLError
from urllib.request import urlopen
import webbrowser


class DashboardLaunchError(RuntimeError):
    """The dashboard cannot start in the current Python environment."""


class DashboardLauncher:
    """Own the local dashboard child process for one CLI session."""

    def __init__(self, project_root: Path, *, open_browser: bool = True) -> None:
        self.project_root = Path(project_root).resolve()
        self.open_browser = open_browser
        self.process: subprocess.Popen | None = None
        self._log = None
        self._monitor: Thread | None = None
        self.url: str | None = None

    @staticmethod
    def _port_in_use(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            return sock.connect_ex(("127.0.0.1", port)) == 0

    @staticmethod
    def _free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]

    def _choose_port(self) -> int:
        configured = os.environ.get("DASHBOARD_PORT", "8501").strip()
        try:
            port = int(configured)
        except ValueError as exc:
            raise DashboardLaunchError("DASHBOARD_PORT must be an integer (1–65535).") from exc
        if not 1 <= port <= 65535:
            raise DashboardLaunchError("DASHBOARD_PORT must be between 1 and 65535.")
        if self._port_in_use(port):
            # An explicit port should never silently start on a different port.
            if "DASHBOARD_PORT" in os.environ:
                raise DashboardLaunchError(f"Port {port} is already in use; change DASHBOARD_PORT.")
            port = self._free_port()
        return port

    def start(self) -> str:
        """Start one background Streamlit server; return its local URL."""
        if self.process is not None:
            raise DashboardLaunchError("Dashboard is already running for this CLI session.")
        if importlib.util.find_spec("streamlit") is None:
            raise DashboardLaunchError(
                "Streamlit is not installed in this Python environment. "
                "Run: python -m pip install -r requirements.txt"
            )
        script = self.project_root / "dashboard.py"
        if not script.is_file():
            raise DashboardLaunchError(f"Dashboard entry point not found: {script}")
        port = self._choose_port()
        self.url = f"http://localhost:{port}"
        cmd = [
            sys.executable, "-m", "streamlit", "run", str(script),
            "--server.address=127.0.0.1",
            f"--server.port={port}",
            "--server.headless=true",
            "--browser.gatherUsageStats=false",
        ]
        self._log = tempfile.TemporaryFile(mode="w+t", encoding="utf-8")
        try:
            self.process = subprocess.Popen(
                cmd, cwd=self.project_root, env=os.environ.copy(),
                stdin=subprocess.DEVNULL, stdout=self._log, stderr=subprocess.STDOUT,
            )
        except OSError as exc:
            self._log.close()
            self._log = None
            raise DashboardLaunchError(f"Could not start Streamlit: {exc}") from exc
        self._monitor = Thread(target=self._wait_until_ready, daemon=True)
        self._monitor.start()
        return self.url

    def _wait_until_ready(self) -> None:
        """Open browser once HTTP is ready and surface early server failures."""
        assert self.process is not None
        port = self.url.rsplit(":", 1)[-1]
        endpoint = f"http://127.0.0.1:{port}/_stcore/health"
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                print(
                    "\n[Dashboard] Server stopped unexpectedly. "
                    "Try: python -m streamlit run dashboard.py",
                    file=sys.stderr,
                )
                return
            try:
                with urlopen(endpoint, timeout=0.5) as result:
                    if result.status == 200:
                        if self.open_browser:
                            webbrowser.open(self.url)
                        return
            except (OSError, URLError):
                pass
            time.sleep(0.25)
        if self.process.poll() is None:
            print(f"\n[Dashboard] Startup is taking longer than expected; check {self.url}.", file=sys.stderr)

    def stop(self) -> None:
        """Stop only the child server launched by this session."""
        process = self.process
        self.process = None
        if process is not None:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            else:
                process.wait()
        if self._monitor is not None:
            # Daemon monitor never holds application shutdown hostage.
            self._monitor = None
        if self._log is not None:
            self._log.close()
            self._log = None
