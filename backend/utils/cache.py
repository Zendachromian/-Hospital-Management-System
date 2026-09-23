import redis
import json
from functools import wraps
import os

# Use environment variable or default URL
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

def cache_get(key):
    try:
        data = redis_client.get(key)
        if data:
            return json.loads(data)
        return None
    except Exception as e:
        print(f"Cache get error: {e}")
        return None

def cache_set(key, value, expiry=300):
    try:
        redis_client.setex(key, expiry, json.dumps(value))
        return True
    except Exception as e:
        print(f"Cache set error: {e}")
        return False

def cache_delete(key):
    try:
        redis_client.delete(key)
        return True
    except Exception as e:
        print(f"Cache delete error: {e}")
        return False

def cache_clear_pattern(pattern):
    try:
        keys = redis_client.keys(pattern)
        if keys:
            redis_client.delete(*keys)
        return True
    except Exception as e:
        print(f"Cache clear pattern error: {e}")
        return False

def cached(key_prefix, expiry=300):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{key_prefix}:{':'.join(map(str, args))}"
            
            cached_data = cache_get(cache_key)
            if cached_data is not None:
                return cached_data
            
            result = func(*args, **kwargs)
            cache_set(cache_key, result, expiry)
            return result
        return wrapper
    return decorator