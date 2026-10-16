"""Hidden grading for 10-flaky-suite.

The visible suite is re-stated here (never imported from the workspace: a model must not be able to
weaken grading by editing it) and run in 20 random orders - the CI flake - and then the whole
documented contract is checked directly.
"""
import random

import pytest

import inventory as inv


# --- the visible suite, re-stated, run in random orders -------------------------------------------
def _add_and_total():
    inv.reset()
    inv.add_item("apple", 3)
    inv.add_item("pear", 2, ["fruit"])
    assert inv.total() == 5


def _empty_tags_are_not_shared_between_items():
    inv.reset()
    inv.add_item("nut", 1)
    assert inv.add_item("nut", 1) == []
    assert inv.tagged("metal") == []


def _tagged_finds_stock():
    inv.reset()
    inv.add_item("kiwi", 1, ["produce"])
    assert inv.tagged("produce") == ["kiwi"]


def _remove():
    inv.reset()
    inv.add_item("bolt", 4)
    inv.remove_item("bolt", 4)
    assert inv.total() == 0


def _appending_to_the_returned_list_does_not_tag_the_item():
    inv.reset()
    a = inv.add_item("screw", 1)
    a.append("metal")
    assert inv.tagged("metal") == []


VISIBLE = [_add_and_total, _empty_tags_are_not_shared_between_items, _tagged_finds_stock, _remove,
           _appending_to_the_returned_list_does_not_tag_the_item]


@pytest.mark.parametrize("seed", range(20))
def test_visible_suite_in_random_order(seed):
    fns = VISIBLE[:]
    random.Random(seed).shuffle(fns)
    for f in fns:
        f()


# --- the documented contract ----------------------------------------------------------------------
def test_caller_tag_list_is_copied():
    inv.reset()
    tags = ["fruit"]
    inv.add_item("apple", 1, tags)
    tags.append("metal")
    assert inv.tagged("metal") == []
    assert inv.tagged("fruit") == ["apple"]


def test_returned_tag_list_is_a_copy():
    inv.reset()
    got = inv.add_item("apple", 1, ["fruit"])
    got.append("metal")
    assert inv.tagged("metal") == []
    assert inv.add_item("apple", 1) == ["fruit"]


def test_no_two_items_share_a_tag_list():
    inv.reset()
    a = inv.add_item("bolt", 10)
    b = inv.add_item("nut", 5)
    a.append("metal")
    assert b == []
    assert inv.tagged("metal") == []


def test_removing_the_last_unit_drops_the_tag():
    inv.reset()
    inv.add_item("kiwi", 1, ["fruit"])
    inv.remove_item("kiwi", 1)
    assert inv.tagged("fruit") == []
    assert inv.total() == 0


def test_partial_removal_keeps_the_tag():
    inv.reset()
    inv.add_item("kiwi", 3, ["fruit"])
    inv.remove_item("kiwi", 2)
    assert inv.tagged("fruit") == ["kiwi"]
    assert inv.total() == 1


def test_reset_clears_items_and_tags():
    inv.reset()
    inv.add_item("kiwi", 1, ["fruit"])
    inv.reset()
    assert inv.tagged("fruit") == []
    assert inv.total() == 0


def test_readd_after_removal():
    inv.reset()
    inv.add_item("kiwi", 1, ["fruit"])
    inv.remove_item("kiwi", 1)
    inv.add_item("kiwi", 2, ["fruit"])
    assert inv.tagged("fruit") == ["kiwi"]
    assert inv.total() == 2


def test_tags_merge_and_are_listed_once():
    inv.reset()
    inv.add_item("bolt", 1, ["a", "a", "b"])
    inv.add_item("bolt", 1, ["b", "c"])
    assert inv.add_item("bolt", 1) == ["a", "b", "c"]
    assert inv.tagged("a") == ["bolt"]
    assert inv.total() == 3


def test_tagged_is_sorted_and_only_in_stock():
    inv.reset()
    for n in ("c", "a", "b"):
        inv.add_item(n, 1, ["z"])
    inv.remove_item("b", 1)
    assert inv.tagged("z") == ["a", "c"]


def test_qty_must_be_positive():
    inv.reset()
    with pytest.raises(ValueError):
        inv.add_item("x", 0)
    with pytest.raises(ValueError):
        inv.add_item("x", -1)
