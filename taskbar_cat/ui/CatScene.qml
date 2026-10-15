import QtQuick

// Alles Sichtbare eines Overlays, unabhängig davon, wie das Fenster zustande
// kommt: Katze, Möbel, UFO, Debug-Linien und die Maus. Koordinaten sind lokal
// zum Monitor; Python setzt Position, Frame und Input-Region.
//
// Die Fensterhüllen (overlay.qml für Layer-Shell, overlay_x11.qml für X11)
// binden diese Szene nur ein. Neue Grafik gehört hierher und gilt damit für
// jede Arbeitsumgebung.
Item {
    id: scene

    property url atlas
    property real catX: 0
    property real catY: 0
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
        model: scene.platforms
        Rectangle {
            x: modelData.x
            y: modelData.y
            width: modelData.w
            height: modelData.h
            color: modelData.color
        }
    }

    Image {
        source: scene.beamSource
        visible: scene.ufoVisible && scene.beamOn
        opacity: 0.55 + 0.15 * Math.sin(scene.ufoTime * 12)
        x: Math.round(scene.ufoX - scene.beamWidth / 2)
        y: Math.round(scene.beamTop)
        width: scene.beamWidth
        height: Math.max(0, scene.beamBottom - scene.beamTop)
    }

    Repeater {
        model: scene.furnitureBack
        Image {
            source: scene.furnitureAtlas
            sourceClipRect: Qt.rect(modelData.sx, modelData.sy, 32, modelData.h)
            x: Math.round(modelData.x - width / 2)
            y: Math.round(modelData.y - height)
            width: scene.spriteSize
            height: scene.spriteSize * modelData.h / 32
            smooth: false
        }
    }

    Image {
        id: sprite
        source: scene.atlas
        sourceClipRect: Qt.rect(scene.srcX, scene.srcY, 32, 32)
        x: Math.round(scene.catX - width / 2)
        y: Math.round(scene.catY - height)
        width: scene.spriteSize
        height: scene.spriteSize
        smooth: false
        mirror: scene.flip
        visible: scene.catVisible
    }

    Repeater {
        model: scene.furnitureFront
        Image {
            source: scene.furnitureAtlas
            sourceClipRect: Qt.rect(modelData.sx, modelData.sy, 32, modelData.h)
            x: Math.round(modelData.x - width / 2)
            y: Math.round(modelData.y - height)
            width: scene.spriteSize
            height: scene.spriteSize * modelData.h / 32
            smooth: false
        }
    }

    Image {
        source: scene.ufoSource
        visible: scene.ufoVisible
        x: Math.round(scene.ufoX - width / 2)
        y: Math.round(scene.ufoY - height / 2 + 3 * Math.sin(scene.ufoTime * 4))
        width: scene.ufoWidth
        height: scene.ufoWidth / 2
        smooth: false
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        hoverEnabled: true
        onPressed: (m) => scene.catPressed(m.x, m.y, m.button)
        onPositionChanged: (m) => scene.catMoved(m.x, m.y, m.buttons)
        onReleased: (m) => scene.catReleased(m.x, m.y, m.button)
        onCanceled: scene.catCanceled()
    }
}
