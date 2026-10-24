#!/usr/bin/python3
"""Restore the user files recorded before this addon was installed."""
import json
import os
from pathlib import Path
import shutil
import subprocess

home = Path.home()
state = home / '.local/state/frame-jis-keyboard'
manifest = json.loads((state / 'before-install.json').read_text())
units = ('frame-jis-keyboard.service', 'framekeyboard-autostart.service')
subprocess.run(['systemctl', '--user', 'stop', *units, 'framekeyboard-jis-local.service'], check=False)
subprocess.run(['systemctl', '--user', 'disable', 'frame-jis-keyboard.service'], check=False)
for relative, value in manifest['files'].items():
    target = home / relative
    if not target.resolve().is_relative_to(home.resolve()):
        raise SystemExit('Invalid backup target')
    if target.is_symlink() or target.is_file():
        target.unlink()
    if value is None:
        continue
    target.parent.mkdir(parents=True, exist_ok=True)
    if 'symlink' in value:
        os.symlink(value['symlink'], target)
    else:
        saved = Path(value['backup'])
        if not saved.resolve().is_relative_to((state / 'before').resolve()):
            raise SystemExit('Invalid backup source')
        shutil.copy2(saved, target)
subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
for unit in units:
    if manifest['bootEnabled'].get(unit):
        subprocess.run(['systemctl', '--user', 'enable', unit], check=True)
print('Previous launchers and units restored. Private addon profiles/backups were retained.')
