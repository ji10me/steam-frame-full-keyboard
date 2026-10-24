#!/usr/bin/python3
"""On-device integration checks. Sends keyboard summon events, never text.

Optional --fault-test verifies the independent guard with a healthy PC panel.
The tests temporarily select dashboard tabs and leave the new Steam JIS open.
"""
import ctypes as C
import json
import os
from pathlib import Path
import runpy
import signal
import subprocess
import sys
import time

home = Path.home()
sys.path.insert(0, str(home / '.local/bin'))
from frame_jis_vr import Overlay

os.environ.update(DISPLAY=':0', XDG_RUNTIME_DIR='/run/user/' + str(os.getuid()),
                  DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/' + str(os.getuid()) + '/bus')
module = runpy.run_path(str(home / '.local/bin/frame-jis-keyboard'), run_name='inspect_only')
vr = Overlay()
report = {'testSentText': False}
LOCAL = module['LOCAL']; NATIVE = module['NATIVE']; PC = module['PC']
GLOBAL = 'frame-jis-keyboard.service'
MAIN = 'valve.steam.gamepadui.main'
show = vr.bind(75, [C.c_uint64, C.c_int, C.c_int, C.c_uint32, C.c_char_p,
                   C.c_uint32, C.c_char_p, C.c_uint64])


def run(args):
    return subprocess.run(args, capture_output=True, text=True, timeout=20)


def active(unit):
    return run(['systemctl', '--user', 'is-active', '--quiet', unit]).returncode == 0


def visible(key):
    h = vr.handle(key)
    return bool(h and vr.visible(h))


def wait(test, seconds=14):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if test():
            return True
        time.sleep(.1)
    return False


def request(key):
    assert show(vr.handle(key), 0, 0, 13, b'', 1024, b'', 0) == 0


def close_native():
    c = module['load_cdp']()
    try:
        c.evaluate('SteamClient.OpenVR.Keyboard.Hide()')
        vr.hide_native()
    finally:
        c.close()


def diag():
    c = module['load_cdp']()
    try:
        return c.evaluate('globalThis.__fullKeyboardNativeV1?.bridge.diagnostics()') or {}
    finally:
        c.close()


def ready():
    c = module['load_cdp']()
    try:
        return c.evaluate('globalThis.__fullKeyboardNativeV1?.bridge.expired() === false') is True
    finally:
        c.close()


override = home / '.config/systemd/user/frame-jis-keyboard.service.d/99-validation.conf'
try:
    for label, key in [('pc', PC), ('desktop', sys.argv[1])]:
        run([str(home / '.local/bin/frame-jis-keyboard'), 'hide'])
        run([module['VRCMD'], '--showdashboard', key]); time.sleep(.5)
        for action, wanted in [('opens', True), ('closes', False), ('reopens', True)]:
            request(key)
            def check():
                return active(LOCAL) == wanted and (visible(module['PANEL']) if wanted else active(NATIVE)) and not visible('valve.steam.gamepadui.keyboard')
            report[label + '_' + action] = wait(check)
            assert report[label + '_' + action], label + '_' + action
            time.sleep(.8)
        report[label + '_owner'] = json.loads((module['STATE'] / 'state.json').read_text())['localOwner'] == key
        run([str(home / '.local/bin/frame-jis-keyboard'), 'hide']); time.sleep(.8)
    if '--fault-test' in sys.argv:
        # A runtime-only test override prevents a quick supervisor restart from
        # concealing the independent guard's native recovery.
        assert not override.exists(), 'Existing validation override must be reviewed first'
        override.parent.mkdir(parents=True, exist_ok=True)
        override.write_text('[Service]\nRestart=no\n')
        run(['systemctl', '--user', 'daemon-reload'])
        run([module['VRCMD'], '--showdashboard', PC]); time.sleep(.5)
        request(PC)
        assert wait(lambda: active(LOCAL) and visible(module['PANEL']) and json.loads((module['STATE'] / 'state.json').read_text())['localOwner'] == PC)
        assert module['focused'](vr, PC), 'PC must own focus before the recovery test'
        pid = int(run(['systemctl', '--user', 'show', GLOBAL, '-p', 'MainPID', '--value']).stdout.strip())
        os.kill(pid, signal.SIGKILL)
        report['independentRecoveryAfterCoordinatorKill'] = wait(lambda: not active(LOCAL) and visible('valve.steam.gamepadui.keyboard'), 12)
        assert report['independentRecoveryAfterCoordinatorKill']
        close_native()
        override.unlink(); run(['systemctl', '--user', 'daemon-reload'])
        run(['systemctl', '--user', 'start', GLOBAL]); time.sleep(1)
    run([module['VRCMD'], '--showdashboard', MAIN]); time.sleep(.5)
    for action, wanted in [('opens', True), ('closes', False), ('reopens', True)]:
        request(MAIN)
        def check_steam():
            state = diag() or {}
            return state.get('active') is wanted and visible(module['PANEL']) == wanted and not visible('valve.steam.gamepadui.keyboard')
        report['steam_' + action] = wait(check_steam)
        assert report['steam_' + action], 'steam_' + action
        time.sleep(.8)
    report['steamRoute'] = diag().get('route')
    result = run([str(home / '.local/bin/frame-jis-keyboard'), 'show', PC])
    report['explicitSteamToPc'] = result.returncode == 0 and json.loads((module['STATE'] / 'state.json').read_text())['localOwner'] == PC
    assert report['explicitSteamToPc']
    run([module['VRCMD'], '--showdashboard', MAIN])
    report['targetChangeClosesLocal'] = wait(lambda: not active(LOCAL) and not json.loads((module['STATE'] / 'state.json').read_text())['localOwner'])
    assert report['targetChangeClosesLocal']
    assert wait(ready)
    request(MAIN)
    report['steamRequestAfterLocalReady'] = wait(lambda: diag().get('active') is True)
    assert report['steamRequestAfterLocalReady']
except Exception as error:
    report['failure'] = str(error)
finally:
    if override.exists():
        override.unlink(); run(['systemctl', '--user', 'daemon-reload'])
        run(['systemctl', '--user', 'start', GLOBAL])
    (module['STATE'] / 'validation.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))
    vr.close()
if 'failure' in report:
    raise SystemExit(1)
