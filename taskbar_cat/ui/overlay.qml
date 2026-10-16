import QtQuick
import QtQuick.Window
import org.kde.layershell 1.0 as LayerShell

// Overlay für Wayland-Compositors mit wlr-layer-shell (KDE Plasma, sway,
// Hyprland): ein transparentes Vollbildfenster auf der Top-Ebene, das
// keinen Platz reserviert. Inhalt und Maus liegen in CatScene. Nicht Overlay:
// darüber lägen Katze und Möbel auch über Kontextmenüs, Tooltips und
// Benachrichtigungen (KWin stapelt Popups unter die Overlay-Ebene).
Window {
    property alias scene: scene

    visible: false
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus

    LayerShell.Window.layer: LayerShell.Window.LayerTop
    LayerShell.Window.anchors: LayerShell.Window.AnchorTop | LayerShell.Window.AnchorBottom
                               | LayerShell.Window.AnchorLeft | LayerShell.Window.AnchorRight
    LayerShell.Window.exclusionZone: -1
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityNone
    LayerShell.Window.scope: "taskbar-cat"

    CatScene {
        id: scene
        anchors.fill: parent
    }
}
