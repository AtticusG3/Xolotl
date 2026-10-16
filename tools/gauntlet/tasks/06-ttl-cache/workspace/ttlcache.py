"""TTLCache: a thread-safe LRU cache whose entries also expire.

  TTLCache(capacity, ttl, clock=time.monotonic)
    capacity: max number of LIVE entries (>= 1); ttl: seconds an entry lives after its last put (> 0);
    clock: a zero-argument callable returning seconds (tests pass a fake clock).

  put(key, value)   store (or overwrite) value; its expiry becomes clock() + ttl and it becomes most recently used.
                    If that leaves more than `capacity` entries: first drop every EXPIRED entry, then, while still over
                    capacity, evict the least recently used live entry.
  get(key, default=None)
                    value if present and not expired (expired means clock() >= expiry), and it becomes most recently
                    used - a get does NOT extend its expiry.  A missing or expired key returns default (an expired
                    entry is removed).
  pop(key, default=None)   remove and return a live value (or default; an expired entry is removed, default returned).
  __len__()         the number of live entries (expired ones are purged first).
  __contains__(key) True if live; does NOT change recency.
  keys()            live keys, least recently used first.

All methods must be safe to call from many threads at once.  The clock may be called any number of times.
"""
import time


class TTLCache:
    def __init__(self, capacity, ttl, clock=time.monotonic):
        raise NotImplementedError
