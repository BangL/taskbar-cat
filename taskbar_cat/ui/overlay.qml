import QtQuick
import QtQuick.Window
import org.kde.layershell 1.0 as LayerShell

// Transparentes Vollbild-Overlay für einen Monitor. Koordinaten sind lokal
// zum Monitor; Python setzt Position/Frame und die Input-Region.
Window {
    id: win
    visible: false
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus

    LayerShell.Window.layer: LayerShell.Window.LayerOverlay
    LayerShell.Window.anchors: LayerShell.Window.AnchorTop | LayerShell.Window.AnchorBottom
                               | LayerShell.Window.AnchorLeft | LayerShell.Window.AnchorRight
    LayerShell.Window.exclusionZone: -1
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityNone
    LayerShell.Window.scope: "taskbar-cat"

    property url atlas
    property real catX: 0
    property real catY: 0
    property int srcX: 0
    property int srcY: 0
    property bool flip: false
    property bool catVisible: false
    property var platforms: []

    signal catPressed(real x, real y, int button)
    signal catMoved(real x, real y, int buttons)
    signal catReleased(real x, real y, int button)
    signal catCanceled()

    Repeater {
        model: win.platforms
        Rectangle {
            x: modelData.x
            y: modelData.y
            width: modelData.w
            height: modelData.h
            color: modelData.color
        }
    }

    Image {
        id: sprite
        source: win.atlas
        sourceClipRect: Qt.rect(win.srcX, win.srcY, 32, 32)
        x: Math.round(win.catX - width / 2)
        y: Math.round(win.catY - height)
        width: 96
        height: 96
        smooth: false
        mirror: win.flip
        visible: win.catVisible
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        hoverEnabled: true
        onPressed: (m) => win.catPressed(m.x, m.y, m.button)
        onPositionChanged: (m) => win.catMoved(m.x, m.y, m.buttons)
        onReleased: (m) => win.catReleased(m.x, m.y, m.button)
        onCanceled: win.catCanceled()
    }
}
