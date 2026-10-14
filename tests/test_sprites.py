from PyQt6.QtGui import QColor, QImage

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


def enclosed_gaps(img, x0, y0):
    """Durchsichtige Pixel, die vom Rand des Frames aus nicht erreichbar sind."""
    from collections import deque

    f = FRAME
    solid = [[img.pixelColor(x0 + x, y0 + y).alpha() > 0 for y in range(f)] for x in range(f)]
    outside = [[False] * f for _ in range(f)]
    q = deque((x, y) for x in range(f) for y in range(f)
              if (x in (0, f - 1) or y in (0, f - 1)) and not solid[x][y])
    for x, y in q:
        outside[x][y] = True
    while q:
        x, y = q.popleft()
        for a, b in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= a < f and 0 <= b < f and not solid[a][b] and not outside[a][b]:
                outside[a][b] = True
                q.append((a, b))
    return [(x, y) for x in range(f) for y in range(f) if not solid[x][y] and not outside[x][y]]


def test_no_frame_shows_the_background_through(qapp, tmp_path):
    """Eingeschlossene Lücken lassen den Desktop durchblitzen."""
    img = load(tmp_path)
    for anim, n in sprites.ANIMS.items():
        for mood in sprites.MOODS:
            for i in range(n):
                x, y = sprites.frame_origin(anim, mood, i)
                assert enclosed_gaps(img, x, y) == [], (anim, mood, i)


# Posen, in denen der Koerper aufliegt (nicht nur schmale Pfoten wie beim Laufen)
RESTING = ("sit", "groom", "lie", "sleep", "purr", "cheer", "crouch")


def test_resting_poses_sit_on_the_ground(qapp, tmp_path):
    """Sonst klafft zwischen Katze und Fensterkante eine Lücke."""
    img = load(tmp_path)
    fur = sprites.Palette()
    for anim in RESTING:
        for i in range(sprites.ANIMS[anim]):
            x, y = sprites.frame_origin(anim, "normal", i)
            touching = sum(1 for dx in range(FRAME)
                           if img.pixelColor(x + dx, y + 30).alpha() > 0
                           and img.pixelColor(x + dx, y + 30).rgb() != fur.outline.rgb())
            assert touching >= 10, (anim, i, touching)


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


def test_whiskers_contrast_with_the_fur(qapp):
    assert sprites.Palette("#e8913a").whisker.value() < QColor("#e8913a").value()
    assert sprites.Palette("#222222").whisker.value() > QColor("#222222").value()


def test_muzzle_is_drawn(qapp):
    """Nase und Schnauzenstriche gehören zu jedem Kopf."""
    img = sprites.head_icon("normal")
    seen = colors(img)
    assert sprites.NOSE.name() in seen
    assert sprites.Palette().whisker.name() in seen


def test_head_icon(qapp):
    img = sprites.head_icon("sad")
    assert (img.width(), img.height()) == (32, 32)
    assert opaque(img) >= 100


def test_climb_and_hang_frames(qapp, tmp_path):
    img = load(tmp_path)
    assert sprites.ANIMS["climb"] == 4 and sprites.ANIMS["hang"] == 2
    assert frame_image(img, "climb", "normal", 0) != frame_image(img, "climb", "normal", 1)
    assert frame_image(img, "hang", "normal", 0) != frame_image(img, "hang", "normal", 1)


def test_groom_frames(qapp, tmp_path):
    img = load(tmp_path)
    assert sprites.ANIMS["groom"] == 2
    assert frame_image(img, "groom", "normal", 0) != frame_image(img, "groom", "normal", 1)
    assert frame_image(img, "groom", "normal", 0) != frame_image(img, "sit", "normal", 0)


def test_crawl_is_flat_enough(qapp, tmp_path):
    """Die geduckte Pose muss deutlich niedriger sein als die aufrechte."""
    img = load(tmp_path)

    def top(anim, i):
        x, y = sprites.frame_origin(anim, "normal", i)
        return min(dy for dy in range(FRAME)
                   if any(img.pixelColor(x + dx, y + dy).alpha() > 0 for dx in range(FRAME)))

    assert sprites.ANIMS["crawl"] == 4
    for i in range(4):
        assert top("crawl", i) >= top("walk", i) + 6
    assert frame_image(img, "crawl", "normal", 0) != frame_image(img, "crawl", "normal", 1)


def test_vomit_frames(qapp, tmp_path):
    img = load(tmp_path)
    assert sprites.ANIMS["vomit"] == 2
    assert frame_image(img, "vomit", "normal", 0) != frame_image(img, "vomit", "normal", 1)
    assert sprites.PUKE.name() in colors(frame_image(img, "vomit", "normal", 0))


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
    assert pal.whisker.value() > pal.fur.value()
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


def test_ufo_images(qapp, tmp_path):
    ufo, beam = sprites.ensure_ufo(tmp_path)
    for path, size in ((ufo, (32, 16)), (beam, (64, 128))):
        img = QImage(str(path))
        assert (img.width(), img.height()) == size and opaque(img) > 0
    assert sprites.ensure_ufo(tmp_path) == (ufo, beam)
    sprites.ensure_atlas(tmp_path)
    assert ufo.exists() and beam.exists()   # Atlas-Aufräumen lässt das UFO stehen


# --- Tigerung ---

def dark_pixels(img, anim="sit"):
    frame = frame_image(img, anim, "normal", 0)
    dark = sprites.Palette().dark.rgb()
    return sum(1 for y in range(FRAME) for x in range(FRAME)
               if frame.pixelColor(x, y).alpha() > 0 and frame.pixelColor(x, y).rgb() == dark)


def test_spread_picks_evenly():
    pts = [1, 2, 3, 4]
    assert sprites._spread(pts, 0) == []
    assert sprites._spread(pts, -1) == []
    assert sprites._spread(pts, 0.5) == [2, 4]
    assert sprites._spread(pts, 1) == pts
    assert sprites._spread(pts, 5) == pts


def test_tabby_adds_and_removes_stripes(qapp, tmp_path):
    counts = [dark_pixels(QImage(str(sprites.ensure_atlas(tmp_path, sprites.FUR_DEFAULT, t))))
              for t in (0, 100, 200)]
    assert counts[0] < counts[1] < counts[2]


def test_tabby_zero_keeps_the_other_details(qapp, tmp_path):
    """Ohne Streifen bleiben Beintrennung und Schwanzspitze stehen."""
    assert dark_pixels(QImage(str(sprites.ensure_atlas(tmp_path, sprites.FUR_DEFAULT, 0)))) > 0


def test_atlas_cached_per_tabby(qapp, tmp_path):
    normal = sprites.ensure_atlas(tmp_path, sprites.FUR_DEFAULT, 100)
    full = sprites.ensure_atlas(tmp_path, sprites.FUR_DEFAULT, 200)
    assert normal != full and full.exists()
    assert sprites.ensure_atlas(tmp_path, sprites.FUR_DEFAULT, 200) == full
