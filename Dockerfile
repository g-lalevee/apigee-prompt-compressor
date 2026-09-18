FROM python:3.11-slim

WORKDIR /app

# Configure performance, threading, and offline Hugging Face / Tiktoken cache
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=0 \
    HF_HOME=/app/model_cache \
    TIKTOKEN_CACHE_DIR=/app/tiktoken_cache \
    TRANSFORMERS_OFFLINE=1 \
    HF_HUB_OFFLINE=1 \
    OMP_NUM_THREADS=2 \
    MKL_NUM_THREADS=2 \
    TORCH_NUM_THREADS=2

# 1. Install CPU-only PyTorch first (avoids ~2.5GB CUDA packages)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# 2. Install application dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Pre-download BERT model weights & tiktoken encodings into container image layer
# Temporarily enable network for download during build
RUN HF_HUB_OFFLINE=0 TRANSFORMERS_OFFLINE=0 python -c "import tiktoken; tiktoken.get_encoding('cl100k_base'); from llmlingua import PromptCompressor; PromptCompressor(model_name='microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank', use_llmlingua2=True, device_map='cpu')"

# 4. Copy application source
COPY compressor_image/ ./compressor_image/

# 5. Pre-compile Python bytecode for faster cold start
RUN python -m compileall -b /app

# Expose port
EXPOSE 8000

# 6. Run with multi-worker Uvicorn using exec form for proper signal propagation
CMD exec uvicorn compressor_image.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2 --timeout-keep-alive 65
