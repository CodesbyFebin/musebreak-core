"""Challenge store: Redis (SET EX + GETDEL, atomic single-use) or in-memory TTL fallback."""
import threading
import time


class MemoryStore:
    def __init__(self):
        self._d, self._lock, self._counters = {}, threading.Lock(), {}

    def set(self, key: str, value: str, ttl: int):
        with self._lock:
            self._d[key] = (value, time.monotonic() + ttl)

    def bump_counter(self, key_id: str, counter: int) -> bool:
        """Atomically accept counter only if strictly greater than the last accepted one."""
        with self._lock:
            last = self._counters.get(key_id, -1)
            if counter <= last:
                return False
            self._counters[key_id] = counter
            return True

    def getdel(self, key: str):
        with self._lock:
            item = self._d.pop(key, None)
        if not item or item[1] < time.monotonic():
            return None
        return item[0]


class RedisStore:
    def __init__(self, url: str):
        import redis
        self.r = redis.Redis.from_url(url, decode_responses=True)
        self.r.ping()

    def set(self, key, value, ttl):
        self.r.set(key, value, ex=ttl)

    _CAS = """
    local last = tonumber(redis.call('GET', KEYS[1]) or '-1')
    if tonumber(ARGV[1]) > last then redis.call('SET', KEYS[1], ARGV[1]) return 1 end
    return 0"""

    def bump_counter(self, key_id, counter):
        return self.r.eval(self._CAS, 1, f"ctr:{key_id}", int(counter)) == 1  # atomic Lua CAS

    def getdel(self, key):
        return self.r.getdel(key)  # atomic: Redis >= 6.2


def make_store(url):
    return RedisStore(url) if url else MemoryStore()
