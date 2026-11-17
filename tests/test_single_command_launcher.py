"""Offline tests for one-command startup (no real browser or server required)."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import main
from campus_safety.dashboard.launcher import DashboardLauncher, DashboardLaunchError


class SingleCommandMainTests(unittest.TestCase):
    def test_both_interfaces_start_with_one_command(self):
        events = []
        app = Mock()
        app.run.side_effect = lambda: events.append("cli")
        with patch.object(main.CampusSafetyApplication, "create_default", return_value=app), \
             patch.object(main, "DashboardLauncher") as server:
            server.return_value.start.side_effect = lambda: (events.append("dashboard") or "http://localhost:8501")
            server.return_value.stop.side_effect = lambda: events.append("stop")
            self.assertEqual(main.main(), 0)
            server.assert_called_once_with(main.PROJECT_ROOT, open_browser=True)
        self.assertEqual(events, ["dashboard", "cli", "stop"])

    def test_cli_only_never_launches_server(self):
        with patch.object(main.CampusSafetyApplication, "create_default", return_value=Mock()), \
             patch.object(main, "DashboardLauncher") as server:
            self.assertEqual(main.main(launch_dashboard=False), 0)
            server.assert_not_called()

    def test_missing_dashboard_keeps_cli_available(self):
        with patch.object(main.CampusSafetyApplication, "create_default", return_value=Mock()) as app, \
             patch.object(main, "DashboardLauncher") as server:
            server.return_value.start.side_effect = DashboardLaunchError("not installed")
            self.assertEqual(main.main(), 0)
            app.return_value.run.assert_called_once()
            server.return_value.stop.assert_not_called()

    def test_cleanup_on_cli_error(self):
        app = Mock()
        app.run.side_effect = KeyboardInterrupt()
        with patch.object(main.CampusSafetyApplication, "create_default", return_value=app), \
             patch.object(main, "DashboardLauncher") as server:
            server.return_value.start.return_value = "http://localhost:8501"
            self.assertEqual(main.main(), main.EXIT_INTERRUPTED)
            server.return_value.stop.assert_called_once()


class DashboardProcessTests(unittest.TestCase):
    def test_subprocess_uses_same_python_and_dashboard_script(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "dashboard.py").write_text("# placeholder\n", encoding="utf-8")
            server = DashboardLauncher(Path(folder), open_browser=False)
            child = Mock()
            child.poll.return_value = None
            with patch("campus_safety.dashboard.launcher.importlib.util.find_spec", return_value=object()), \
                 patch("campus_safety.dashboard.launcher.subprocess.Popen", return_value=child) as popen, \
                 patch("campus_safety.dashboard.launcher.Thread"), \
                 patch.object(server, "_choose_port", return_value=12345):
                self.assertEqual(server.start(), "http://localhost:12345")
                args, kwargs = popen.call_args
                self.assertEqual(args[0][1:4], ["-m", "streamlit", "run"])
                self.assertEqual(args[0][4], str(Path(folder) / "dashboard.py"))
                self.assertIn("--server.port=12345", args[0])
                self.assertEqual(kwargs["cwd"], Path(folder))
                self.assertEqual(kwargs["env"].get("PATH"), __import__("os").environ.get("PATH"))
                server.stop()
                child.terminate.assert_called_once()

    def test_explicit_busy_port_does_not_connect_to_another_service(self):
        server = DashboardLauncher(Path(__file__).resolve().parents[1])
        with patch.dict("os.environ", {"DASHBOARD_PORT": "8501"}), \
             patch.object(server, "_port_in_use", return_value=True):
            with self.assertRaisesRegex(DashboardLaunchError, "already in use"):
                server._choose_port()

    def test_default_busy_port_uses_available_port(self):
        server = DashboardLauncher(Path(__file__).resolve().parents[1])
        with patch.dict("os.environ", {"DASHBOARD_PORT": ""}), \
             patch.object(server, "_port_in_use", return_value=True), \
             patch.object(server, "_free_port", return_value=41001):
            # Empty explicit values aren't valid ports.
            with self.assertRaises(DashboardLaunchError):
                server._choose_port()
        with patch.dict("os.environ", {}, clear=True), \
             patch.object(server, "_port_in_use", return_value=True), \
             patch.object(server, "_free_port", return_value=41001):
            self.assertEqual(server._choose_port(), 41001)


if __name__ == "__main__":
    unittest.main()
