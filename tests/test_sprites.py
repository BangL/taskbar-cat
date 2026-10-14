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


# --- Fellfarbe ---

def colors(img):
    return {img.pixelColor(x, y).name() for y in range(img.height()) for x in range(img.width())
            if img.pixelColor(x, y).alpha() > 0}


def test_default_palette_unchanged(qapp):
    """Die Vorgabe muss die alten, handgewählten Farbwerte ergeben."""
    pal = sprites.Palette()
    assert (pal.fur.name(), pal.dark.name(), pal.outline.name()) == ("#e8913a", "#8a4a1c", "#3b2414")


def test_palette_follows_fur(qapp):
    pal = sprites.Palette("#8899aa")
    assert pal.fur.name() == "#8899aa"
    assert pal.dark.value() < pal.fur.value()
    assert pal.outline.value() < pal.dark.value()


def test_dark_fur_gets_lighter_outline(qapp):
    """Sonst verschwinden Kontur und Streifen in schwarzem Fell."""
    pal = sprites.Palette("#222222")
    assert pal.outline.value() > pal.fur.value()
    assert pal.dark.value() > pal.fur.value()
    assert pal.light.value() > pal.fur.value()
    assert pal.eye.value() > pal.fur.value()      # schwarze Augen in schwarzem Fell
    assert sprites.Palette().eye == sprites.EYE


def test_sick_is_green_whatever_the_fur(qapp):
    for fur in ("#e8913a", "#8899aa", "#ffffff", "#222222"):
        assert 60 <= sprites.Palette(fur, "sick").fur.hue() <= 110


def test_invalid_color_falls_back(qapp):
    assert sprites.Palette("keine farbe").fur.name() == sprites.Palette().fur.name()


def test_atlas_cached_per_color(qapp, tmp_path):
    orange = sprites.ensure_atlas(tmp_path)
    grey = sprites.ensure_atlas(tmp_path, "#8899aa")
    assert orange != grey and grey.exists()
    assert sprites.ensure_atlas(tmp_path, "#8899aa") == grey
    assert colors(frame_image(QImage(str(orange)), "sit", "normal", 0)) != \
        colors(frame_image(QImage(str(grey)), "sit", "normal", 0))


def test_atlas_uses_the_chosen_fur(qapp, tmp_path):
    img = QImage(str(sprites.ensure_atlas(tmp_path, "#8899AA")))
    assert "#8899aa" in colors(frame_image(img, "sit", "normal", 0))


def test_head_icon_follows_fur(qapp):
    assert colors(sprites.head_icon("normal", "#8899aa")) != colors(sprites.head_icon("normal"))


def test_old_atlas_versions_are_removed(qapp, tmp_path):
    stale = tmp_path / "atlas-v1.png"
    stale.write_bytes(b"alt")
    keep = sprites.ensure_atlas(tmp_path)
    sprites.ensure_atlas(tmp_path, "#8899aa")
    assert not stale.exists()
    assert keep.exists()
