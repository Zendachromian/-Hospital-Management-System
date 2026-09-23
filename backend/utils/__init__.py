# backend/utils/__init__.py

# Only import cache functions - remove everything else
from .cache import cache_get, cache_set, cache_delete, cache_clear_pattern, cached

# That's it! No Flask app code here