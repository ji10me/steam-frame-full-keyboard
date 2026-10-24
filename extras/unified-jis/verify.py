"""Run the existing bridge suite plus exact-owner handoff regressions."""
import argparse
from pathlib import Path
import py_compile
import shutil
import subprocess
import tempfile

from patch_runtime import patch

parser = argparse.ArgumentParser()
parser.add_argument('--node', default='node')
args = parser.parse_args()
addon = Path(__file__).resolve().parent
repo = addon.parents[1]
with tempfile.TemporaryDirectory(prefix='frame-jis-') as name:
    temp = Path(name)
    bridge = temp / 'bridge'
    bridge.mkdir()
    for file in ('steam_bridge.js', 'native_bridge.py'):
        shutil.copy2(repo / 'bridge' / file, bridge / file)
    patch(bridge)
    py_compile.compile(str(bridge / 'native_bridge.py'), doraise=True)
    (temp / 'src').mkdir()
    shutil.copy2(repo / 'src/native_replacement.cpp', temp / 'src/native_replacement.cpp')
    (temp / 'tests').mkdir()
    harness = (repo / 'tests/native_bridge_tests.js').read_text(encoding='utf-8')
    harness = harness.replace('discoveryProbe = false) {', 'discoveryProbe = false, initialTarget = "") {')
    harness = harness.replace('production ? undefined : store, external);',
                              'production ? undefined : store, external, initialTarget);')
    harness += r'''
for (const production of [false, true]) {
    const initial = key => fixture(true, production, false, false, false, false, key);
    for (const target of [MAIN, "current-steam"]) {
        const f = initial(target);
        assert(f.nativeOpen(), "installation alone must not close existing native");
        const s = f.step();
        assert(s.eligible && !f.nativeOpen(), "healthy exact-owner opt-in takes over");
        assert(f.step(s.request).active);
        f.bridge.dispose();
        assert(f.nativeOpen(), "disposal restores the same Steam owner");
    }
    for (const target of ["", "valve.steam.gamepadui.barpopup", "gamescope.gamescope-0.window.62"]) {
        const f = initial(target);
        assert(!f.step().eligible && f.nativeOpen(), "default, mismatched and local owners remain native");
        f.bridge.dispose();
    }
    {
        const f = initial(MAIN);
        assert(!f.step(0, false).eligible && f.nativeOpen(), "unready runtime cannot take over");
        assert(f.step().eligible, "opt-in waits for real readiness");
        f.bridge.dispose();
    }
    {
        const f = initial(MAIN);
        f.status({sOverlayKey: "valve.steam.gamepadui.barpopup"});
        assert(!f.step().eligible && f.nativeOpen(), "changed owner cannot be adopted as the initial request");
        f.bridge.dispose();
    }
}
console.log("Unified JIS: exact-owner opt-in, readiness, mismatch, owner-change and restore regressions passed.");
'''
    test = temp / 'tests/native_bridge_tests.js'
    test.write_text(harness, encoding='utf-8')
    subprocess.run([args.node, str(test), str(bridge / 'steam_bridge.js')], check=True)
for file in ('frame-jis-keyboard', 'install.py', 'frame_jis_vr.py', 'patch_runtime.py'):
    py_compile.compile(str(addon / file), doraise=True)
