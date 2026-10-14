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
    property int spriteSize: 96
    property var platforms: []
    // UFO-Easter-Egg (Mitte der Untertasse, Strahl von beamTop bis beamBottom)
    property url ufoSource
    property url beamSource
    property bool ufoVisible: false
    property real ufoX: 0
    property real ufoY: 0
    property int ufoWidth: 150
    property real ufoTime: 0
    property bool beamOn: false
    property real beamTop: 0
    property real beamBottom: 0
    property real beamWidth: 120

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
        source: win.beamSource
        visible: win.ufoVisible && win.beamOn
        opacity: 0.55 + 0.15 * Math.sin(win.ufoTime * 12)
        x: Math.round(win.ufoX - win.beamWidth / 2)
        y: Math.round(win.beamTop)
        width: win.beamWidth
        height: Math.max(0, win.beamBottom - win.beamTop)
    }

    Image {
        id: sprite
        source: win.atlas
        sourceClipRect: Qt.rect(win.srcX, win.srcY, 32, 32)
        x: Math.round(win.catX - width / 2)
        y: Math.round(win.catY - height)
        width: win.spriteSize
        height: win.spriteSize
        smooth: false
        mirror: win.flip
        visible: win.catVisible
    }

    Image {
        source: win.ufoSource
        visible: win.ufoVisible
        x: Math.round(win.ufoX - width / 2)
        y: Math.round(win.ufoY - height / 2 + 3 * Math.sin(win.ufoTime * 4))
        width: win.ufoWidth
        height: win.ufoWidth / 2
        smooth: false
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
