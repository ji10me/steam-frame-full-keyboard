#!/usr/bin/python3
"""Exercise the real Frame button method without typing or calling native Show."""
import ctypes as C
import json
from pathlib import Path
import runpy
import subprocess
import sys
import threading
import time

home=Path.home();sys.path.insert(0,str(home/'.local/bin'))
from frame_jis_cdp import systemui_client
from frame_jis_vr import Overlay,Matrix
module=runpy.run_path(str(home/'.local/bin/frame-jis-keyboard'),run_name='inspect_only')
vr=Overlay();client=systemui_client();key=sys.argv[1] if len(sys.argv)>1 else module['PC']
if not module['local_key'](key):raise SystemExit('Expected a supported local overlay key')
run=lambda args:subprocess.run(args,capture_output=True,text=True,timeout=20)
run([str(home/'.local/bin/frame-jis-keyboard'),'hide'])
shared=module['load_cdp']();shared.evaluate('SteamClient.OpenVR.Keyboard.Hide()');shared.close();vr.hide_native()
run([module['VRCMD'],'--showdashboard',key]);time.sleep(.4)
native=vr.handle('valve.steam.gamepadui.keyboard');samples=[];stop=False
def sample():
    while not stop:
        if native and vr.visible(native):samples.append(time.monotonic())
        time.sleep(.002)
def state():return json.loads((module['STATE']/'state.json').read_text())
def wait(test,seconds=10):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        if test():return True
        time.sleep(.03)
    return False
def press():
    return client.evaluate('''(() => {const p=FrameStore.frames_local.flatMap(f=>f.pages||[])
        .find(p=>p.keyboard?.keyboardInputOverlayKey===KEY&&p.isActiveAndVisiblePage);
        if(!p)return false;p.keyboard.ShowKeyboard();return true;})()'''.replace('KEY',json.dumps(key)))
report={'sentText':False,'parentOverlayKey':key,'invokesRealFooterMethod':True};thread=threading.Thread(target=sample);thread.start()
try:
    for label,wanted in [('open',True),('close',False),('reopen',True)]:
        before=len(samples);assert press(),'Footer owner is not selected'
        report[label]=wait(lambda:(state()['localOwner']==key)==wanted and
            (not wanted or bool(vr.handle(module['PANEL']) and vr.visible(vr.handle(module['PANEL'])))))
        assert report[label],label
        time.sleep(.4)
        report[label+'NativeVisibleSamples']=len(samples)-before
    report['nativeVisibleSamples']=len(samples)
    assert wait(lambda:vr.geometry(module['PANEL']) is not None,2),'Keyboard pose was not available'
    current=vr.geometry(module['PANEL'])
    config=module['CONFIG']/('pc' if module['pc_target'](key) else 'desktop')
    desired=json.loads((config/'placement.json').read_text())
    report['initialPositionErrorM']=max(abs(current['center'][r][3]-desired['transform'][r][3]) for r in range(3))
    report['keyboardWidthM']=current['width']
    report['keyboardHeightM']=current['center'][1][3]
    assert report['initialPositionErrorM']<.003,'Starting pose differs from app placement'
    moved=Matrix()
    for r in range(3):
        for c in range(4):moved.m[r][c]=current['center'][r][c]
    moved.m[0][3]+=.06;vr.set_absolute(vr.handle(module['PANEL']),1,C.byref(moved));time.sleep(.6)
    report['movedPoseNotSnappedBack']=abs(vr.geometry(module['PANEL'])['center'][0][3]-moved.m[0][3])<.003
    assert report['movedPoseNotSnappedBack'],'Keyboard position was forced back'
    moved.m[0][3]-=.06;vr.set_absolute(vr.handle(module['PANEL']),1,C.byref(moved))
    report['noNativeFlash']=report['nativeVisibleSamples']==0
except Exception as error:report['failure']=str(error)
finally:
    stop=True;thread.join();client.close();vr.close()
    (module['STATE']/'footer-validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
if 'failure' in report or not report.get('noNativeFlash'):raise SystemExit(1)
