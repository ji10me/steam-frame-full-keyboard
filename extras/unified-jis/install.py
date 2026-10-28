#!/usr/bin/python3
"""Install this optional addon beside an existing verified 0.8.2 installation.

Run on the headset with the addon scripts only, never a source checkout/build.
Installing this opt-in addon enables its coordinator at SteamVR startup.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from patch_runtime import patch

home = Path.home()
source = Path(__file__).resolve().parent
release = (home / '.local/share/framekeyboard/current').resolve()
root = home / '.local/share/framekeyboard/unified-jis'
state = home / '.local/state/frame-jis-keyboard'
config = home / '.config/framekeyboard-unified-jis'
units = home / '.config/systemd/user'
bin_dir = home / '.local/bin'
runtime = root / 'runtime'
for directory in (root, state, config, units, bin_dir):
    directory.mkdir(parents=True, exist_ok=True)
if not (release / 'bin/framekeyboard').is_file():
    raise SystemExit('Install Full Keyboard 0.8.2 first')
version = subprocess.run([str(release / 'bin/framekeyboard'), '--help'], capture_output=True, text=True, check=True).stdout
if not version.startswith('Full Keyboard for Steam Frame 0.8.2\n'):
    raise SystemExit('This addon requires the verified 0.8.2 runtime')
manifest_file = state / 'before-install.json'
manifest = json.loads(manifest_file.read_text()) if manifest_file.exists() else {'files': {}, 'bootEnabled': {}}


def backup(path):
    key = str(path.relative_to(home))
    if key in manifest['files']:
        return
    if path.is_symlink():
        manifest['files'][key] = {'symlink': os.readlink(path)}
    elif path.exists():
        saved = state / 'before' / key
        saved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, saved)
        manifest['files'][key] = {'backup': str(saved)}
    else:
        manifest['files'][key] = None
    manifest_file.write_text(json.dumps(manifest, indent=2))


if not runtime.exists():
    shutil.copytree(release, runtime, symlinks=True)
    # Intentionally Steam-only: external JIS belongs to the independent local
    # coordinator, not the Unicode compositor path in native replacement.
    for guard in (runtime / 'bin/framekeyboard-native-guard', runtime / 'share/framekeyboard/framekeyboard-native-guard'):
        guard.unlink(missing_ok=True)
    patch(runtime / 'share/framekeyboard/bridge')
    (root / 'provenance.json').write_text(json.dumps({
        'version': '0.8.2', 'sourceRelease': str(release),
        'binarySHA256': hashlib.sha256((release / 'bin/framekeyboard').read_bytes()).hexdigest(),
        'steamBridgeSHA256Before': hashlib.sha256((release / 'share/framekeyboard/bridge/steam_bridge.js').read_bytes()).hexdigest(),
        'modification': 'initial exact Steam owner opt-in; external native guard omitted',
    }, indent=2))

# Keep the ordinary release/current package shape for the app's startup
# validation. Its startup metadata uses a private XDG home below; actual boot
# activation remains exclusively controlled by the coordinator's systemd unit.
managed_release = root / 'releases/0.8.2-jis'
if not runtime.is_symlink():
    subprocess.run(['systemctl', '--user', 'stop', 'frame-jis-keyboard.service',
                    'framekeyboard-autostart.service', 'framekeyboard-jis-local.service'], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    managed_release.parent.mkdir(exist_ok=True)
    if managed_release.exists():
        raise SystemExit('Review the existing managed release before migration')
    runtime.rename(managed_release)
    runtime.symlink_to('releases/0.8.2-jis', target_is_directory=True)
current = root / 'current'
if not current.exists():
    current.symlink_to('releases/0.8.2-jis', target_is_directory=True)

original = home / '.config/framekeyboard'
for name in ('steam-runtime-home', 'local-runtime-home'):
    vr_config = config / name / 'openvr'
    vr_config.mkdir(parents=True, exist_ok=True)
    registry = vr_config / 'openvrpaths.vrpath'
    if not registry.exists():
        registry.symlink_to(home / '.config/openvr/openvrpaths.vrpath')
preferences = json.loads((original / 'config.json').read_text())
for mode in ('steam', 'desktop', 'pc'):
    directory = config / mode
    directory.mkdir(parents=True, exist_ok=True)
    if not (directory / 'config.json').exists():
        settings = dict(preferences)
        settings['active'] = dict(preferences['active'])
        settings['replace_native_keyboard'] = mode == 'steam'
        # Required for a hidden native lifecycle; this alone enables no unit.
        settings['start_with_steamos'] = mode == 'steam'
        if mode == 'steam':
            settings['active'].update(layout='ja-jis-full', language='ja-romaji-jis')
        (directory / 'config.json').write_text(json.dumps(settings, ensure_ascii=False, indent=2))
        for kind in ('languages', 'layouts'):
            (directory / kind).mkdir(exist_ok=True)
            for name in ('ja-jis-frame.json', 'ja-romaji-jis.json'):
                candidate = original / kind / name
                if candidate.is_file():
                    shutil.copy2(candidate, directory / kind / name)
        placement = (home / '.config/frame-desktop-jis-keyboard/placement.json') if mode == 'pc' else original / 'placement.json'
        if placement.is_file():
            shutil.copy2(placement, directory / 'placement.json')
    subprocess.run([str(runtime / 'bin/framekeyboard'), '--check', '--config-dir', str(directory),
                    '--data-dir', str(runtime / 'share/framekeyboard')], check=True, stdout=subprocess.DEVNULL)

shutil.copy2(source / 'systemui_router.js',root / 'systemui_router.js')
for name in ('frame-jis-keyboard', 'frame_jis_vr.py', 'frame_jis_cdp.py', 'frame_jis_pc.py', 'frame-jis-systemui-session'):
    target = bin_dir / name
    backup(target)
    shutil.copy2(source / name, target)
    target.chmod(0o755)

native = f'''[Unit]
Description=Full Keyboard unified JIS Steam input
After=steamvr.service
PartOf=steamvr.service
StartLimitIntervalSec=0

[Service]
Type=exec
NotifyAccess=all
EnvironmentFile=-/usr/share/deckard/mesavars.sh
EnvironmentFile=-{state}/native.env
Environment=DISPLAY=:0
Environment=XDG_RUNTIME_DIR=/run/user/{os.getuid()}
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{os.getuid()}/bus
Environment=FRAMEKEYBOARD_SERVICE=framekeyboard-autostart.service
Environment=XDG_CONFIG_HOME={config}/steam-runtime-home
UnsetEnvironment=FRAMEKEYBOARD_TARGET_LANGUAGE
ExecStart={runtime}/bin/framekeyboard --vr --input ei --start-enabled --autostart --data-dir {runtime}/share/framekeyboard --config-dir {config}/steam
Restart=on-failure
RestartSec=3
RestartPreventExitStatus=3
SuccessExitStatus=3
TimeoutStopSec=6
KillMode=process
'''
coordinator = f'''[Unit]
Description=Unified Steam Frame JIS keyboard coordinator
After=steamvr.service
PartOf=steamvr.service

[Service]
Type=exec
ExecStartPre=-{bin_dir}/frame-jis-systemui-session
TimeoutStartSec=20
ExecStart={bin_dir}/frame-jis-keyboard --daemon
Restart=on-failure
RestartSec=4
TimeoutStopSec=10
KillMode=process

[Install]
WantedBy=steamvr.service
'''
for name, contents in (('framekeyboard-autostart.service', native), ('frame-jis-keyboard.service', coordinator)):
    path = units / name
    backup(path)
    if name not in manifest['bootEnabled']:
        manifest['bootEnabled'][name] = subprocess.run(['systemctl', '--user', 'is-enabled', '--quiet', name]).returncode == 0
        manifest_file.write_text(json.dumps(manifest, indent=2))
    path.write_text(contents)
legacy = bin_dir / 'framekeyboard-toggle'
backup(legacy)
legacy.write_text('#!/bin/sh\nexec "$HOME/.local/bin/frame-jis-keyboard" "${1:-toggle}"\n')
legacy.chmod(0o755)
subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
subprocess.run(['systemctl', '--user', 'enable', 'frame-jis-keyboard.service'], check=True)
# Install is also useful before VR is running. Enable it for the next session,
# and only start now when the SteamVR dependency is already active.
steamvr_running = subprocess.run(['systemctl', '--user', 'is-active', '--quiet', 'steamvr.service']).returncode == 0
if steamvr_running:
    subprocess.run(['systemctl', '--user', 'start', 'frame-jis-keyboard.service'], check=True)
print(json.dumps({'installed': True, 'runtime': str(runtime), 'backupManifest': str(manifest_file),
                  'startupRequested': True, 'coordinatorStarted': steamvr_running}))
