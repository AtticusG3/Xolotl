"""TTLCache (reference)."""
import threading
import time
from collections import OrderedDict

_MISSING = object()


class TTLCache:
    def __init__(self, capacity, ttl, clock=time.monotonic):
        if capacity < 1 or ttl <= 0:
            raise ValueError("capacity >= 1 and ttl > 0")
        self.capacity, self.ttl, self.clock = capacity, ttl, clock
        self._d = OrderedDict()          # key -> (value, expiry), LRU first
        self._lock = threading.RLock()

    def _purge(self, now):
        for k in [k for k, (_, e) in self._d.items() if now >= e]:
            del self._d[k]

    def put(self, key, value):
        with self._lock:
            now = self.clock()
            self._d[key] = (value, now + self.ttl)
            self._d.move_to_end(key)
            if len(self._d) > self.capacity:
                self._purge(now)
                while len(self._d) > self.capacity:
                    self._d.popitem(last=False)

    def _live(self, key, now):
        item = self._d.get(key, _MISSING)
        if item is _MISSING:
            return _MISSING
        if now >= item[1]:
            del self._d[key]
            return _MISSING
        return item[0]

    def get(self, key, default=None):
        with self._lock:
            v = self._live(key, self.clock())
            if v is _MISSING:
                return default
            self._d.move_to_end(key)
            return v

    def pop(self, key, default=None):
        with self._lock:
            v = self._live(key, self.clock())
            if v is _MISSING:
                return default
            del self._d[key]
            return v

    def __len__(self):
        with self._lock:
            self._purge(self.clock())
            return len(self._d)

    def __contains__(self, key):
        with self._lock:
            return self._live(key, self.clock()) is not _MISSING

    def keys(self):
        with self._lock:
            self._purge(self.clock())
            return list(self._d)
