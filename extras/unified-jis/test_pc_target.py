import json
from pathlib import Path
import tempfile
import unittest

from frame_jis_pc import pc_target


class Target(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.home = Path(self.directory.name)
        self.proc = self.home / 'proc'
        self.state = self.home / '.local/state/frame-desktop-overlay'
        self.state.mkdir(parents=True)
        self.key = 'gamescope.gamescope-0.window.301'
        self.panel = dict(schema_version=1, input='windows', overlayKey=self.key,
                          instance='one', hostPid=42, processStart='1234')
        self.owner = dict(application='com.moonlight_stream.Moonlight', instance='one')
        process = self.proc / '42'
        (process / 'root').mkdir(parents=True)
        (process / 'stat').write_text('42 (name with parentheses (inside)) ' +
                                     ' '.join(['S'] + ['0']*18 + ['1234']))
        (process / 'root/.flatpak-info').write_text('[Instance]\ninstance-id=one\n')
        self.save()

    def save(self):
        (self.state / 'panel.json').write_text(json.dumps(self.panel))
        (self.state / 'owned-instance.json').write_text(json.dumps(self.owner))

    def test_exact_live_panel_uses_pc_profile(self):
        self.assertTrue(pc_target(self.key, self.home, self.proc))
        self.assertFalse(pc_target('gamescope.gamescope-0.window.56', self.home, self.proc))

    def test_reused_pid_cannot_retain_pc_ownership(self):
        self.panel['processStart'] = 'older'
        self.save()
        self.assertFalse(pc_target(self.key, self.home, self.proc))

    def test_different_instance_or_application_is_not_pc(self):
        for field, value in [('instance', 'two'), ('application', 'other')]:
            previous = self.owner[field]
            self.owner[field] = value
            self.save()
            self.assertFalse(pc_target(self.key, self.home, self.proc))
            self.owner[field] = previous

    def test_missing_or_malformed_registration_does_not_claim_desktop(self):
        (self.state / 'panel.json').write_text('{broken')
        self.assertFalse(pc_target(self.key, self.home, self.proc))
        self.assertTrue(pc_target('valve.steam.desktopgame.2000000420', self.home, self.proc))

    def test_wrong_sandbox_and_untyped_pid_are_rejected(self):
        (self.proc / '42/root/.flatpak-info').write_text('[Instance]\ninstance-id=other\n')
        self.assertFalse(pc_target(self.key, self.home, self.proc))
        self.panel['hostPid'] = '42'
        self.save()
        self.assertFalse(pc_target(self.key, self.home, self.proc))


if __name__ == '__main__':
    unittest.main()
