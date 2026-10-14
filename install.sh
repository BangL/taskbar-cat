#!/bin/sh
# Taskbar-Cat lokal für den aktuellen Benutzer einrichten (kein root).
#
#   ./install.sh              Desktop-Eintrag + Icon installieren
#   ./install.sh --autostart  zusätzlich beim Anmelden starten
#   ./install.sh --uninstall  Einträge wieder entfernen
#
# Der Exec-Pfad wird hier ermittelt, nicht fest eingetragen: ist das Paket
# installiert (pip/AUR), wird dessen Startprogramm benutzt, sonst der Clone.
set -eu

src=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
apps=${XDG_DATA_HOME:-$HOME/.local/share}/applications
icons=${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps
autostart=${XDG_CONFIG_HOME:-$HOME/.config}/autostart
desktop=taskbar-cat.desktop

if [ "${1:-}" = "--uninstall" ]; then
    rm -fv "$apps/$desktop" "$autostart/$desktop" "$icons/taskbar-cat.png"
    command -v update-desktop-database >/dev/null && update-desktop-database "$apps" || true
    exit 0
fi

if bin=$(command -v taskbar-cat 2>/dev/null); then
    exec_line="Exec=$bin"
    path_line=
else
    exec_line="Exec=$(command -v python3) -m taskbar_cat"
    path_line="Path=$src"
    echo "taskbar-cat nicht im PATH -> starte aus $src"
fi

mkdir -p "$apps" "$icons"
sed -e "s|^Exec=.*|$exec_line|" "$src/data/$desktop" > "$apps/$desktop"
if [ -n "$path_line" ]; then
    printf '%s\n' "$path_line" >> "$apps/$desktop"
fi
python3 -m taskbar_cat.sprites --icon "$icons/taskbar-cat.png"
command -v update-desktop-database >/dev/null && update-desktop-database "$apps" || true
echo "installiert: $apps/$desktop"

if [ "${1:-}" = "--autostart" ]; then
    mkdir -p "$autostart"
    cp "$apps/$desktop" "$autostart/$desktop"
    echo "Autostart: $autostart/$desktop"
fi
