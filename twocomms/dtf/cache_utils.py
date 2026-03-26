from django.core.cache import cache, caches


PUBLISHED_POSTS_CACHE_KEY = "dtf:published_posts:v1"
ACTIVE_WORKS_CACHE_KEY = "dtf:active_works:v1"


def get_fragment_cache_backend():
    try:
        return caches["fragments"]
    except Exception:
        return cache


def invalidate_dtf_cache_keys(*cache_keys: str) -> None:
    cache_backend = get_fragment_cache_backend()
    for cache_key in cache_keys:
        if cache_key:
            cache_backend.delete(cache_key)
