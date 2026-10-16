"""A tiny inventory service (the module our flaky CI suite tests)."""

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
