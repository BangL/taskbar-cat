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
    // Fliegen über verschüttetem Futter: flyPos flach je Fliege x, y (lokal), Flügel oben (0/1)
    property int flyCount: 0
    property var flyPos: []
    property real flySize: 1
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
        model: scene.bigtrees
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
                onWheel: (e) => scene.bigtreeWheel(modelData.kind, e.angleDelta.x, e.angleDelta.y)
            }
        }
    }

    // Bällchen wie im Baumbild (Faden 1 px, Kugel 3 px, Kontur 1 px), drehen sich um die Aufhängung
    Repeater {
        model: scene.bigtreeToys
        Item {
            readonly property real s: modelData.s
            x: Math.round(modelData.x - width / 2)
            y: Math.round(modelData.y)
            width: 5 * s
            height: modelData.len + 4 * s
            transformOrigin: Item.Top
            rotation: -(scene.toyAngles[index] || 0) * 180 / Math.PI
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
        opacity: scene.catOpacity
        visible: scene.catVisible
    }

    Repeater {
        model: scene.bigtreeFronts
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
        model: scene.flyCount
        Item {
            readonly property real s: scene.flySize
            x: Math.round((scene.flyPos[3 * index] || 0) - s)
            y: Math.round((scene.flyPos[3 * index + 1] || 0) - s)
            Rectangle { width: 2 * scene.flySize; height: scene.flySize; color: "#1E1E1E" }   // Körper
            Rectangle {                                                                // Flügel
                x: scene.flyPos[3 * index + 2] ? 0 : scene.flySize
                y: -scene.flySize
                width: scene.flySize; height: scene.flySize
                color: "#CFE3F0"
            }
        }
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
