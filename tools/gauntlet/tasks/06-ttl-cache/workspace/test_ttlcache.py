from ttlcache import TTLCache


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_basic():
    clk = Clock()
    c = TTLCache(2, 10, clk)
    c.put("a", 1)
    c.put("b", 2)
    assert c.get("a") == 1
    c.put("c", 3)                  # evicts b (least recently used)
    assert c.get("b") is None and c.get("c") == 3
    clk.t = 10
    assert c.get("a") is None      # expired exactly at ttl
