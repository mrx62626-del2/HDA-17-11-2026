from threading import RLock
from time import monotonic

_cache = {}
_lock = RLock()

def get(key):
    with _lock:
        item = _cache.get(key)
        if not item: return None
        expires, value = item
        if monotonic() >= expires:
            _cache.pop(key, None)
            return None
        return value

def set_value(key, value, ttl=900):
    with _lock:
        _cache[key] = (monotonic() + max(1, ttl), value)

def clear():
    with _lock:
        _cache.clear()
