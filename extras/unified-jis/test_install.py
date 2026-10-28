"""Install/startup and restoration use temporary files and no real services."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import runpy
from subprocess import CompletedProcess
import tempfile
import unittest
from unittest.mock import patch

import patch_runtime

ADDON = Path(__file__).resolve().parent
UNIT = 'frame-jis-keyboard.service'


class Install(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='jis-install-')
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        release = self.home / '.local/share/framekeyboard/current/bin'
        release.mkdir(parents=True)
        (release / 'framekeyboard').write_bytes(b'test executable, never run')
        bridge = release.parent / 'share/framekeyboard/bridge'
        bridge.mkdir(parents=True)
        (bridge / 'steam_bridge.js').write_bytes(b'// test bridge')
        config = self.home / '.config/framekeyboard'
        config.mkdir(parents=True)
        self.preferences = json.dumps({'schema_version': 1, 'active': {
            'layout': 'ja-jis-frame-full', 'language': 'ja-jis-frame', 'theme': 'graphite'}})
        (config / 'config.json').write_text(self.preferences, encoding='utf-8')
        self.unit = self.home / '.config/systemd/user' / UNIT
        self.unit.parent.mkdir(parents=True)
        self.unit.write_text('previous user unit\n', encoding='utf-8')
        self.enabled_before = False
        self.vr_running = True
        self.commands = []

    def command(self, args, **kwargs):
        self.commands.append(args)
        if args[-1] == '--help':
            return CompletedProcess(args, 0, stdout='Full Keyboard for Steam Frame 0.8.2\n')
        if args[:3] == ['systemctl', '--user', 'is-enabled']:
            return CompletedProcess(args, 0 if self.enabled_before else 1)
        if args[:3] == ['systemctl', '--user', 'is-active']:
            return CompletedProcess(args, 0 if self.vr_running else 3)
        return CompletedProcess(args, 0)

    def execute(self, script):
        output = io.StringIO()
        with patch.object(Path, 'home', return_value=self.home), \
             patch.object(Path, 'symlink_to'), \
             patch.object(os, 'getuid', return_value=1000, create=True), \
             patch.object(patch_runtime, 'patch'), \
             patch('subprocess.run', side_effect=self.command), redirect_stdout(output):
            runpy.run_path(str(ADDON / script), run_name='__main__')
        return output.getvalue()

    def test_install_enables_and_starts_on_running_steamvr(self):
        result = json.loads(self.execute('install.py'))
        self.assertIn(['systemctl', '--user', 'enable', UNIT], self.commands)
        self.assertIn(['systemctl', '--user', 'start', UNIT], self.commands)
        self.assertTrue(result['startupRequested'])
        self.assertTrue(result['coordinatorStarted'])
        self.assertEqual((self.home / '.config/framekeyboard/config.json').read_text(), self.preferences)

    def test_install_before_steamvr_enables_without_starting(self):
        self.vr_running = False
        result = json.loads(self.execute('install.py'))
        self.assertIn(['systemctl', '--user', 'enable', UNIT], self.commands)
        self.assertNotIn(['systemctl', '--user', 'start', UNIT], self.commands)
        self.assertTrue(result['startupRequested'])
        self.assertFalse(result['coordinatorStarted'])

    def test_restore_returns_previously_disabled_unit_and_contents(self):
        self.execute('install.py')
        self.commands.clear()
        self.execute('restore.py')
        self.assertIn(['systemctl', '--user', 'disable', UNIT], self.commands)
        self.assertNotIn(['systemctl', '--user', 'enable', UNIT], self.commands)
        self.assertEqual(self.unit.read_text(), 'previous user unit\n')

    def test_restore_keeps_preexisting_startup_enabled(self):
        self.enabled_before = True
        self.execute('install.py')
        self.commands.clear()
        self.execute('restore.py')
        self.assertIn(['systemctl', '--user', 'enable', UNIT], self.commands)
        self.assertEqual(self.unit.read_text(), 'previous user unit\n')


if __name__ == '__main__':
    unittest.main()
