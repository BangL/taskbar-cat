from taskbar_cat import sprites
from taskbar_cat.furniture import Furniture
from taskbar_cat.ui.inventory import InventoryDialog


def test_inventory_is_not_modal(qapp):
    assert not InventoryDialog(Furniture()).isModal()


def test_button_places_and_stores(qapp):
    f = Furniture()
    dlg = InventoryDialog(f)
    asked = []
    dlg.placeRequested.connect(lambda k: asked.append(("place", k)))
    dlg.storeRequested.connect(lambda k: asked.append(("store", k)))
    assert dlg._buttons["bed"].text() == "Aufstellen"
    dlg._buttons["bed"].click()
    f.bodies["bowl"].placed = True
    dlg.refresh()
    assert dlg._buttons["bowl"].text() == "Einlagern"
    dlg._buttons["bowl"].click()
    assert asked == [("place", "bed"), ("store", "bowl")]


def test_shows_food(qapp):
    f = Furniture()
    f.food = 2
    dlg = InventoryDialog(f)
    assert "2/3" in dlg._status["bowl"].text()


def test_furniture_frames_are_drawn(qapp):
    img = sprites.render_furniture()
    for name in sprites.FURNITURE_FRAMES:
        x0, y0 = sprites.furniture_origin(name)
        assert any(img.pixelColor(x0 + x, y0 + y).alpha() > 0
                   for x in range(sprites.FRAME) for y in range(sprites.FRAME)), name


def test_full_bowl_matches_the_one_she_eats_from(qapp):
    """Fress-Pose neben dem Napf: ihr eigener Napf liegt genau über dem Möbel."""
    from taskbar_cat.cat import BOWL_REACH
    atlas = sprites.render_atlas()
    furn = sprites.render_furniture()
    ax, ay = sprites.frame_origin("eat", "normal", 0)
    fx, fy = sprites.furniture_origin("bowl_3")
    for x in range(sprites.FRAME - BOWL_REACH):
        for y in range(sprites.FRAME):
            c = furn.pixelColor(fx + x, fy + y)
            if c == sprites.BOWL:
                assert atlas.pixelColor(ax + x + BOWL_REACH, ay + y) == sprites.BOWL


def test_bowl_levels_differ(qapp):
    """Jede Portion mehr sieht man am Napf."""
    from taskbar_cat.furniture import BOWL_PORTIONS
    assert sprites.BOWL_LEVELS == BOWL_PORTIONS
    img = sprites.render_furniture()
    frames = []
    for n in range(sprites.BOWL_LEVELS + 1):
        x0, y0 = sprites.furniture_origin(f"bowl_{n}")
        frames.append([img.pixel(x0 + x, y0 + y) for x in range(sprites.FRAME) for y in range(sprites.FRAME)])
    assert len({tuple(f) for f in frames}) == len(frames)
