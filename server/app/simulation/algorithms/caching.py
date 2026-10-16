
from collections import OrderedDict


class LRUCache:
    def __init__(self, capacity: int = 1000):
        if capacity < 1:
            raise ValueError("Cache capacity must be positive")

        self.capacity = capacity
        self.items: OrderedDict[str, float] = OrderedDict()

        self.hits = 0
        self.misses = 0

    def access(
        self,
        key: str,
        now: float,
        ttl_seconds: float = 60.0,
    ) -> bool:
        if ttl_seconds <= 0:
            raise ValueError("TTL must be positive")

        expiry = self.items.get(key)

        if expiry is not None and expiry > now:
            self.items.move_to_end(key)
            self.hits += 1
            return True

        self.misses += 1
        self.items.pop(key, None)

        if len(self.items) >= self.capacity:
            self.items.popitem(last=False)

        self.items[key] = now + ttl_seconds
        return False

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0
