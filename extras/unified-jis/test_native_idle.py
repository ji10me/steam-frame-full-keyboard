"""Prepare local summons without delaying footer polling or losing Steam fallback."""
import os
from pathlib import Path
import runpy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

with patch.object(os, 'getuid', return_value=1000, create=True), patch.dict(os.environ):
    module = runpy.run_path(str(Path(__file__).with_name('frame-jis-keyboard')), run_name='inspect_only')
idle = module['native_idle']
NATIVE = module['NATIVE']
LOCAL = 'gamescope.gamescope-0.window.42'
STEAM = 'valve.steam.gamepadui.main'


class Standby(unittest.TestCase):
    def check_idle(self, running, status, footer, code='0', pid=123):
        self.command = Mock(return_value=SimpleNamespace(stdout=code))
        self.start = Mock()
        self.bindings = patch.dict(idle.__globals__, active=Mock(return_value=running),
            run=self.command, native_start=self.start, NATIVE_PROCESS_PID=pid, NATIVE_START_AT=99)
        self.bindings.start()
        self.addCleanup(self.bindings.stop)
        return idle(status, footer)

    def test_idle_local_focus_starts_shutdown_without_blocking_footer(self):
        self.assertTrue(self.check_idle(True, {'open': False}, {'localFocus': LOCAL}))
        self.command.assert_called_once_with(
            ['systemctl', '--user', 'stop', '--no-block', NATIVE], check=True)
        self.start.assert_not_called()
        self.assertEqual(idle.__globals__['NATIVE_PROCESS_PID'], 0)
        self.assertEqual(idle.__globals__['NATIVE_START_AT'], 0)

    def test_repeated_local_summons_leave_steam_parked(self):
        self.assertTrue(self.check_idle(False, {'open': False}, {'localFocus': LOCAL}))
        self.start.assert_not_called()
        self.assertEqual(self.command.call_count, 1)  # Exit classification, no stop/start cycle.

    def test_open_native_request_is_never_parked(self):
        self.assertTrue(self.check_idle(True, {'open': True, 'key': STEAM}, {'localFocus': LOCAL}))
        self.command.assert_not_called()

    def test_steam_request_resumes_with_its_exact_owner(self):
        self.assertTrue(self.check_idle(False, {'open': True, 'key': STEAM}, {'localFocus': ''}))
        self.start.assert_called_once_with(STEAM)

    def test_unknown_focus_or_missing_router_preserves_steam_readiness(self):
        for footer in (None, {}, {'localFocus': 'unknown'}, {'localFocus': STEAM}):
            with self.subTest(footer=footer):
                self.assertTrue(self.check_idle(False, {'open': False}, footer))
                self.start.assert_called_once_with('')

    def test_settings_quit_stops_coordinator_even_on_local_focus(self):
        self.assertFalse(self.check_idle(False, {'open': False}, {'localFocus': LOCAL}, code='3'))
        self.start.assert_not_called()

    def test_explicit_coordinator_restart_does_not_replay_previous_quit(self):
        self.assertTrue(self.check_idle(False, {'open': False}, None, code='3', pid=0))
        self.start.assert_called_once_with('')


if __name__ == '__main__':
    unittest.main()
