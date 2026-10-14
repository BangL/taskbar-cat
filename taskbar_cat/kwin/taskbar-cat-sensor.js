// Taskbar-Cat Fenster-Sensor: meldet Monitore, Arbeitsflächen und begehbare
// Fenster an die App (de.bangl.TaskbarCat). Keine Timer in KWin-JS ->
// jede Änderung wird sofort gesendet, die App fasst zusammen.

function rect(r) {
    return { x: r.x, y: r.y, w: r.width, h: r.height };
}

function relevant(w) {
    return w.normalWindow && !w.minimized && !w.deleted &&
        (!w.desktops.length || w.desktops.includes(workspace.currentDesktop)) &&
        (!w.activities.length || w.activities.includes(workspace.currentActivity));
}

function send() {
    var outputs = workspace.screens.map(function (o) {
        return {
            name: o.name,
            geometry: rect(o.geometry),
            workArea: rect(workspace.clientArea(KWin.MaximizeArea, o, workspace.currentDesktop))
        };
    });
    var windows = workspace.windowList().filter(relevant).map(function (w) {
        var g = w.frameGeometry;
        var area = workspace.clientArea(KWin.MaximizeArea, w);
        return {
            id: w.internalId.toString(),
            x: g.x, y: g.y, w: g.width, h: g.height,
            stack: w.stackingOrder,
            pid: w.pid,
            fullScreen: w.fullScreen,
            maximized: g.width >= area.width && g.height >= area.height
        };
    });
    callDBus("de.bangl.TaskbarCat", "/", "de.bangl.TaskbarCat", "update",
             JSON.stringify({ outputs: outputs, windows: windows }));
}

function watch(w) {
    ["frameGeometryChanged", "minimizedChanged", "fullScreenChanged",
     "stackingOrderChanged", "desktopsChanged", "activitiesChanged"].forEach(function (s) {
        if (w[s]) {
            w[s].connect(send);
        }
    });
}

workspace.windowList().forEach(watch);
workspace.windowAdded.connect(function (w) { watch(w); send(); });
["windowRemoved", "windowActivated", "currentDesktopChanged", "currentActivityChanged",
 "screensChanged", "virtualScreenGeometryChanged", "stackingOrderChanged"].forEach(function (s) {
    if (workspace[s]) {
        workspace[s].connect(send);
    }
});
send();

// Mauszeiger für das Fang-Spiel, gedrosselt auf ~30/s
var lastCursor = 0;
workspace.cursorPosChanged.connect(function () {
    var now = Date.now();
    if (now - lastCursor < 33) {
        return;
    }
    lastCursor = now;
    var p = workspace.cursorPos;
    callDBus("de.bangl.TaskbarCat", "/", "de.bangl.TaskbarCat", "cursor", p.x + " " + p.y);
});
