#!/usr/bin/python3
"""Click only the known JIS toolbar Close button, including guard-only close."""
import ctypes as C
import json
from pathlib import Path
import os
import runpy
import signal
import subprocess
import sys
import threading
import time

home=Path.home();sys.path.insert(0,str(home/'.local/bin'))
from frame_jis_cdp import systemui_client
from frame_jis_vr import Overlay
module=runpy.run_path(str(home/'.local/bin/frame-jis-keyboard'),run_name='inspect_only')
key=sys.argv[1] if len(sys.argv)>1 else module['PC']
if not module['local_key'](key):raise SystemExit('Expected a supported local overlay key')
config=module['CONFIG']/('pc' if module['pc_target'](key) else 'desktop')
preferences=json.loads((config/'config.json').read_text())
if preferences['active']['layout']!='ja-jis-frame-full' or preferences.get('hide_numpad',False):
    raise SystemExit('Close coordinates require the full, visible-numpad JIS profile')
run=lambda args:subprocess.run(args,capture_output=True,text=True,timeout=20)
vr=Overlay();client=systemui_client();paused=0;stop=False;samples=[]
def visible(key):
    handle=vr.handle(key);return bool(handle and vr.visible(handle))
def native():return any(visible(k) for k in ('valve.steam.gamepadui.keyboard','system.keyboard'))
def sample():
    while not stop:
        if native():samples.append(time.monotonic())
        time.sleep(.002)
def wait(test,seconds=8):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        if test():return True
        time.sleep(.03)
    return False
def owner():return json.loads((module['STATE']/'state.json').read_text())['localOwner']
def unit():
    result=run(['systemctl','--user','show',module['LOCAL'],'-p','MainPID','-p','ActiveState',
                '-p','SubState','-p','Result','-p','ExecMainCode','-p','ExecMainStatus'])
    return dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)
def open_footer():
    return client.evaluate('''(() => {const p=FrameStore.frames_local.flatMap(f=>f.pages||[])
        .find(p=>p.keyboard?.keyboardInputOverlayKey===KEY&&p.isActiveAndVisiblePage);
        if(!p)return false;p.keyboard.ShowKeyboard();return true;})()'''.replace('KEY',json.dumps(key)))
class Mouse(C.Structure):
    _fields_=[('x',C.c_float),('y',C.c_float),('button',C.c_uint32),('cursor',C.c_uint32)]
class Data(C.Union):_fields_=[('mouse',Mouse),('reserved',C.c_uint64*6)]
class Event(C.Structure):
    _pack_=4
    _fields_=[('kind',C.c_uint32),('device',C.c_uint32),('age',C.c_float),('data',Data)]
error=C.c_int();pointer=vr.lib.VR_GetGenericInterface(b'FnTable:IVROverlayView_003',C.byref(error))
if error.value or not pointer:raise SystemExit('Overlay event API unavailable')
table=C.cast(pointer,C.POINTER(C.c_void_p))
post=C.CFUNCTYPE(None,C.c_uint64,C.POINTER(Event))(table[2])
def click_close():
    handle=vr.handle(module['PANEL']);geometry=vr.geometry(module['PANEL'])
    assert handle and visible(module['PANEL']) and geometry['scale']==[1600.,1000.]
    # From App::controls and panel.hpp: body width1600; Close x1522..1582,
    # y12..54. OpenVR uses bottom-left texture coordinates (+200 popup margin).
    event=Event();event.device=0xffffffff;event.data.mouse=Mouse(1552,767,1,0)
    for kind in (300,301,302):
        event.kind=kind;post(handle,C.byref(event));time.sleep(.06)

report={'sentText':False,'parentOverlayKey':key,'clicksRealToolbarClose':True}
thread=threading.Thread(target=sample)
try:
    run([str(home/'.local/bin/frame-jis-keyboard'),'hide'])
    shared=module['load_cdp']();shared.evaluate('SteamClient.OpenVR.Keyboard.Hide()');shared.close();vr.hide_native()
    run([module['VRCMD'],'--showdashboard',key]);time.sleep(.3)
    thread.start()
    for phase in ('normal','coordinatorPaused'):
        assert open_footer(),'Footer unavailable'
        assert wait(lambda:owner()==key and visible(module['PANEL'])),'JIS did not open'
        if phase=='coordinatorPaused':
            paused=int(run(['systemctl','--user','show','frame-jis-keyboard.service','-p','MainPID','--value']).stdout)
            os.kill(paused,signal.SIGSTOP);time.sleep(1.1)
        before=len(samples);click_close()
        assert wait(lambda:unit().get('MainPID')=='0'),'Close did not exit JIS'
        report[phase+'Exit']=unit()
        if phase=='coordinatorPaused':
            assert report[phase+'Exit']['ExecMainCode']=='1' and report[phase+'Exit']['ExecMainStatus']=='0'
        time.sleep(1.2)
        report[phase+'BothClosed']=not visible(module['PANEL']) and not native()
        report[phase+'NativeVisibleSamples']=len(samples)-before
        assert report[phase+'BothClosed'],'Native keyboard remained after Close'
        assert report[phase+'NativeVisibleSamples']==0,'Native flashed during Close'
        if paused:
            guard=json.loads((module['STATE']/'guard-state.json').read_text())
            report['guardRecognizedClose']=guard['reason']=='keyboard-closed' and not guard['restored']
            assert report['guardRecognizedClose'],'Guard treated Close as failure'
            os.kill(paused,signal.SIGCONT);paused=0
        assert wait(lambda:not owner()),'Coordinator retained the closed owner'
    assert open_footer() and wait(lambda:owner()==key and visible(module['PANEL'])),'Cannot reopen after Close'
    report['reopensAfterClose']=True;click_close()
    assert wait(lambda:not owner() and not visible(module['PANEL']) and not native()),'Final Close failed'
    time.sleep(1);report['bothRemainClosed']=not visible(module['PANEL']) and not native()
    assert report['bothRemainClosed']
except Exception as error:report['failure']=str(error)
finally:
    if paused:os.kill(paused,signal.SIGCONT)
    stop=True
    if thread.is_alive():thread.join()
    report['nativeVisibleSamples']=len(samples)
    client.close();vr.close()
    (module['STATE']/'close-validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
if 'failure' in report:raise SystemExit(1)
