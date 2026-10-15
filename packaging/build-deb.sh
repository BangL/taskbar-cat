#!/bin/sh
# Baut taskbar-cat_<version>_all.deb aus dem Wheel in dist/.
#
#   python3 -m build --wheel
#   packaging/build-deb.sh [zielverzeichnis]
#
# Reines Python-Paket, daher Architecture: all. Der Code landet in
# /usr/lib/python3/dist-packages (Debian-Layout, nicht site-packages).
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
out=${1:-$root/dist}
wheel=$(ls "$root"/dist/taskbar_cat-*-py3-none-any.whl | tail -1)
version=$(basename "$wheel" | sed -E 's/^taskbar_cat-([^-]+)-.*/\1/')
build=$(mktemp -d)
trap 'rm -rf "$build"' EXIT

pkg=$build/taskbar-cat
install -d "$pkg/DEBIAN" "$pkg/usr/bin" "$pkg/usr/lib/python3/dist-packages" \
           "$pkg/usr/share/applications" "$pkg/usr/share/icons/hicolor/256x256/apps" \
           "$pkg/usr/share/doc/taskbar-cat"

# Wheel entpacken; --target legt kein Startskript an, das schreiben wir selbst
python3 -m pip install --quiet --no-deps --no-compile --no-warn-script-location \
    --target "$pkg/usr/lib/python3/dist-packages" "$wheel"
rm -rf "$pkg/usr/lib/python3/dist-packages/bin" \
       "$pkg/usr/lib/python3/dist-packages"/*.dist-info/RECORD \
       "$pkg/usr/lib/python3/dist-packages"/*.dist-info/direct_url.json \
       "$pkg/usr/lib/python3/dist-packages"/*.dist-info/REQUESTED

cat > "$pkg/usr/bin/taskbar-cat" <<'LAUNCHER'
#!/usr/bin/python3
import sys

from taskbar_cat.__main__ import main

sys.exit(main())
LAUNCHER
chmod 755 "$pkg/usr/bin/taskbar-cat"

install -m644 "$root/taskbar_cat/data/taskbar-cat.desktop" \
    "$pkg/usr/share/applications/taskbar-cat.desktop"
install -m644 "$root/LICENSE" "$pkg/usr/share/doc/taskbar-cat/copyright"
QT_QPA_PLATFORM=offscreen PYTHONPATH="$root" python3 -m taskbar_cat.sprites --icon \
    "$pkg/usr/share/icons/hicolor/256x256/apps/taskbar-cat.png"

cat > "$pkg/DEBIAN/control" <<CONTROL
Package: taskbar-cat
Version: $version
Section: games
Priority: optional
Architecture: all
Maintainer: BangL <henno.rickowski@gmail.com>
Depends: python3 (>= 3.10), python3-pyqt6, python3-pyqt6.qtquick
Recommends: qml6-module-org-kde-layershell, qt6-wayland, xwayland
Suggests: kwin-wayland, gnome-shell
Homepage: https://github.com/BangL/taskbar-cat
Description: Pixel-Art-Tamagotchi-Katze fuer KDE Plasma 6 und GNOME
 Eine Katze lebt am unteren Rand der Arbeitsflaeche und auf den Oberkanten
 von Fenstern, ueber alle Monitore hinweg. Sie will gefuettert und
 gestreichelt werden, spielt mit dem Mauszeiger und wird bei
 Vernachlaessigung traurig oder krank.
 .
 Unter KDE Plasma meldet ein KWin-Script die Fenster und braucht
 qml6-module-org-kde-layershell; unter GNOME uebernimmt das eine
 mitgelieferte Shell-Erweiterung, das Fenster laeuft dort ueber XWayland.
CONTROL

mkdir -p "$out"
deb=$out/taskbar-cat_${version}_all.deb
fakeroot dpkg-deb --build --root-owner-group "$pkg" "$deb" >/dev/null
echo "$deb"
