"""Silhouetten: Mausflächen folgen der Sprite-Form, nicht einem Kasten."""
import pytest
from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QColor, QImage

from taskbar_cat import paths, sprites
from taskbar_cat.ui.silhouette import Silhouettes, boxes, place


def _image(rows: list[str]) -> QImage:
    """'#' = deckend, '.' = durchsichtig."""
    img = QImage(len(rows[0]), len(rows), QImage.Format.Format_ARGB32)
    img.fill(QColor(0, 0, 0, 0))
    for y, row in enumerate(rows):
        for x, c in enumerate(row):
            if c == "#":
                img.setPixelColor(x, y, QColor(255, 0, 0, 255))
    return img


def test_empty_frame_has_no_area(qapp):
    assert boxes(_image(["....", "....", "....", "...."]), 0, 0, 4, 4) == ()


def test_full_frame_is_one_box(qapp):
    assert boxes(_image(["####"] * 4), 0, 0, 4, 4) == ((0, 0, 4, 4),)


def test_equal_rows_are_merged(qapp):
    """Drei gleiche Zeilen ergeben ein Rechteck, nicht drei."""
    assert boxes(_image([".##.", ".##.", ".##.", "...."]), 0, 0, 4, 4) == ((1, 0, 2, 3),)


def test_gap_in_a_row_becomes_two_boxes(qapp):
    assert boxes(_image(["#..#"]), 0, 0, 4, 1) == ((0, 0, 1, 1), (3, 0, 1, 1))


def test_reads_the_requested_frame_only(qapp):
    """Der Atlas enthält viele Frames nebeneinander; Koordinaten sind frame-lokal."""
    img = _image(["..##", "..##"])
    assert boxes(img, 2, 0, 2, 2) == ((0, 0, 2, 2),)
    assert boxes(img, 0, 0, 2, 2) == ()


def test_place_scales_and_moves(qapp):
    r = place(((1, 2, 2, 1),), left=100, top=200, scale=3.0)
    assert [(q.x(), q.y(), q.width(), q.height()) for q in r] == [(103, 206, 6, 3)]


def test_place_mirrors_horizontally(qapp):
    r = place(((0, 0, 1, 1),), left=0, top=0, scale=1.0, frame_width=4)
    assert (r[0].x(), r[0].width()) == (3, 1)


def test_place_leaves_no_gaps(qapp):
    """Aneinandergrenzende Flächen müssen sich auch nach dem Runden berühren."""
    rects = place(((0, 0, 1, 1), (1, 0, 1, 1), (2, 0, 1, 1)), 0, 0, 2.5)
    for a, b in zip(rects, rects[1:]):
        assert a.x() + a.width() == b.x()


def test_missing_atlas_falls_back_to_the_whole_frame(qapp):
    assert Silhouettes(None).shape(0, 0, 32, 32) == ((0, 0, 32, 32),)


def test_shapes_are_cached(qapp):
    s = Silhouettes(None)
    assert s.shape(0, 0, 8, 8) is s.shape(0, 0, 8, 8)


# --- gegen die echten Sprites ---

@pytest.fixture(scope="module")
def cat_shapes(tmp_path_factory, qapp):
    return Silhouettes(sprites.ensure_atlas(tmp_path_factory.mktemp("cache")))


def test_sitting_cat_leaves_its_corners_free(cat_shapes):
    """Oben links ist bei jeder Pose Luft - genau da sollen Klicks durchgehen."""
    sx, sy = sprites.frame_origin("sit", "normal", 0)
    rects = cat_shapes.rects(sx, sy, sprites.FRAME, sprites.FRAME, 0, 0, 3.0)
    assert rects, "die Katze hat überhaupt eine Fläche"
    assert not any(r.contains(QPoint(1, 1)) for r in rects)
    assert not any(r.contains(QPoint(94, 1)) for r in rects)


def test_cat_covers_much_less_than_its_box(cat_shapes):
    """Sonst wäre das Durchklicken wertlos."""
    sx, sy = sprites.frame_origin("sit", "normal", 0)
    rects = cat_shapes.rects(sx, sy, sprites.FRAME, sprites.FRAME, 0, 0, 3.0)
    covered = sum(r.width() * r.height() for r in rects)
    assert 0.15 < covered / (96 * 96) < 0.75


def test_rects_stay_inside_the_drawn_sprite(cat_shapes):
    """Die Flächen müssen dort liegen, wo QML das Sprite zeichnet."""
    size, left, top = 96, 500, 400
    sx, sy = sprites.frame_origin("walk", "normal", 1)
    for flip in (False, True):
        for r in cat_shapes.rects(sx, sy, sprites.FRAME, sprites.FRAME, left, top,
                                  size / sprites.FRAME, flip):
            assert left <= r.x() and r.x() + r.width() <= left + size
            assert top <= r.y() and r.y() + r.height() <= top + size


def test_furniture_has_a_shape_too(tmp_path, qapp):
    shapes = Silhouettes(sprites.ensure_furniture(tmp_path))
    fx, fy = sprites.furniture_origin("tree")
    h = sprites.furniture_height("tree")
    rects = shapes.rects(fx, fy, sprites.FRAME, h, 0, 0, 3.0)
    assert rects and len(rects) > 1   # ein Kratzbaum ist kein Vollquadrat
