// Taskbar-Cat Fenster-Sensor für GNOME Shell. Gegenstück zum KWin-Script:
// meldet Monitore, Arbeitsflächen und begehbare Fenster an die App
// (de.bangl.TaskbarCat) - dasselbe JSON, dieselben D-Bus-Methoden.
//
// Gesendet wird nur, solange die Katze läuft; den D-Bus-Namen beobachten wir.
// Änderungen werden auf einen Tick gebündelt, damit die Shell nicht ruckelt.

import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const SERVICE = 'de.bangl.TaskbarCat';
const OBJECT = '/';
const SEND_MS = 33;      // Bursts beim Fensterziehen bündeln
const CURSOR_MS = 33;    // wie im KWin-Script: ~30 Meldungen je Sekunde

function rect(r) {
    return {x: r.x, y: r.y, w: r.width, h: r.height};
}

function monitorManager() {
    if (global.backend && global.backend.get_monitor_manager)
        return global.backend.get_monitor_manager();
    return Meta.MonitorManager.get();   // ältere Shell-Versionen
}

function isMaximized(w) {
    if (typeof w.is_maximized === 'function')
        return !!w.is_maximized();
    return !!(w.maximized_horizontally && w.maximized_vertically);
}

export default class TaskbarCatSensor extends Extension {
    enable() {
        this._links = [];            // [GObject, handlerId]
        this._watched = new Map();   // MetaWindow -> handlerIds
        this._running = false;
        this._sendTimer = 0;
        this._cursorTimer = 0;
        this._lastCursor = null;
        this._nameWatch = Gio.bus_watch_name(
            Gio.BusType.SESSION, SERVICE, Gio.BusNameWatcherFlags.NONE,
            () => this._appAppeared(),
            () => this._appVanished());
    }

    disable() {
        if (this._nameWatch)
            Gio.bus_unwatch_name(this._nameWatch);
        this._nameWatch = 0;
        this._appVanished();
    }

    // --- An- und Abmelden der App ---

    _appAppeared() {
        if (this._running)
            return;
        this._running = true;
        this._connectAll();
        this._cursorTimer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, CURSOR_MS, () => {
            this._sendCursor();
            return GLib.SOURCE_CONTINUE;
        });
        this._send();
    }

    _appVanished() {
        this._running = false;
        for (const [obj, id] of this._links)
            obj.disconnect(id);
        this._links = [];
        for (const [win, ids] of this._watched) {
            for (const id of ids)
                win.disconnect(id);
        }
        this._watched.clear();
        for (const name of ['_sendTimer', '_cursorTimer']) {
            if (this[name])
                GLib.source_remove(this[name]);
            this[name] = 0;
        }
        this._lastCursor = null;
    }

    // --- Signale ---

    _link(obj, signal, handler) {
        if (!obj)
            return;
        try {
            this._links.push([obj, obj.connect(signal, handler)]);
        } catch (e) {
            // Signal gibt es in dieser Shell-Version nicht - nicht schlimm
            logError(e, `taskbar-cat: ${signal} nicht verfügbar`);
        }
    }

    _connectAll() {
        const queue = () => this._queueSend();
        const display = global.display;
        this._link(display, 'window-created', (_d, win) => {
            this._watch(win);
            this._queueSend();
        });
        for (const signal of ['restacked', 'grab-op-end', 'in-fullscreen-changed',
                              'workareas-changed'])
            this._link(display, signal, queue);
        this._link(monitorManager(), 'monitors-changed', queue);
        this._link(global.workspace_manager, 'active-workspace-changed', queue);
        this._link(global.window_manager, 'minimize', queue);
        this._link(global.window_manager, 'unminimize', queue);
        this._link(global.window_manager, 'size-change', queue);
        this._link(global.window_manager, 'map', queue);
        this._link(global.window_manager, 'destroy', queue);
        for (const win of global.display.list_all_windows())
            this._watch(win);
    }

    _watch(win) {
        if (this._watched.has(win))
            return;
        const queue = () => this._queueSend();
        const ids = [];
        for (const signal of ['position-changed', 'size-changed', 'workspace-changed',
                              'notify::minimized', 'notify::fullscreen',
                              'notify::maximized-horizontally', 'notify::maximized-vertically',
                              'notify::window-type', 'notify::on-all-workspaces']) {
            try {
                ids.push(win.connect(signal, queue));
            } catch (e) {
                // Eigenschaft fehlt in dieser Shell-Version
            }
        }
        ids.push(win.connect('unmanaged', () => {
            for (const id of this._watched.get(win) ?? [])
                win.disconnect(id);
            this._watched.delete(win);
            this._queueSend();
        }));
        this._watched.set(win, ids);
    }

    // --- Senden ---

    _call(method, text) {
        if (!this._running)
            return;
        Gio.DBus.session.call(
            SERVICE, OBJECT, SERVICE, method, new GLib.Variant('(s)', [text]), null,
            Gio.DBusCallFlags.NO_AUTO_START, -1, null, null);
    }

    _queueSend() {
        if (this._sendTimer || !this._running)
            return;
        this._sendTimer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, SEND_MS, () => {
            this._sendTimer = 0;
            this._send();
            return GLib.SOURCE_REMOVE;
        });
    }

    _send() {
        if (!this._running)
            return;
        try {
            this._call('update', JSON.stringify(
                {outputs: this._outputs(), windows: this._windows()}));
        } catch (e) {
            logError(e, 'taskbar-cat: Update nicht gesendet');
        }
    }

    _sendCursor() {
        const [x, y] = global.get_pointer();
        if (this._lastCursor && this._lastCursor[0] === x && this._lastCursor[1] === y)
            return;
        this._lastCursor = [x, y];
        this._call('cursor', `${x} ${y}`);
    }

    // --- Weltmodell ---

    _outputs() {
        const mm = monitorManager();
        const workspace = global.workspace_manager.get_active_workspace();
        const out = [];
        for (const monitor of mm.get_monitors()) {
            if (!monitor.is_active())
                continue;
            const name = monitor.get_connector();
            const index = mm.get_monitor_for_connector(name);
            if (index < 0)
                continue;
            out.push({
                name,
                geometry: rect(global.display.get_monitor_geometry(index)),
                workArea: rect(workspace.get_work_area_for_monitor(index)),
            });
        }
        return out;
    }

    _relevant(win, workspace) {
        if (!win.located_on_workspace(workspace))
            return false;
        const type = win.get_window_type();
        if (type === Meta.WindowType.NORMAL)
            return !win.minimized;
        // Panels und Docks: die Katze soll auch auf Leisten laufen können
        return type === Meta.WindowType.DOCK;
    }

    _windows() {
        const workspace = global.workspace_manager.get_active_workspace();
        const all = global.display.list_all_windows();
        const stacked = global.display.sort_windows_by_stacking(all);
        const out = [];
        stacked.forEach((win, stack) => {
            if (!this._relevant(win, workspace))
                return;
            const g = win.get_frame_rect();
            out.push({
                id: String(win.get_stable_sequence()),
                x: g.x, y: g.y, w: g.width, h: g.height,
                stack,
                pid: win.get_pid(),
                fullScreen: !!win.is_fullscreen(),
                maximized: isMaximized(win),
                panel: win.get_window_type() === Meta.WindowType.DOCK,
            });
        });
        return out;
    }
}
