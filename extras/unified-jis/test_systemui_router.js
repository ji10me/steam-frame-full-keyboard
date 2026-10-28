"use strict";
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict");
const factory=vm.runInNewContext(fs.readFileSync(process.argv[2],"utf8"));
const PC="valve.steam.desktopgame.2000000420";
function fixture(key=PC) {
    let time=100,timer,shows=0,hides=0,pid=10;
    class Keyboard {
        ShowKeyboard(){shows++;this.isKeyboardVisible=true;}
        HideKeyboard(){hides++;this.isKeyboardVisible=false;}
    }
    const originalShow=Keyboard.prototype.ShowKeyboard,originalHide=Keyboard.prototype.HideKeyboard;
    const page={isActiveAndVisiblePage:true,inputFocus:{PushInputFocus(){}}};
    const keyboard=new Keyboard();Object.assign(keyboard,{framePage:page,keyboardInputOverlayKey:key,supportsKeyboardInput:true,isKeyboardVisible:false});
    page.keyboard=keyboard;
    const root={performance:{now:()=>time},FrameStore:{frames_local:[{frameID:7,pages:[page]}]},
        OverlayStore:{GetOverlayInfo:()=>pid?{unClientPID:pid}:null},
        DashboardStore:{activeFrameID:7,visibilityState_IgnoringKeyboardHack:0,
            _setActiveFrame(id){this.activeFrameID=id;},
            OnShown(){this.visibilityState_IgnoringKeyboardHack=1;},OnHidden(){this.visibilityState_IgnoringKeyboardHack=0;}},
        setInterval(fn){timer=fn;return 1;},clearInterval(){timer=null;}};
    const bridge=factory(root);
    return {bridge,keyboard,page,root,originalShow,originalHide,
        counts:()=>({shows,hides}),pid(n){pid=n;},advance(ms){time+=ms;timer?.();}};
}
{
    const f=fixture();
    assert.equal(f.bridge.poll("").localFocus,PC,"idle local focus can prepare the next summon");
    f.root.DashboardStore.activeFrameID=8;
    assert.equal(f.bridge.poll("").localFocus,"","another selected frame cannot park Steam");
    f.root.DashboardStore.activeFrameID=7;f.page.isActiveAndVisiblePage=false;
    assert.equal(f.bridge.poll("").localFocus,"","hidden pages cannot park Steam");
    f.page.isActiveAndVisiblePage=true;f.keyboard.supportsKeyboardInput=false;
    assert.equal(f.bridge.poll("").localFocus,"","unsupported pages retain Steam readiness");
    f.bridge.dispose(false);
}
{
    const f=fixture();f.root.FrameStore.frames_local[0].pages.push(f.page);
    assert.equal(f.bridge.poll("").localFocus,"","ambiguous local owners retain Steam readiness");
    f.bridge.dispose(false);
}
{
    const f=fixture();f.bridge.poll("");f.keyboard.ShowKeyboard();
    assert.equal(f.root.DashboardStore.visibilityState_IgnoringKeyboardHack,1);
    let state=f.bridge.poll("");assert.equal(state.pending.action,"show");assert.equal(f.counts().shows,0);
    const id=state.pending.id;assert(f.bridge.busy(id));f.pid(20);f.advance(1200);
    assert(f.bridge.ack(id,true,20));f.bridge.poll(PC);f.keyboard.ShowKeyboard();
    state=f.bridge.poll(PC);assert.equal(state.pending.action,"hide");
    assert(f.bridge.ack(state.pending.id,false));assert.deepEqual(f.counts(),{shows:0,hides:0});
    assert.equal(f.root.DashboardStore.visibilityState_IgnoringKeyboardHack,0);
    f.bridge.dispose(false);assert.equal(f.keyboard.ShowKeyboard,f.originalShow);
    assert.equal(f.keyboard.HideKeyboard,f.originalHide);
}
{
    const f=fixture();f.root.DashboardStore.activeFrameID=8;f.bridge.poll("");f.keyboard.ShowKeyboard();
    assert.equal(f.root.DashboardStore.activeFrameID,7,"explicit visible-window footer selects its own frame");
    const id=f.bridge.poll("").pending.id;assert(f.bridge.ack(id,true,20));
    assert.equal(f.bridge.poll(PC,20).ownerValid,true);assert.equal(f.counts().shows,0);f.bridge.dispose(false);
}
{
    const f=fixture();f.bridge.poll("");f.keyboard.ShowKeyboard();const id=f.bridge.poll("").pending.id;
    f.root.DashboardStore.activeFrameID=8;
    assert.equal(f.bridge.ack(id,true,20),false,"focus changed during launch cannot acquire input");
    f.pid(0);f.advance(1000);assert.equal(f.counts().shows,0);f.bridge.dispose(false);
}
{
    const f=fixture();f.bridge.poll("");f.keyboard.ShowKeyboard();f.advance(1000);
    assert.equal(f.counts().shows,1,"unconsumed request falls back independently after lease expiry");
    assert.equal(f.bridge.poll("").fallbackKey,PC);f.bridge.dispose(false);
}
{
    const f=fixture();f.bridge.poll("");f.keyboard.ShowKeyboard();f.advance(1000);
    f.bridge.poll("");f.keyboard.HideKeyboard();f.keyboard.ShowKeyboard();
    assert.equal(f.counts().shows,1,"closing recovered native permits an immediate new direct request");
    assert.equal(f.bridge.poll("").pending.action,"show");f.bridge.dispose(false);
}
{
    const f=fixture();f.pid(0);f.bridge.poll("",0,10);f.keyboard.ShowKeyboard();
    f.pid(10);f.advance(1000);
    assert.equal(f.counts().shows,1,"late creation of the known hidden Steam resident cannot block fallback");
    f.bridge.dispose(false);
}
{
    const f=fixture();f.pid(20);f.bridge.beginManual(PC);f.keyboard.isKeyboardVisible=true;
    assert.equal(f.bridge.poll(PC,20).fallbackKey,"");
    assert.equal(f.root.DashboardStore.visibilityState_IgnoringKeyboardHack,1);
    f.keyboard.isKeyboardVisible=false;f.bridge.poll(PC,20);f.keyboard.ShowKeyboard();
    assert.equal(f.bridge.poll(PC,20).pending.action,"hide");f.bridge.dispose(false);
}
{
    const f=fixture();f.pid(20);f.bridge.poll(PC,20);f.keyboard.isKeyboardVisible=true;
    assert.equal(f.bridge.poll(PC,20).fallbackKey,"");
    f.pid(0);assert.equal(f.bridge.poll(PC,20).fallbackKey,PC);f.bridge.dispose(false);
}
{
    const f=fixture();f.pid(20);f.bridge.poll(PC,20);f.pid(0);f.keyboard.isKeyboardVisible=true;
    f.advance(50);f.keyboard.isKeyboardVisible=false;f.advance(1000);
    assert.equal(f.counts().shows,0,"closing guard recovery cannot be undone by a delayed UI watchdog");
    f.bridge.dispose(false);
}
{
    const f=fixture();f.pid(20);f.bridge.poll(PC,20);f.root.DashboardStore.activeFrameID=8;
    assert.equal(f.bridge.poll(PC,20).ownerValid,false);
    f.pid(0);f.advance(1000);assert.equal(f.counts().shows,0,"another active frame cannot inherit recovery input");
    f.bridge.dispose(false);
}
{
    const f=fixture();f.bridge.poll("");f.keyboard.ShowKeyboard();
    const id=f.bridge.poll("").pending.id;f.bridge.busy(id);f.pid(20);f.advance(6100);
    assert.equal(f.counts().shows,0,"fallback cannot overlap a newly launched replacement");
    f.pid(0);f.advance(60);assert.equal(f.counts().shows,1);f.bridge.dispose(false);
}
{
    const f=fixture();f.bridge.poll("");f.keyboard.ShowKeyboard();
    const id=f.bridge.poll("").pending.id;f.pid(20);assert(f.bridge.ack(id,true,20));f.advance(1000);
    assert.equal(f.counts().shows,0);f.pid(0);f.advance(60);
    assert.equal(f.counts().shows,0,"guard gets time to classify Close before UI recovery");
    f.advance(800);assert.equal(f.counts().shows,1);
    f.bridge.dispose(false);
}
for(const key of ["valve.steam.gamepadui.main","unknown"]) {
    const f=fixture(key);f.bridge.poll("");f.keyboard.ShowKeyboard();assert.equal(f.counts().shows,1);f.bridge.dispose(false);
}
{
    const f=fixture();f.bridge.poll("");f.keyboard.ShowKeyboard();f.page.isActiveAndVisiblePage=false;f.advance(1000);
    assert.equal(f.counts().shows,0,"hidden owner cannot be restored");f.bridge.dispose(false);
}
{
    const f=fixture();f.bridge.poll("");f.keyboard.ShowKeyboard();let id=f.bridge.poll("").pending.id;
    f.keyboard.ShowKeyboard();assert.equal(f.bridge.ack(id,true,20),false,"retired generations cannot acquire presentation");
    f.bridge.dispose(false);
}
{
    const f=fixture();f.pid(20);f.bridge.poll(PC,20);f.keyboard.isKeyboardVisible=true;
    assert(f.bridge.completeClose(PC,20));
    assert.equal(f.keyboard.isKeyboardVisible,false,"Close dismisses an existing native keyboard too");
    assert.equal(f.counts().hides,1);f.pid(0);f.advance(1200);
    assert.equal(f.counts().shows,0,"normal Close cannot become watchdog recovery");
    f.bridge.poll("");f.keyboard.ShowKeyboard();
    assert.equal(f.bridge.poll("").pending.action,"show","the footer immediately reopens after Close");
    f.bridge.dispose(false);
}
{
    const f=fixture();f.pid(30);f.bridge.poll(PC,30);f.keyboard.isKeyboardVisible=true;
    assert.equal(f.bridge.completeClose(PC,20),false,"an old guard cannot close a newly reopened process");
    assert.equal(f.keyboard.isKeyboardVisible,true);assert.equal(f.counts().hides,0);f.bridge.dispose(false);
}
console.log("Footer router: no native Show/Hide, toggle, exact owners, lease fallback, no overlap, cancellation and cleanup passed.");
