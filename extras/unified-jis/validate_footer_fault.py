#!/usr/bin/python3
"""No-text active and unconsumed-request recovery, with no restart race."""
import json
from pathlib import Path
import runpy
import signal
import os
import subprocess
import sys
import threading
import time

home=Path.home();sys.path.insert(0,str(home/'.local/bin'))
from frame_jis_cdp import systemui_client
from frame_jis_vr import Overlay
module=runpy.run_path(str(home/'.local/bin/frame-jis-keyboard'),run_name='inspect_only')
vr=Overlay();client=systemui_client();key=module['PC'];GLOBAL='frame-jis-keyboard.service'
override=home/'.config/systemd/user/frame-jis-keyboard.service.d/99-footer-validation.conf'
if override.exists():raise SystemExit('Review the existing test override first')
run=lambda args:subprocess.run(args,capture_output=True,text=True,timeout=20)
def active(unit):return run(['systemctl','--user','is-active','--quiet',unit]).returncode==0
def visible(key):
    handle=vr.handle(key);return bool(handle and vr.visible(handle))
def wait(test,seconds=10):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        if test():return True
        time.sleep(.04)
    return False
def invoke(method):
    return client.evaluate('''(() => {const p=FrameStore.frames_local.flatMap(f=>f.pages||[])
        .find(p=>p.keyboard?.keyboardInputOverlayKey===KEY&&p.isActiveAndVisiblePage);
        if(!p)return false;p.keyboard.METHOD();return true;})()'''.replace('KEY',json.dumps(key)).replace('METHOD',method))
def pid():return int(run(['systemctl','--user','show',GLOBAL,'-p','MainPID','--value']).stdout.strip())
def no_owner():
    return not json.loads((module['STATE']/'state.json').read_text())['localOwner']
overlap=[];stop=False
def sample():
    while not stop:
        if visible('valve.steam.gamepadui.keyboard') and visible(module['PANEL']):overlap.append(time.monotonic())
        time.sleep(.003)
thread=threading.Thread(target=sample);report={'sentText':False};started=False
override.parent.mkdir(parents=True,exist_ok=True);override.write_text('[Service]\nRestart=no\n')
run(['systemctl','--user','daemon-reload'])
try:
    run([str(home/'.local/bin/frame-jis-keyboard'),'hide']);run([module['VRCMD'],'--showdashboard',key]);time.sleep(.3)
    shared=module['load_cdp']();shared.evaluate('SteamClient.OpenVR.Keyboard.Hide()');shared.close();vr.hide_native()
    assert wait(lambda:client.evaluate('globalThis.__frameJisFooterRouterV1?.snapshot().fresh') is True),'initial router not ready'
    time.sleep(.2)
    assert invoke('ShowKeyboard'),'local-crash button unavailable'
    assert wait(lambda:active(module['LOCAL']) and not no_owner()),'local-crash JIS did not open'
    local_pid=int(run(['systemctl','--user','show',module['LOCAL'],'-p','MainPID','--value']).stdout.strip())
    thread.start();started=True
    os.kill(local_pid,signal.SIGKILL)
    report['localProcessCrashRecoversNative']=wait(lambda:not active(module['LOCAL']) and visible('valve.steam.gamepadui.keyboard'))
    assert report['localProcessCrashRecoversNative'],'local-process crash recovery failed'
    assert invoke('HideKeyboard');assert wait(lambda:not visible('valve.steam.gamepadui.keyboard'))
    assert wait(no_owner),'crashed owner was not dismissed'
    assert wait(lambda:client.evaluate('globalThis.__frameJisFooterRouterV1?.snapshot().fresh') is True),'router not ready after crash'
    report['before']=client.evaluate('globalThis.__frameJisFooterRouterV1.snapshot()')
    assert invoke('ShowKeyboard'),'active-stage button unavailable'
    report['afterInvoke']=client.evaluate('globalThis.__frameJisFooterRouterV1.snapshot()')
    assert wait(lambda:active(module['LOCAL']) and not no_owner()),'active-stage JIS did not open'
    os.kill(pid(),signal.SIGKILL)
    report['activeCoordinatorDeathRecoversNative']=wait(lambda:not active(module['LOCAL']) and visible('valve.steam.gamepadui.keyboard'))
    assert report['activeCoordinatorDeathRecoversNative'],'active recovery failed'
    time.sleep(1);report['recoveredNativeStaysOpen']=visible('valve.steam.gamepadui.keyboard')
    assert invoke('HideKeyboard');assert wait(lambda:not visible('valve.steam.gamepadui.keyboard'))
    run(['systemctl','--user','start',GLOBAL]);assert wait(lambda:active(GLOBAL))
    assert wait(lambda:client.evaluate('globalThis.__frameJisFooterRouterV1?.snapshot().fresh') is True),'new router not ready'
    # Stop before the router queue can be consumed. Its own UI watchdog must
    # restore native without relying on Python, its guard, or a visible JIS.
    process=pid();os.kill(process,signal.SIGSTOP)
    assert invoke('ShowKeyboard'),'pending-stage button unavailable'
    assert client.evaluate('globalThis.__frameJisFooterRouterV1.snapshot().pending?.action')=='show','request was not queued'
    report['unconsumedRequestRecoversNative']=wait(lambda:visible('valve.steam.gamepadui.keyboard'),4)
    assert report['unconsumedRequestRecoversNative'],'UI watchdog recovery failed'
    os.kill(process,signal.SIGKILL)
    assert invoke('HideKeyboard');assert wait(lambda:not visible('valve.steam.gamepadui.keyboard'))
except Exception as error:report['failure']=str(error)
finally:
    stop=True
    if started:thread.join()
    current=pid()
    if current:
        try:os.kill(current,signal.SIGCONT)
        except ProcessLookupError:pass
    override.unlink(missing_ok=True);run(['systemctl','--user','daemon-reload'])
    run(['systemctl','--user','start',GLOBAL]);time.sleep(.5)
    run([str(home/'.local/bin/frame-jis-keyboard'),'show',key]);time.sleep(.3)
    client.close();vr.close()
    report['overlapSamples']=len(overlap)
    (module['STATE']/'footer-fault-validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
if 'failure' in report or report['overlapSamples']:raise SystemExit(1)
