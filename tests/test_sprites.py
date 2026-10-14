from PyQt6.QtGui import QImage

from taskbar_cat import sprites

FRAME = 32


def frame_image(atlas, anim, mood, i):
    x, y = sprites.frame_origin(anim, mood, i)
    return atlas.copy(x, y, FRAME, FRAME)


def opaque(img):
    return sum(1 for y in range(img.height()) for x in range(img.width()) if img.pixelColor(x, y).alpha() > 0)


def load(tmp_path):
    return QImage(str(sprites.ensure_atlas(tmp_path)))


def test_atlas_dimensions(qapp, tmp_path):
    img = load(tmp_path)
    assert img.width() == FRAME * max(sprites.ANIMS.values())
    assert img.height() == FRAME * len(sprites.ANIMS) * len(sprites.MOODS)


def test_every_frame_has_pixels(qapp, tmp_path):
    img = load(tmp_path)
    for anim, n in sprites.ANIMS.items():
        for mood in sprites.MOODS:
            for i in range(n):
                assert opaque(frame_image(img, anim, mood, i)) >= 50, (anim, mood, i)


def test_frame_index_wraps():
    assert sprites.frame_origin("walk", "normal", 5) == sprites.frame_origin("walk", "normal", 1)


def test_frames_differ_within_walk(qapp, tmp_path):
    img = load(tmp_path)
    assert frame_image(img, "walk", "normal", 0) != frame_image(img, "walk", "normal", 1)


def test_sick_differs_from_normal(qapp, tmp_path):
    img = load(tmp_path)
    assert frame_image(img, "sit", "sick", 0) != frame_image(img, "sit", "normal", 0)
    assert frame_image(img, "sit", "sad", 0) != frame_image(img, "sit", "normal", 0)


def test_cached_atlas_reused(qapp, tmp_path):
    p = sprites.ensure_atlas(tmp_path)
    m = p.stat().st_mtime_ns
    assert sprites.ensure_atlas(tmp_path) == p
    assert p.stat().st_mtime_ns == m


def test_head_icon(qapp):
    img = sprites.head_icon("sad")
    assert (img.width(), img.height()) == (32, 32)
    assert opaque(img) >= 100


def test_climb_and_hang_frames(qapp, tmp_path):
    img = load(tmp_path)
    assert sprites.ANIMS["climb"] == 4 and sprites.ANIMS["hang"] == 2
    assert frame_image(img, "climb", "normal", 0) != frame_image(img, "climb", "normal", 1)
    assert frame_image(img, "hang", "normal", 0) != frame_image(img, "hang", "normal", 1)


def test_play_frames(qapp, tmp_path):
    img = load(tmp_path)
    for anim in ("crouch", "swipe", "cheer"):
        assert sprites.ANIMS[anim] == 2
        assert frame_image(img, anim, "normal", 0) != frame_image(img, anim, "normal", 1)
