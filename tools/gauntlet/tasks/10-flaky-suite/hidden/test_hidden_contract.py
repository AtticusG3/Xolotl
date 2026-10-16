"""Hidden grading for 10-flaky-suite.

The visible suite is re-stated here - never imported from the workspace, so a model cannot
weaken grading by editing a test - and run in 20 random orders (the CI order), and then the
whole documented contract of both modules is checked directly: the tag-list identity rules, the
tag index across reset and removal, the price memo across a price change and across inventory
changing underneath it, and the price-table ordering.
"""
import random
from decimal import Decimal

import pytest

import inventory as inv
import pricing as pr


# --- the visible suite, re-stated, run in 20 random orders ----------------------------------------
def _add_and_total():
    inv.reset()
    inv.add_item("apple", 3)
    inv.add_item("pear", 2, ["fruit"])
    assert inv.total() == 5


def _tagged_finds_the_tagged_stock():
    inv.reset()
    inv.add_item("kiwi", 1, ["produce"])
    assert inv.tagged("produce") == ["kiwi"]


def _partial_removal_leaves_the_rest():
    inv.reset()
    inv.add_item("bolt", 4, ["hardware"])
    inv.remove_item("bolt", 1)
    assert (inv.total(), inv.add_item("bolt", 1, ["hardware"])) == (3, ["hardware"])


def _tags_are_merged_in_first_seen_order():
    inv.reset()
    inv.add_item("nut", 1, ["bulk", "fragile"])
    assert inv.add_item("nut", 1, ["fragile", "bulk"]) == ["bulk", "fragile"]


def _qty_must_be_positive():
    inv.reset()
    with pytest.raises(ValueError):
        inv.add_item("widget", 0)


def _price_and_quote():
    inv.reset()
    pr.reset()
    inv.add_item("grommet", 10)
    pr.set_price("grommet", "2.00")
    assert (pr.price_of("grommet"), pr.quote("grommet", 5)) == (Decimal("2.00"), Decimal("10.00"))


def _clearance_halves_the_unit_price():
    inv.reset()
    pr.reset()
    inv.add_item("screw", 2, ["clearance"])
    pr.set_price("screw", "3.00")
    assert pr.quote("screw", 1) == Decimal("1.50")


VISIBLE = [_add_and_total, _tagged_finds_the_tagged_stock, _partial_removal_leaves_the_rest,
           _tags_are_merged_in_first_seen_order, _qty_must_be_positive, _price_and_quote,
           _clearance_halves_the_unit_price]


@pytest.mark.parametrize("seed", range(20))
def test_visible_suite_in_random_order(seed):
    fns = VISIBLE[:]
    random.Random(seed).shuffle(fns)
    for f in fns:
        f()


# --- fault 1: the tags argument and the returned list are copies, and no two items share one -----
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


def test_no_two_untagged_items_share_one_list():
    inv.reset()
    a = inv.add_item("bolt", 10)
    b = inv.add_item("nut", 5)
    a.append("metal")
    assert b == []
    assert inv.tagged("metal") == []


def test_two_items_with_tags_do_not_share_them():
    inv.reset()
    first, second = ["a"], ["b"]
    inv.add_item("bolt", 1, first)
    inv.add_item("nut", 1, second)
    first.append("z")
    assert inv.tagged("z") == []
    assert inv.tagged("b") == ["nut"]


# --- fault 2: the tag index is maintained on reset and on removal ---------------------------------
def test_reset_forgets_every_tag():
    inv.reset()
    inv.add_item("kiwi", 1, ["fruit"])
    inv.reset()
    assert inv.tagged("fruit") == []
    assert inv.total() == 0


def test_removing_the_last_unit_drops_the_tag():
    inv.reset()
    inv.add_item("kiwi", 1, ["fruit"])
    inv.remove_item("kiwi", 1)
    assert inv.tagged("fruit") == []


def test_partial_removal_keeps_the_tag():
    inv.reset()
    inv.add_item("kiwi", 3, ["fruit"])
    inv.remove_item("kiwi", 2)
    assert inv.tagged("fruit") == ["kiwi"]


def test_readding_after_removal_is_tagged_again():
    inv.reset()
    inv.add_item("kiwi", 1, ["fruit"])
    inv.remove_item("kiwi", 1)
    inv.add_item("kiwi", 2, ["fruit"])
    assert inv.tagged("fruit") == ["kiwi"]


# --- fault 3: the price memo never outlives the state the quote is about --------------------------
def test_quote_needs_a_price():
    inv.reset()
    pr.reset()
    inv.add_item("cap", 1)
    with pytest.raises(ValueError):
        pr.quote("cap", 1)


def test_quote_follows_a_price_change():
    inv.reset()
    pr.reset()
    pr.set_price("bolt", "2.00")
    assert pr.quote("bolt", 4) == Decimal("8.00")
    pr.set_price("bolt", "2.50")
    assert pr.quote("bolt", 4) == Decimal("10.00")


def test_quote_follows_the_price_back_down():
    inv.reset()
    pr.reset()
    pr.set_price("nut", "1.00")
    assert pr.quote("nut", 2) == Decimal("2.00")
    pr.set_price("nut", "4.00")
    assert pr.quote("nut", 2) == Decimal("8.00")
    pr.set_price("nut", "1.00")
    assert pr.quote("nut", 2) == Decimal("2.00")


def test_quote_follows_inventory_tagging_an_item_for_clearance():
    inv.reset()
    pr.reset()
    inv.add_item("bolt", 5)
    pr.set_price("bolt", "2.00")
    assert pr.quote("bolt", 3) == Decimal("6.00")
    inv.add_item("bolt", 1, ["clearance"])
    assert pr.quote("bolt", 3) == Decimal("3.00")


def test_quote_follows_inventory_removing_the_item():
    inv.reset()
    pr.reset()
    inv.add_item("kiwi", 2, ["clearance"])
    pr.set_price("kiwi", "3.00")
    assert pr.quote("kiwi", 1) == Decimal("1.50")
    inv.remove_item("kiwi", 2)
    assert pr.quote("kiwi", 1) == Decimal("3.00")


# --- fault 4: the price table is ordered by value, ties in recording order ------------------------
def test_price_table_is_smallest_first():
    pr.reset()
    pr.set_price("washer", "2.00")
    pr.set_price("spanner", "1.50")
    assert pr.price_table() == ["spanner 1.50", "washer 2.00"]


def test_price_table_orders_by_value_not_by_text():
    pr.reset()
    pr.set_price("bolt", "2.00")
    pr.set_price("kiwi", "10.00")
    pr.set_price("nut", "9.00")
    assert pr.price_table() == ["bolt 2.00", "nut 9.00", "kiwi 10.00"]


def test_price_table_keeps_equal_prices_in_recording_order():
    pr.reset()
    pr.set_price("zzz", "2.00")
    pr.set_price("aaa", "2.00")
    pr.set_price("mmm", "1.50")
    assert pr.price_table() == ["mmm 1.50", "zzz 2.00", "aaa 2.00"]
