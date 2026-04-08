"""Triton Python backend for ruBERT emotion classification."""

import json
import logging

import numpy as np
import triton_python_backend_utils as pb_utils
from transformers import pipeline

logger = logging.getLogger(__name__)

# cointegrated/rubert-tiny2-cedr-emotion-detection labels → our domain labels
_CEDR_LABEL_MAP = {
    "no_emotion": "neutral",
    "joy": "positive",
    "sadness": "sad",
    "anger": "angry",
    "fear": "sad",  # closest negative without dedicated category
    "surprise": "neutral",
}


class TritonPythonModel:
    def initialize(self, args):
        model_config = json.loads(args["model_config"])
        self.model_name = model_config.get("parameters", {}).get(
            "model_name", {"string_value": "cointegrated/rubert-tiny2-cedr-emotion-detection"}
        )
        if isinstance(self.model_name, dict):
            self.model_name = self.model_name.get(
                "string_value", "cointegrated/rubert-tiny2-cedr-emotion-detection"
            )

        device = 0 if args.get("model_instance_kind") == "GPU" else -1
        logger.info("Loading emotion model=%s device=%s", self.model_name, device)
        self.pipe = pipeline(
            "text-classification",
            model=self.model_name,
            device=device,
            top_k=None,
        )
        logger.info("Emotion model loaded successfully")

    def execute(self, requests):
        responses = []
        for request in requests:
            text_tensor = pb_utils.get_input_tensor_by_name(request, "TEXT")
            text = text_tensor.as_numpy()[0].decode("utf-8")

            results = self.pipe(text)[0]
            best = max(results, key=lambda r: r["score"])

            raw_label = best["label"].lower()
            label = _CEDR_LABEL_MAP.get(raw_label, "neutral")
            logger.debug("emotion raw=%s mapped=%s score=%.3f", raw_label, label, best["score"])

            emotion_out = pb_utils.Tensor("EMOTION", np.array([label], dtype=object))
            confidence_out = pb_utils.Tensor(
                "CONFIDENCE", np.array([best["score"]], dtype=np.float32)
            )
            responses.append(
                pb_utils.InferenceResponse(output_tensors=[emotion_out, confidence_out])
            )
        return responses

    def finalize(self):
        logger.info("Emotion model unloaded")
