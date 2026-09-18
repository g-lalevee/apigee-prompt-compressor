"""
Prompt compression using LLMLingua.
"""
import os
import torch
from llmlingua import PromptCompressor
from cachetools import TTLCache
from hashlib import md5

# Tune PyTorch CPU thread count to prevent core contention
torch.set_num_threads(int(os.getenv("TORCH_NUM_THREADS", "2")))

# Initialize compressor (lazy loaded or lifespan preloaded)
_compressor = None

# Initialize cache: 5000 items, 1 hour TTL (<20MB RAM)
cache = TTLCache(maxsize=5000, ttl=3600)

MODEL_NAME = os.getenv("MODEL_NAME", "microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank")


def get_compressor() -> PromptCompressor:
    """Get or initialize the prompt compressor."""
    global _compressor
    if _compressor is None:
        _compressor = PromptCompressor(
            model_name=MODEL_NAME,
            use_llmlingua2=True,
            device_map="cpu"
        )
    return _compressor


def get_cache_key(prompt: str, ratio: float) -> str:
    """Generate a stable cache key."""
    return md5(f"{prompt}_{ratio}".encode()).hexdigest()


def compress_prompt(prompt: str, ratio: float) -> str:
    """
    Compress a prompt using LLMLingua with CPU inference optimization.
    
    Args:
        prompt: The prompt text to compress
        ratio: Compression ratio (0.0 to 1.0)
               
    Returns:
        str: The compressed prompt
    """
    compressor = get_compressor()
    
    with torch.inference_mode():
        result = compressor.compress_prompt(
            prompt,
            rate=ratio,
            force_tokens=["\n", ".", "!", "?"],
            chunk_end_tokens=["\n", ".", "!", "?"],
        )
    
    return result["compressed_prompt"]
