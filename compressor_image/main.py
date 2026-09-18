"""
Main FastAPI application for prompt compression gateway.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .models import CompressionRequest, CompressionResponse
from .policies import enforce_token_limit, PolicyViolation, tokenizer
from .compressor import compress_prompt, get_compressor, get_cache_key, cache

logger = logging.getLogger("prompt-compression-gateway")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-load model weights during container startup."""
    print("Pre-loading prompt compressor...")
    get_compressor()
    print("Prompt compressor loaded successfully.")
    yield


app = FastAPI(
    title="Prompt Compression Gateway",
    description="Enforce policies and compress LLM prompts",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Prompt Compression Gateway",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring and Cloud Run probes."""
    return {
        "status": "healthy",
        "service": "prompt-compression-gateway"
    }


@app.post("/compress", response_model=CompressionResponse)
def compress(req: CompressionRequest):
    """
    Compress a prompt with policy enforcement.
    Executed synchronously so FastAPI dispatches to an AnyIO worker threadpool,
    preventing event loop blocking during CPU-bound PyTorch inference.
    
    Args:
        req: Compression request with prompt and parameters
        
    Returns:
        CompressionResponse with token counts and compressed prompt
        
    Raises:
        HTTPException: If policy violation occurs or inference fails
    """
    try:
        # 1. Hot-path cache check: bypasses tokenization and PyTorch inference on cache hit
        cache_key = get_cache_key(req.prompt, req.compression_ratio)
        cached_res = cache.get(cache_key)
        if cached_res is not None:
            if cached_res["original_tokens"] > req.max_tokens:
                raise HTTPException(
                    status_code=400,
                    detail=f"Prompt exceeds token limit: {cached_res['original_tokens']} > {req.max_tokens}"
                )
            return CompressionResponse(**cached_res)

        # 2. Enforce token limit policy on cache miss
        original_tokens = enforce_token_limit(
            req.prompt,
            req.max_tokens
        )

        # 3. Compress the prompt
        compressed = compress_prompt(
            req.prompt,
            req.compression_ratio
        )

        # 4. Count compressed tokens using fast ordinary encoding
        compressed_tokens = len(tokenizer.encode_ordinary(compressed))

        response_data = {
            "original_tokens": original_tokens,
            "compressed_tokens": compressed_tokens,
            "compressed_prompt": compressed
        }

        # 5. Store full response in cache
        cache[cache_key] = response_data

        return CompressionResponse(**response_data)

    except PolicyViolation as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Compression error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Compression failed: {str(e)}")
