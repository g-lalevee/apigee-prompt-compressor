"""
Prompt compression using LLMLingua.
"""
from llmlingua import PromptCompressor
from cachetools import TTLCache, cached
from hashlib import md5

# Initialize compressor (lazy loaded)
_compressor = None

# Initialize cache: 100 items, 1 hour TTL
cache = TTLCache(maxsize=100, ttl=3600)

def get_compressor() -> PromptCompressor:
    """Get or initialize the prompt compressor."""
    global _compressor
    if _compressor is None:
        _compressor = PromptCompressor(
            model_name="microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank",
            use_llmlingua2=True,
            device_map="cpu"
        )
    return _compressor


def get_cache_key(prompt: str, ratio: float) -> str:
    """Generate a stable cache key."""
    return md5(f"{prompt}_{ratio}".encode()).hexdigest()


def compress_prompt(prompt: str, ratio: float) -> str:
    """
    Compress a prompt using LLMLingua with in-memory caching.
    
    Args:
        prompt: The prompt text to compress
        ratio: Compression ratio (0.0 to 1.0)
               
    Returns:
        str: The compressed prompt
    """
    key = get_cache_key(prompt, ratio)
    
    # Check cache manually to avoid @cached decorator complexity with global compressor
    if key in cache:
        print("Cache hit! Returning cached compression.")
        return cache[key]

    compressor = get_compressor()
    
    result = compressor.compress_prompt(
        prompt,
        rate=ratio,
        force_tokens=["\n", ".", "!", "?"],
        chunk_end_tokens=["\n", ".", "!", "?"],
    )
    
    compressed_text = result["compressed_prompt"]
    cache[key] = compressed_text
    
    return compressed_text
