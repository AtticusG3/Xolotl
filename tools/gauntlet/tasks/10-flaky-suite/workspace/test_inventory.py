"""CI runs these in a random order (pytest-randomly) and fails about one run in three; locally (file order) they pass."""
import inventory as inv


def test_add_and_total():
    inv.reset()
    inv.add_item("apple", 3)
    inv.add_item("pear", 2, ["fruit"])
    assert inv.total() == 5


def test_tags_are_per_item():
    inv.reset()
    a = inv.add_item("bolt", 10)
    b = inv.add_item("nut", 5)
    a.append("metal")
    assert inv.add_item("nut", 1) == []


def test_tagged_only_lists_stock():
    inv.reset()
    inv.add_item("kiwi", 1, ["fruit"])
    inv.remove_item("kiwi", 1)
    assert inv.tagged("fruit") == []


def test_remove():
    inv.reset()
    inv.add_item("bolt", 4)
    inv.remove_item("bolt", 4)
    assert inv.total() == 0
