FROM nvcr.io/nvidia/tritonserver:24.08-py3

# Python backend dependencies for Whisper and ruBERT models.
# faster-whisper and transformers come from PyPI; torch is pulled from the
# PyTorch CUDA index as an extra source so PyPI remains the primary index.
RUN pip install --no-cache-dir faster-whisper transformers && \
    pip install --no-cache-dir torch \
        --extra-index-url https://download.pytorch.org/whl/cu121
