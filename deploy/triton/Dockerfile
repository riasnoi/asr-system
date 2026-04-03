FROM nvcr.io/nvidia/tritonserver:24.08-py3

# Python backend dependencies for Whisper and ruBERT models.
# Torch cu121 matches the CUDA version in the 24.08 Triton image.
RUN pip install --no-cache-dir \
    faster-whisper \
    transformers \
    torch --index-url https://download.pytorch.org/whl/cu121
