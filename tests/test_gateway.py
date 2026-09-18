"""
Unit tests for Prompt Compression Gateway using standard library unittest.
"""
import unittest
from unittest.mock import MagicMock, patch

from compressor_image.models import CompressionRequest, CompressionResponse
from compressor_image.policies import enforce_token_limit, enforce_compression_ratio, PolicyViolation, tokenizer
from compressor_image.compressor import get_cache_key, cache


class TestModels(unittest.TestCase):
    """Test Pydantic request/response models."""

    def test_valid_compression_request(self):
        req = CompressionRequest(
            prompt="Hello world, please compress this sentence.",
            max_tokens=100,
            compression_ratio=0.5
        )
        self.assertEqual(req.prompt, "Hello world, please compress this sentence.")
        self.assertEqual(req.max_tokens, 100)
        self.assertEqual(req.compression_ratio, 0.5)

    def test_empty_prompt_rejected(self):
        with self.assertRaises(ValueError):
            CompressionRequest(prompt="   ", max_tokens=100)

    def test_compression_ratio_bounds(self):
        with self.assertRaises(ValueError):
            CompressionRequest(prompt="Test", compression_ratio=0.1)  # Below 0.2
        with self.assertRaises(ValueError):
            CompressionRequest(prompt="Test", compression_ratio=0.95)  # Above 0.9

    def test_compression_response_ratio_calculation(self):
        resp = CompressionResponse(
            original_tokens=100,
            compressed_tokens=40,
            compressed_prompt="Compressed"
        )
        self.assertEqual(resp.compression_ratio_achieved, 0.40)

    def test_compression_response_zero_division_guard(self):
        resp = CompressionResponse(
            original_tokens=0,
            compressed_tokens=0,
            compressed_prompt=""
        )
        self.assertEqual(resp.compression_ratio_achieved, 0.0)


class TestPolicies(unittest.TestCase):
    """Test policy enforcement logic."""

    def test_enforce_token_limit_within_bounds(self):
        prompt = "This is a short test prompt."
        count = enforce_token_limit(prompt, max_tokens=50)
        self.assertGreater(count, 0)
        self.assertLessEqual(count, 50)

    def test_enforce_token_limit_exceeded(self):
        prompt = "This prompt is specifically crafted to exceed a very low limit."
        with self.assertRaises(PolicyViolation) as ctx:
            enforce_token_limit(prompt, max_tokens=2)
        self.assertIn("Prompt exceeds token limit", str(ctx.exception))

    def test_enforce_compression_ratio_success(self):
        orig, comp = enforce_compression_ratio(
            "This is a longer prompt that will be tested for compression ratio.",
            "This is shorter.",
            target_ratio=0.6
        )
        self.assertLessEqual(comp, orig)

    def test_enforce_compression_ratio_failure(self):
        with self.assertRaises(PolicyViolation):
            enforce_compression_ratio(
                "Short prompt",
                "Short prompt with even more text added to completely fail compression ratio",
                target_ratio=0.3
            )


class TestCaching(unittest.TestCase):
    """Test hot-path caching mechanisms."""

    def test_get_cache_key_deterministic(self):
        k1 = get_cache_key("Sample prompt text", 0.5)
        k2 = get_cache_key("Sample prompt text", 0.5)
        k3 = get_cache_key("Sample prompt text", 0.6)
        self.assertEqual(k1, k2)
        self.assertNotEqual(k1, k3)

    def test_cache_storage_and_retrieval(self):
        key = get_cache_key("Test cache storage", 0.5)
        payload = {
            "original_tokens": 10,
            "compressed_tokens": 5,
            "compressed_prompt": "Test storage"
        }
        cache[key] = payload
        self.assertIn(key, cache)
        self.assertEqual(cache[key]["compressed_tokens"], 5)


if __name__ == "__main__":
    unittest.main()

