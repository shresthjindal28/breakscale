from app.simulation.algorithms.caching import LRUCache


def test_cache_miss_then_hit():
    cache = LRUCache(capacity=2)
    assert cache.access("user:1", now=0) is False
    assert cache.access("user:1", now=1) is True
    assert cache.hit_rate == 0.5


def test_cache_expiration():
    cache = LRUCache(capacity=2)
    cache.access("key", now=0, ttl_seconds=2)
    assert cache.access("key", now=3) is False


def test_cache_evicts_least_recently_used():
    cache = LRUCache(capacity=2)
    cache.access("a", now=0)
    cache.access("b", now=0)
    assert cache.access("a", now=1) is True
    cache.access("c", now=1)
    assert cache.access("b", now=1) is False
