import random
import threading

from ttlcache import TTLCache


class Clock:
    def __init__(self):
        self.t = 0.0
        self.lock = threading.Lock()

    def __call__(self):
        with self.lock:
            return self.t


def test_expired_purged_before_live_eviction():
    clk = Clock()
    c = TTLCache(2, 10, clk)
    c.put("x", 1)                    # expires at 10
    clk.t = 5
    c.put("y", 2)                    # expires at 15
    clk.t = 6
    assert c.get("x") == 1           # x is now the MOST recently used, y the least
    clk.t = 10.5                     # x has expired, y is live
    c.put("z", 3)                    # 3 entries > 2: purge expired x first -> no live entry is evicted
    assert c.get("y") == 2 and c.get("z") == 3 and len(c) == 2


def test_get_refreshes_recency_not_expiry():
    clk = Clock()
    c = TTLCache(2, 10, clk)
    c.put("a", 1)
    clk.t = 5
    c.put("b", 2)
    clk.t = 9
    assert c.get("a") == 1           # a is now most recent...
    c.put("c", 3)                    # ...so b is evicted
    assert "b" not in c and "a" in c
    clk.t = 10
    assert c.get("a") is None        # ...but a still expires at 10


def test_contains_keeps_recency_and_keys_order():
    clk = Clock()
    c = TTLCache(2, 100, clk)
    c.put("a", 1)
    c.put("b", 2)
    assert "a" in c                  # no recency change
    c.put("c", 3)                    # evicts a
    assert c.keys() == ["b", "c"]


def test_overwrite_resets_expiry_and_recency():
    clk = Clock()
    c = TTLCache(2, 10, clk)
    c.put("a", 1)
    c.put("b", 2)
    clk.t = 8
    c.put("a", 9)                    # expiry -> 18, a most recent
    c.put("c", 3)                    # evicts b
    clk.t = 15
    assert c.get("a") == 9 and "b" not in c


def test_pop_and_len():
    clk = Clock()
    c = TTLCache(5, 10, clk)
    for i in range(5):
        c.put(i, i)
    assert c.pop(2) == 2 and c.pop(2, "x") == "x" and len(c) == 4
    clk.t = 10
    assert len(c) == 0 and c.pop(0) is None


def test_threads_invariants():
    clk = Clock()
    c = TTLCache(50, 5, clk)
    errors = []

    def worker(seed):
        r = random.Random(seed)
        try:
            for _ in range(3000):
                k = r.randint(0, 120)
                op = r.random()
                if op < 0.45:
                    c.put(k, (k, seed))
                elif op < 0.85:
                    v = c.get(k)
                    if v is not None and v[0] != k:
                        errors.append(("wrong value", k, v))
                elif op < 0.95:
                    c.pop(k)
                else:
                    if len(c) > 50:
                        errors.append(("over capacity", len(c)))
                if r.random() < 0.01:
                    with clk.lock:
                        clk.t += 0.5
        except Exception as e:      # noqa: BLE001
            errors.append(repr(e))

    ts = [threading.Thread(target=worker, args=(s,)) for s in range(8)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(60)
    assert not any(t.is_alive() for t in ts), "deadlock"
    assert not errors, errors[:3]
    assert len(c) <= 50 and len(c.keys()) == len(c)
