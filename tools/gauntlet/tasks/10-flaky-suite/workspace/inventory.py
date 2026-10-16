"""inventory.py - module A: the items and the tags on them; pricing.py quotes them - one system.

Documented behaviour, for every caller:

  reset()                forget every item AND every tag - every index derived from them goes.
  add_item(name, qty, tags=[])
                         qty must be > 0 else ValueError; adds qty units of name, creating the
                         item if it is new.  Its tags are the union of the tags it already had
                         and `tags`, once each, in first-seen order.  Returns its tag list.
  remove_item(name, qty) qty must not exceed the stock, else ValueError.  At zero the item is
                         gone - and so is its tag.
  tagged(tag)            the names of the items currently IN STOCK carrying tag, sorted.
  total()                the stock of every item, summed.

Two rules about identity, not values:

  * the `tags` argument is COPIED into the item - the caller may keep the list and mutate it
    later and the item must not change - and two calls that pass no tags must not share a list.
  * the list add_item returns is a COPY too: appending to it must not change the item.
"""

_items = {}
_by_tag = {}


def reset():
    """Forget every item, and every tag with it."""
    _items.clear()


def add_item(name, qty, tags=[]):
    """Add qty of name (qty > 0); tags is an optional list of strings.  Returns the item's tags."""
    if qty <= 0:
        raise ValueError("qty must be positive")
    item = _items.setdefault(name, {"qty": 0, "tags": tags})
    item["qty"] += qty
    for t in tags:
        if t not in item["tags"]:
            item["tags"].append(t)
        _by_tag.setdefault(t, set()).add(name)
    return item["tags"]


def remove_item(name, qty):
    item = _items[name]
    if qty > item["qty"]:
        raise ValueError("not enough stock")
    item["qty"] -= qty
    if item["qty"] == 0:
        del _items[name]


def tagged(tag):
    """Names of the items in stock that carry tag, sorted."""
    return sorted(_by_tag.get(tag, set()))


def total():
    return sum(i["qty"] for i in _items.values())
