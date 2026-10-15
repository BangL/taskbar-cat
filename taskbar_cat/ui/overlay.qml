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
    property real catOpacity: 1
    property int srcX: 0
    property int srcY: 0
    property bool flip: false
    property bool catVisible: false
    property int spriteSize: 96
    property var platforms: []
    // Möbel: je {x, y (Mitte unten, lokal), sx, sy, h (Frame im Atlas)}; vorn = vor der Katze
    property url furnitureAtlas
    property var furnitureBack: []
    property var furnitureFront: []
    // Große Kratzbäume: je {kind, src (image://bigtree/...), x, y, w, h} (lokal, links oben)
    property var bigtrees: []
    // Bällchen der großen Kratzbäume: {x, y (Aufhängung), len (Faden), s (Pixelgröße), color,
    // string, outline};
    // toyAngles: Auslenkung je Bällchen in rad (positiv = nach rechts)
    property var bigtreeToys: []
    property var toyAngles: []
    // Vor der Katze: durchhängende Hängematte oder Höhlenwand: {src (.../front), x, y, w, h}
    property var bigtreeFronts: []
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
    signal bigtreeWheel(string kind, real dx, real dy)

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

    Repeater {
        model: win.bigtrees
        Item {
            x: Math.round(modelData.x)
            y: Math.round(modelData.y)
            width: Math.round(modelData.w)
            height: Math.round(modelData.h)
            Image {
                anchors.fill: parent
                source: modelData.src
                smooth: false
                cache: false
            }
            // Mausrad: hoch/runter = Höhe, seitlich = Breite (Tasten gehen an die Katze)
            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.NoButton
                onWheel: (e) => win.bigtreeWheel(modelData.kind, e.angleDelta.x, e.angleDelta.y)
            }
        }
    }

    // Bällchen wie im Baumbild (Faden 1 px, Kugel 3 px, Kontur 1 px), drehen sich um die Aufhängung
    Repeater {
        model: win.bigtreeToys
        Item {
            readonly property real s: modelData.s
            x: Math.round(modelData.x - width / 2)
            y: Math.round(modelData.y)
            width: 5 * s
            height: modelData.len + 4 * s
            transformOrigin: Item.Top
            rotation: -(win.toyAngles[index] || 0) * 180 / Math.PI
            Rectangle {
                x: s
                width: 3 * s
                height: modelData.len
                color: modelData.outline
                Rectangle { x: s; width: s; height: parent.height; color: modelData.string }
            }
            Rectangle {
                y: modelData.len - s
                width: 5 * s
                height: 5 * s
                radius: width / 2          // rund: sieht auch schräg wie eine Kugel aus
                antialiasing: false        // Pixel-Optik wie der Rest
                color: modelData.outline
                Rectangle {
                    x: s; y: s; width: 3 * s; height: 3 * s
                    radius: width / 2; antialiasing: false; color: modelData.color
                }
            }
        }
    }

    Repeater {
        model: win.furnitureBack
        Image {
            source: win.furnitureAtlas
            sourceClipRect: Qt.rect(modelData.sx, modelData.sy, 32, modelData.h)
            x: Math.round(modelData.x - width / 2)
            y: Math.round(modelData.y - height)
            width: win.spriteSize
            height: win.spriteSize * modelData.h / 32
            smooth: false
        }
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
        opacity: win.catOpacity
        visible: win.catVisible
    }

    Repeater {
        model: win.bigtreeFronts
        Image {
            source: modelData.src
            x: Math.round(modelData.x)
            y: Math.round(modelData.y)
            width: Math.round(modelData.w)
            height: Math.round(modelData.h)
            smooth: false
            cache: false
        }
    }

    Repeater {
        model: win.furnitureFront
        Image {
            source: win.furnitureAtlas
            sourceClipRect: Qt.rect(modelData.sx, modelData.sy, 32, modelData.h)
            x: Math.round(modelData.x - width / 2)
            y: Math.round(modelData.y - height)
            width: win.spriteSize
            height: win.spriteSize * modelData.h / 32
            smooth: false
        }
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
