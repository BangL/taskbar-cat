import QtQuick

// Alles Sichtbare eines Overlays, unabhängig davon, wie das Fenster zustande
// kommt: Katze, Möbel, UFO, Debug-Linien und die Maus. Koordinaten sind lokal
// zum Monitor; Python setzt Position, Frame und Input-Region.
//
// Die Fensterhüllen (overlay.qml für Layer-Shell, overlay_x11.qml für X11)
// binden diese Szene nur ein. Neue Grafik gehört hierher und gilt damit für
// jede Arbeitsumgebung.
//
// Bilder erscheinen nur in ihren sichtbaren Stücken (ClippedImage). Ohne ein
// Fenster davor ist das Stück das ganze Bild; steht ein Kratzbaum hinter den
// Fenstern, bleiben nur die Streifen daneben stehen - und die Katze darin
// verschwindet mit ihm.
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
    // Sichtbare Stücke der Katze, lokal: {x, y, w, h}; ohne Fenster davor eins über alles
    property var catPieces: []
    property int spriteSize: 96
    property var platforms: []
    // Möbel: je {x, y (Mitte unten, lokal), sx, sy, h (Frame im Atlas), clip}; vorn = vor der Katze
    property url furnitureAtlas
    property var furnitureBack: []
    property var furnitureFront: []
    // Große Kratzbäume: je {kind, src (image://bigtree/...), x, y, w, h, clip} (lokal, links oben)
    property var bigtrees: []
    // Bällchen der Kratzbäume: {x, y (Aufhängung), len (Faden), s (Pixelgröße), color,
    // string, outline, clip};
    // toyAngles: Auslenkung je Bällchen in rad (positiv = nach rechts)
    property var bigtreeToys: []
    // Fliegen über verschüttetem Futter: flyPos flach je Fliege x, y (lokal), Flügel oben (0/1)
    property int flyCount: 0
    property var flyPos: []
    property real flySize: 1
    property var toyAngles: []
    // Vor der Katze: durchhängende Hängematte oder Höhlenwand: {src (.../front), x, y, w, h, clip}
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
    signal bigtreeWheel(string kind, real dx, real dy, bool ctrl)

    // Ein Bild, von dem nur die Stücke in pieces gezeichnet werden. Das Bild selbst liegt
    // bei (ix, iy) und ist iw x ih groß, unabhängig davon, wie es zerschnitten ist.
    component ClippedImage: Repeater {
        property var pieces: []
        property url src
        property real ix: 0
        property real iy: 0
        property real iw: 0
        property real ih: 0
        property rect part: Qt.rect(0, 0, 0, 0)   // Ausschnitt der Quelle (Atlas), leer = ganz
        property bool mirrored: false
        property real alpha: 1
        property bool cached: true
        property bool shown: true

        model: pieces
        Item {
            x: modelData.x
            y: modelData.y
            width: modelData.w
            height: modelData.h
            clip: true
            visible: shown
            Image {
                x: Math.round(ix) - parent.x
                y: Math.round(iy) - parent.y
                width: iw
                height: ih
                source: src
                sourceClipRect: part
                mirror: mirrored
                opacity: alpha
                cache: cached
                smooth: false
            }
        }
    }

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
            readonly property var tree: modelData
            ClippedImage {
                pieces: tree.clip
                src: tree.src
                ix: tree.x
                iy: tree.y
                iw: Math.round(tree.w)
                ih: Math.round(tree.h)
                cached: false
            }
            // Mausrad: hoch/runter = Höhe, seitlich = Breite, mit Strg auch hoch/runter
            // die Breite (Tasten gehen an die Katze). Über verdeckten Stellen kommt hier
            // nichts an, die liegen außerhalb der Input-Region.
            MouseArea {
                x: Math.round(tree.x)
                y: Math.round(tree.y)
                width: Math.round(tree.w)
                height: Math.round(tree.h)
                acceptedButtons: Qt.NoButton
                onWheel: (e) => scene.bigtreeWheel(tree.kind, e.angleDelta.x, e.angleDelta.y,
                                                   (e.modifiers & Qt.ControlModifier) !== 0)
            }
        }
    }

    // Bällchen wie im Baumbild (Faden 1 px, Kugel 3 px, Kontur 1 px), drehen sich um die Aufhängung
    Repeater {
        model: scene.bigtreeToys
        Item {
            readonly property var toy: modelData
            readonly property real angle: scene.toyAngles[index] || 0
            Repeater {
                model: toy.clip
                Item {
                    // s gehört hierher und nicht ans Bällchen darunter: QML sucht einen
                    // Namen nur im Wurzelobjekt der Komponente, nicht beim Eltern-Item
                    readonly property real s: toy.s
                    x: modelData.x
                    y: modelData.y
                    width: modelData.w
                    height: modelData.h
                    clip: true
                    Item {
                        x: Math.round(toy.x - width / 2) - parent.x
                        y: Math.round(toy.y) - parent.y
                        width: 5 * s
                        height: toy.len + 4 * s
                        transformOrigin: Item.Top
                        rotation: -angle * 180 / Math.PI
                        Rectangle {
                            x: s
                            width: 3 * s
                            height: toy.len
                            color: toy.outline
                            Rectangle { x: s; width: s; height: parent.height; color: toy.string }
                        }
                        Rectangle {
                            y: toy.len - s
                            width: 5 * s
                            height: 5 * s
                            radius: width / 2          // rund: sieht auch schräg wie eine Kugel aus
                            antialiasing: false        // Pixel-Optik wie der Rest
                            color: toy.outline
                            Rectangle {
                                x: s; y: s; width: 3 * s; height: 3 * s
                                radius: width / 2; antialiasing: false; color: toy.color
                            }
                        }
                    }
                }
            }
        }
    }

    Repeater {
        model: scene.furnitureBack
        ClippedImage {
            pieces: modelData.clip
            src: scene.furnitureAtlas
            part: Qt.rect(modelData.sx, modelData.sy, 32, modelData.h)
            ix: modelData.x - scene.spriteSize / 2
            iy: modelData.y - scene.spriteSize * modelData.h / 32
            iw: scene.spriteSize
            ih: scene.spriteSize * modelData.h / 32
        }
    }

    ClippedImage {
        pieces: scene.catPieces
        shown: scene.catVisible
        src: scene.atlas
        part: Qt.rect(scene.srcX, scene.srcY, 32, 32)
        ix: scene.catX - scene.spriteSize / 2
        iy: scene.catY - scene.spriteSize
        iw: scene.spriteSize
        ih: scene.spriteSize
        mirrored: scene.flip
        alpha: scene.catOpacity
    }

    Repeater {
        model: scene.bigtreeFronts
        ClippedImage {
            pieces: modelData.clip
            src: modelData.src
            ix: modelData.x
            iy: modelData.y
            iw: Math.round(modelData.w)
            ih: Math.round(modelData.h)
            cached: false
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
        ClippedImage {
            pieces: modelData.clip
            src: scene.furnitureAtlas
            part: Qt.rect(modelData.sx, modelData.sy, 32, modelData.h)
            ix: modelData.x - scene.spriteSize / 2
            iy: modelData.y - scene.spriteSize * modelData.h / 32
            iw: scene.spriteSize
            ih: scene.spriteSize * modelData.h / 32
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
