import threading

from app.core.cache.ttl_cache import TTLCache


def test_ttl_cache_is_bounded() -> None:
    cache = TTLCache(max_items=2)
    cache.set("one", 1, 60)
    cache.set("two", 2, 60)
    cache.set("three", 3, 60)

    assert len(cache._items) == 2
    assert cache.get("three") == 3


def test_ttl_cache_supports_concurrent_access() -> None:
    cache = TTLCache(max_items=64)

    def write(index: int) -> None:
        cache.set(f"key-{index}", index, 60)
        assert cache.get(f"key-{index}") == index

    threads = [threading.Thread(target=write, args=(index,)) for index in range(32)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(cache._items) <= 64
