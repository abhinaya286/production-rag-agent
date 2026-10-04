from production_api.cache import ResponseCache

class TestCache:
    def setup_method(self):
        self.cache = ResponseCache()

    def test_cache_set_and_get(self):
        prompt = "Hello, how are you?"
        response = "I'm fine, thank you!"
        self.cache.set(prompt, response)
        cached_response = self.cache.get(prompt)
        assert cached_response == response

    def test_cache_expiration(self):
        prompt = "Hello, how are you?"
        response = "I'm fine, thank you!"
        self.cache.set(prompt, response)
        # Simulate expiration by manually adjusting the timestamp
        self.cache.cache[self.cache._generate_key(prompt)]["timestamp"] -= (self.cache.expiration + 1)
        cached_response = self.cache.get(prompt)
        assert cached_response is None
