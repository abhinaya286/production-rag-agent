import hashlib
import time
from typing import Any


class ResponseCache:
    def __init__(self, expiration: int = 300, max_entries: int = 1000):
        if expiration <= 0 or max_entries <= 0:
            raise ValueError("expiration and max_entries must be positive.")
        self.expiration = expiration
        self.max_entries = max_entries
        self.cache = {}

    def _generate_key(self, prompt: str) -> str:
        return hashlib.sha256(prompt.encode()).hexdigest()

    def get(self, prompt: str) -> Any | None:
        key = self._generate_key(prompt)
        entry = self.cache.get(key)
        if entry and (time.time() - entry["timestamp"] < self.expiration):
            return entry["response"]
        self.cache.pop(key, None)
        return None

    def set(self, prompt: str, response: Any) -> None:
        key = self._generate_key(prompt)
        self.cache.pop(key, None)
        expired = [
            item_key
            for item_key, entry in self.cache.items()
            if time.time() - entry["timestamp"] >= self.expiration
        ]
        for item_key in expired:
            self.cache.pop(item_key, None)
        while len(self.cache) >= self.max_entries:
            self.cache.pop(next(iter(self.cache)))
        self.cache[key] = {
            "response": response,
            "timestamp": time.time()
        }

    def stats(self) -> dict:
        """Return cache statistics."""
        total_entries = len(self.cache)
        valid_entries = sum(
            1 for entry in self.cache.values()
            if time.time() - entry["timestamp"] < self.expiration
        )
        hit_rate = valid_entries / total_entries if total_entries > 0 else 0
        misses = total_entries - valid_entries
        return {
            "total_entries": total_entries,
            "valid_entries": valid_entries,
            "hit_rate": hit_rate,
            "misses": misses,
        }

    def get_stats(self) -> dict:
        """Return cache statistics (alias for compatibility)."""
        return self.stats()
