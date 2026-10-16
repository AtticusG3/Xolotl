"""CI runs these in a random order (pytest-randomly) and fails about one run in three;
locally - file order - they all pass.  The service is used by other code too.
"""
import inventory as inv


def test_add_and_total():
    inv.reset()
    inv.add_item("apple", 3)
    inv.add_item("pear", 2, ["fruit"])
    assert inv.total() == 5


def test_empty_tags_are_not_shared_between_items():
    inv.reset()
    inv.add_item("nut", 1)
    assert inv.add_item("nut", 1) == []
    assert inv.tagged("metal") == []


def test_tagged_finds_stock():
    inv.reset()
    inv.add_item("kiwi", 1, ["produce"])
    assert inv.tagged("produce") == ["kiwi"]


def test_remove():
    inv.reset()
    inv.add_item("bolt", 4)
    inv.remove_item("bolt", 4)
    assert inv.total() == 0


def test_appending_to_the_returned_list_does_not_tag_the_item():
    inv.reset()
    a = inv.add_item("screw", 1)
    a.append("metal")
    assert inv.tagged("metal") == []
