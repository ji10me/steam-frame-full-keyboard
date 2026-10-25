"""Recognize an optional, live PC stream without treating every local app as PC."""
import configparser
import json
from pathlib import Path
import re

LEGACY_PC = 'valve.steam.desktopgame.2000000420'


def pc_target(key, home=Path.home(), proc=Path('/proc')):
    if key == LEGACY_PC:
        return True
    if not isinstance(key, str) or not re.fullmatch(r'gamescope\.gamescope-[0-9]+\.window\.[0-9]+', key):
        return False
    try:
        state = home / '.local/state/frame-desktop-overlay'
        panel = json.loads((state / 'panel.json').read_text())
        owner = json.loads((state / 'owned-instance.json').read_text())
        if (panel.get('schema_version') != 1 or panel.get('input') != 'windows' or
                panel.get('overlayKey') != key or
                owner.get('application') != 'com.moonlight_stream.Moonlight' or
                owner.get('instance') != panel.get('instance')):
            return False
        pid = panel['hostPid']
        if type(pid) is not int or pid <= 0:
            return False
        process = proc / str(pid)
        if process.joinpath('stat').read_text().rsplit(')', 1)[1].split()[19] != panel['processStart']:
            return False
        info = configparser.ConfigParser()
        info.read(process / 'root/.flatpak-info')
        return info.get('Instance', 'instance-id', fallback=None) == panel['instance']
    except (OSError, ValueError, KeyError, IndexError, TypeError, configparser.Error):
        return False
