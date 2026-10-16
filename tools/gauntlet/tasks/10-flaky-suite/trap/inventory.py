"""THE TRAP: makes the visible suite green in every order (per-call default list, reset clears the tag
index, removal maintains it) but still hands out the caller's list and returns the internal one, so
mutating either still changes the item - the hidden tests catch exactly that.

(This file exists only for validate.py.)
"""

_items = {}
_by_tag = {}


def reset():
    _items.clear()
    _by_tag.clear()


def add_item(name, qty, tags=None):
    if qty <= 0:
        raise ValueError("qty must be positive")
    if tags is None:
        tags = []
    item = _items.setdefault(name, {"qty": 0, "tags": tags})   # the caller's list IS the item's list
    item["qty"] += qty
    for t in tags:
        if t not in item["tags"]:
            item["tags"].append(t)
        _by_tag.setdefault(t, set()).add(name)
    return item["tags"]                                        # and the internal list is returned


def remove_item(name, qty):
    item = _items[name]
    if qty > item["qty"]:
        raise ValueError("not enough stock")
    item["qty"] -= qty
    if item["qty"] == 0:
        del _items[name]
        for t in item["tags"]:
            _by_tag.get(t, set()).discard(name)


def tagged(tag):
    return sorted(_by_tag.get(tag, set()))


def total():
    return sum(i["qty"] for i in _items.values())
