// Route the actual Frame keyboard button BEFORE its native ShowKeyboard call.
// No native keyboard status, field text or clipboard values are modified/read.
(function installFooterRouter(root) {
    "use strict";
    const now = () => root.performance.now();
    const frames = root.FrameStore;
    const overlays = root.OverlayStore;
    const dashboard = root.DashboardStore;
    const panel = "org.framekeyboard.panel";
    const local = key => key === "valve.steam.desktopgame.2000000420" ||
        typeof key === "string" && /^gamescope\.gamescope-[0-9]+(?:\.window\.[0-9]+)?$/.test(key);
    const components = frames?.frames_local?.flatMap(frame => frame.pages || []).map(page => page.keyboard).filter(Boolean);
    const prototype = components?.map(Object.getPrototypeOf).find(p => typeof p.ShowKeyboard === "function" && typeof p.HideKeyboard === "function");
    if (!prototype || typeof overlays?.GetOverlayInfo !== "function" ||
        typeof dashboard?.OnShown !== "function" || typeof dashboard?.OnHidden !== "function" ||
        typeof dashboard?._setActiveFrame !== "function") throw Error("footer-api-unavailable");
    const showDescriptor = Object.getOwnPropertyDescriptor(prototype, "ShowKeyboard");
    const hideDescriptor = Object.getOwnPropertyDescriptor(prototype, "HideKeyboard");
    if (!showDescriptor?.configurable || !hideDescriptor?.configurable) throw Error("footer-api-readonly");
    const originalShow = prototype.ShowKeyboard, originalHide = prototype.HideKeyboard;
    let lease = 0, sequence = 0, pending = null, active = null, fallback = null, disposed = false;
    let routed = 0, nativeFallbacks = 0;
    let idlePid = 0;
    let openedForFrame = null;
    const fresh = () => !disposed && now() < lease;
    const panelPid = () => overlays.GetOverlayInfo(panel)?.unClientPID || 0;
    function openDashboard(frame) {
        if (dashboard.visibilityState_IgnoringKeyboardHack===0) {
            openedForFrame=frame;dashboard.OnShown();
        }
    }
    function releaseDashboard() {
        if (openedForFrame!==null && dashboard.activeFrameID===openedForFrame &&
            dashboard.visibilityState_IgnoringKeyboardHack===1) dashboard.OnHidden();
        openedForFrame=null;
    }
    function focusOwner(owner) {
        // Clicking an undocked/theater frame is an explicit input-target
        // selection, even while the dashboard still points at another frame.
        if (dashboard.activeFrameID!==owner.frame)
            dashboard._setActiveFrame(owner.frame,owner.component.framePage.summonOverlayKey || owner.key);
        openDashboard(owner.frame);
        owner.component.framePage.inputFocus.PushInputFocus();
    }
    function target(component) {
        const key = component?.keyboardInputOverlayKey;
        if (!local(key) || component.supportsKeyboardInput !== true ||
            component.framePage?.isActiveAndVisiblePage !== true ||
            typeof component.framePage?.inputFocus?.PushInputFocus !== "function") return null;
        const matching = frames.frames_local.filter(frame => frame.pages?.includes(component.framePage));
        return matching.length === 1 && Number.isSafeInteger(matching[0].frameID) ?
            {component, key, frame: matching[0].frameID} : null;
    }
    function valid(request) {
        const current = target(request?.component);
        return !!request && current?.key === request.key && current.frame === request.frame;
    }
    const focused = request => valid(request) && dashboard.activeFrameID===request.frame;
    function metadata(request) {
        return request ? {id:request.id, key:request.key, frame:request.frame, action:request.action} : null;
    }
    function restoreNative(request) {
        pending = active = null;
        if (!request || !focused(request) || request.action === "hide") return;
        fallback = {...request, until:now()+1000,seen:request.component.isKeyboardVisible===true}; nativeFallbacks++;
        originalShow.call(request.component);
    }
    function updateFallback() {
        if (!fallback) return;
        if (fallback.component.isKeyboardVisible===true) fallback.seen=true;
        else if (fallback.seen || now()>=fallback.until) { fallback=null;releaseDashboard(); }
    }
    function observeRecovery() {
        const request=pending || active;
        if (request && request.action!=="hide" && request.component.isKeyboardVisible===true && canRestore(request)) {
            fallback={...request,until:now()+1000,seen:true};active=pending=null;
        }
    }
    function canRestore(request) {
        const pid = panelPid();
        // A live replacement must finish shutdown before native is requested.
        // During startup, the initial PID belongs to the hidden Steam resident.
        return !pid || (request.pid ? pid !== request.pid : pid === request.initialPid || pid === idlePid);
    }
    function enqueue(component, action) {
        updateFallback();
        const owner = target(component);
        if (!fresh() || !owner || fallback?.key === owner.key || component.isKeyboardVisible === true) return false;
        if (action === "show" && (active?.key === owner.key || pending?.key === owner.key)) action = "hide";
        if (action === "show") {
            // Keep the exact same target-focus action as the native button.
            focusOwner(owner);
        }
        pending = {...owner, id:++sequence, action, initialPid:panelPid()};
        routed++;
        return true;
    }
    const show = function(...args) {
        if (!enqueue(this, "show")) return originalShow.apply(this,args);
    };
    const hide = function(...args) {
        if (!enqueue(this, "hide")) return originalHide.apply(this,args);
    };
    Object.defineProperty(prototype,"ShowKeyboard",{...showDescriptor,value:show});
    Object.defineProperty(prototype,"HideKeyboard",{...hideDescriptor,value:hide});
    function watchdog() {
        observeRecovery();
        updateFallback();
        const request = pending || active;
        if (!request) return;
        if (!valid(request) || !pending && !focused(request)) { pending=active=null; releaseDashboard(); return; }
        if (!fresh() && canRestore(request)) {
            // A vanished acknowledged process may have just exited normally.
            // Let the independent guard read the retained systemd status and
            // retire Close before this UI-only fallback can show native.
            if (request.pid) {
                request.missingSince ??= now();
                if (now()-request.missingSince < 750) return;
            }
            restoreNative(request);
        } else delete request.missingSince;
    }
    const timer = root.setInterval(watchdog,50);
    return {
        beginManual(key) {
            if (disposed || !local(key)) return false;
            const owners=frames.frames_local.flatMap(frame=>(frame.pages || []).map(page=>({frame,page})))
                .filter(owner=>owner.page.keyboard?.keyboardInputOverlayKey===key);
            if (owners.length!==1) return false;
            const owner=target(owners[0].page.keyboard);
            if (!owner) return false;
            focusOwner(owner);return true;
        },
        poll(key,pid=0,hiddenPid=0) {
            idlePid=Number.isSafeInteger(hiddenPid)?hiddenPid:0;
            if (!disposed) lease=now()+900;
            if (key && pid && !active && !pending) {
                const owners=frames.frames_local.flatMap(frame=>frame.pages || [])
                    .map(page=>target(page.keyboard)).filter(owner=>owner?.key===key);
                if (owners.length===1 && owners[0].component.isKeyboardVisible!==true) active={...owners[0],action:"show",pid};
            }
            observeRecovery();
            if (active && active.key !== key && !pending) active=null;
            updateFallback();
            if (!key && !active && !pending && !fallback) releaseDashboard();
            const matching=key ? frames.frames_local.flatMap(frame=>frame.pages || [])
                .map(page=>target(page.keyboard)).filter(owner=>owner?.key===key) : [];
            const selected=frames.frames_local.filter(frame=>frame.frameID===dashboard.activeFrameID)
                .flatMap(frame=>frame.pages || []).map(page=>target(page.keyboard)).filter(Boolean);
            return {pending:metadata(pending),fallbackKey:fallback?.key || "",routed,nativeFallbacks,
                localFocus:selected.length===1?selected[0].key:"",
                ownerValid:!key || matching.length===1&&dashboard.activeFrameID===matching[0].frame,
                ownerFrame:matching.length===1?matching[0].frame:null};
        },
        snapshot() { return {fresh:fresh(),pending:metadata(pending),routed,nativeFallbacks}; },
        busy(id) { if (pending?.id !== id || !fresh() || !valid(pending)) return false; lease=now()+6000; return true; },
        ack(id,shown,pid=0) {
            if (pending?.id !== id || !fresh() || !focused(pending)) return false;
            active=shown ? {...pending,pid} : null; pending=null;
            if (!shown) releaseDashboard();return true;
        },
        reject(id) { if (pending?.id === id) restoreNative(pending); },
        nativeFallback(key) {
            const owners=frames.frames_local.flatMap(frame=>frame.pages || []).map(page=>target(page.keyboard))
                .filter(owner=>owner?.key===key);
            active=pending=null;
            if (owners.length===1) fallback={...owners[0],action:"show",until:now()+1000,
                seen:owners[0].component.isKeyboardVisible===true};
        },
        completeClose(key,pid) {
            // An old guard must not close a replacement already reopened with
            // a different process, or a different frame's native keyboard.
            if (active && (active.key!==key || active.pid && active.pid!==pid)) return false;
            if (fallback && fallback.key!==key) return false;
            const owners=frames.frames_local.flatMap(frame=>frame.pages || [])
                .map(page=>target(page.keyboard)).filter(owner=>owner?.key===key);
            if (active?.key===key) active=null;
            if (pending?.key===key && (pending.action==='hide' || pid===0)) pending=null;
            if (fallback?.key===key) fallback=null;
            if (owners.length===1 && owners[0].component.isKeyboardVisible===true)
                originalHide.call(owners[0].component);
            if (!active && !pending && !fallback) releaseDashboard();
            return true;
        },
        clear() { pending=active=null; releaseDashboard(); },
        dispose(restore=true) {
            if (disposed) return;
            const request=pending || active;
            disposed=true;lease=0;root.clearInterval(timer);
            if (prototype.ShowKeyboard===show) Object.defineProperty(prototype,"ShowKeyboard",showDescriptor);
            if (prototype.HideKeyboard===hide) Object.defineProperty(prototype,"HideKeyboard",hideDescriptor);
            if (restore && request && canRestore(request)) restoreNative(request);
            if (!restore || !request) releaseDashboard();
        }
    };
})
