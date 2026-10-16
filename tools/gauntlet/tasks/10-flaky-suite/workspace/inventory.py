"""A tiny inventory service (the module our flaky CI suite tests).

Documented behaviour - every function, for every caller:

  reset()                forget every item AND every tag (tests call this first)
  add_item(name, qty, tags=[])   qty must be > 0, else ValueError.  Adds qty units of name (creating the
                         item if new).  The item's tags are the union of the tags it already had and
                         `tags`, each tag listed once.  Returns the item's tag list.
  remove_item(name, qty) qty must not exceed the stock, else ValueError.  When the stock reaches 0 the
                         item is gone - and so is its tag.
  tagged(tag)            names of the items currently IN STOCK that carry tag, sorted.
  total()                the sum of the stock of every item.

Two rules that are easy to get wrong, because they are about identity, not values:

  * the `tags` argument is COPIED into the item: the caller may keep the list and mutate it afterwards
    and the item must not change.  Two calls that pass no tags at all must not end up sharing one list.
  * the list add_item returns is a COPY too: appending to it must not change the item or its tags.
"""

_items = {}
_by_tag = {}


def reset():
    """Forget every item (tests call this first)."""
    _items.clear()


def add_item(name, qty, tags=[]):
    """Add qty of name (qty > 0); tags is an optional list of strings.  Returns the item's tag list."""
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
