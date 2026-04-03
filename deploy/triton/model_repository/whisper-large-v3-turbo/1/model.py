"""Triton Python backend for Whisper ASR using faster-whisper."""

import base64
import json
import logging
import tempfile

import numpy as np
import triton_python_backend_utils as pb_utils
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


class TritonPythonModel:
    def initialize(self, args):
        model_config = json.loads(args["model_config"])
        self.model_name = model_config.get("parameters", {}).get(
            "model_name", {"string_value": "large-v3-turbo"}
        )
        if isinstance(self.model_name, dict):
            self.model_name = self.model_name.get("string_value", "large-v3-turbo")

        device = "cuda" if args.get("model_instance_kind") == "GPU" else "cpu"
        compute_type = "float16" if device == "cuda" else "int8"

        logger.info("Loading faster-whisper model=%s device=%s", self.model_name, device)
        self.model = WhisperModel(self.model_name, device=device, compute_type=compute_type)
        logger.info("Whisper model loaded successfully")

    def execute(self, requests):
        responses = []
        for request in requests:
            audio_b64 = pb_utils.get_input_tensor_by_name(request, "AUDIO_DATA")
            audio_bytes = base64.b64decode(audio_b64.as_numpy()[0].decode("utf-8"))

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as f:
                f.write(audio_bytes)
                f.flush()
                segments_iter, _ = self.model.transcribe(f.name, language="ru")
                segments = [[s.start, s.end, s.text.strip()] for s in segments_iter]

            output_tensor = pb_utils.Tensor(
                "SEGMENTS", np.array([json.dumps(segments, ensure_ascii=False)], dtype=object)
            )
            responses.append(pb_utils.InferenceResponse(output_tensors=[output_tensor]))
        return responses

    def finalize(self):
        logger.info("Whisper model unloaded")
