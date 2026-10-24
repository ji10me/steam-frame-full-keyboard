#!/usr/bin/python3
"""No-text on-device checks for native flash and non-pinned placement."""
import ctypes as C
import json
from pathlib import Path
import runpy
import subprocess
import sys
import threading
import time

home=Path.home();sys.path.insert(0,str(home/'.local/bin'))
from frame_jis_vr import Matrix,Overlay
module=runpy.run_path(str(home/'.local/bin/frame-jis-keyboard'),run_name='inspect_only')
vr=Overlay();client=module['load_cdp']();key=module['PC']
run=lambda args:subprocess.run(args,capture_output=True,text=True,timeout=20)
run([str(home/'.local/bin/frame-jis-keyboard'),'hide'])
run([module['VRCMD'],'--showdashboard',key])
client.evaluate('SteamClient.OpenVR.Keyboard.Hide()');vr.hide_native();time.sleep(.4)
native=vr.handle('valve.steam.gamepadui.keyboard');samples=[];stop=False
def sample():
    while not stop:
        if native and vr.visible(native):samples.append(time.monotonic())
        time.sleep(.002)
def wait(test,seconds=10):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        if test():return True
        time.sleep(.03)
    return False
def owner():return json.loads((module['STATE']/'state.json').read_text())['localOwner']
show=vr.bind(75,[C.c_uint64,C.c_int,C.c_int,C.c_uint32,C.c_char_p,C.c_uint32,C.c_char_p,C.c_uint64])
report={'sentText':False};sampler=threading.Thread(target=sample);sampler.start()
try:
    for label,wanted in [('open',True),('close',False),('reopen',True)]:
        start=len(samples);assert show(vr.handle(key),0,0,13,b'',1024,b'',0)==0
        report[label]=wait(lambda:bool(owner())==wanted)
        assert report[label],label
        time.sleep(.4)
        report[label+'StockVisibleSamples']=len(samples)-start
        report[label+'StockAfterReady']=bool(native and vr.visible(native))
    report['hookStats']=client.evaluate('globalThis.__frameJisLocalV1?.stats()')
    current=vr.geometry(module['PANEL']);desired=vr.placement(key)
    report['initialPositionErrorM']=max(abs(current['center'][r][3]-desired['transform'][r][3]) for r in range(3))
    report['initialWidthErrorM']=abs(current['width']-desired['width_m'])
    moved=Matrix()
    for r in range(3):
        for c in range(4):moved.m[r][c]=current['center'][r][c]
    moved.m[0][3]+=.06
    assert vr.set_absolute(vr.handle(module['PANEL']),1,C.byref(moved))==0
    time.sleep(.7)
    after=vr.geometry(module['PANEL'])
    report['movedPoseNotSnappedBack']=abs(after['center'][0][3]-moved.m[0][3])<.003
    moved.m[0][3]-=.06;vr.set_absolute(vr.handle(module['PANEL']),1,C.byref(moved))
    report['stockVisibleSamples']=len(samples)
except Exception as error:report['failure']=str(error)
finally:
    stop=True;sampler.join();client.close();vr.close()
    (module['STATE']/'presentation-validation.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report))
if 'failure' in report:raise SystemExit(1)
