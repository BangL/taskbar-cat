import QtQuick
import QtQuick.Window

// Overlay für GNOME und andere Umgebungen ohne Layer-Shell: ein X11-Fenster
// (über XWayland), das sich selbst positioniert und am Fenstermanager vorbei
// über allem liegt. Python setzt die Geometrie je Monitor.
Window {
    property alias scene: scene

    visible: false
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
           | Qt.WindowDoesNotAcceptFocus | Qt.X11BypassWindowManagerHint

    CatScene {
        id: scene
        anchors.fill: parent
    }
}
