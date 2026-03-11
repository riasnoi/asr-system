from asr_system.domain.ports import EmotionPort
from asr_system.domain.value_objects import Emotion


class RuleBasedEmotionAdapter(EmotionPort):
    def classify(self, text: str) -> tuple[Emotion, float]:
        lowered = text.lower()
        if "issue" in lowered or "problem" in lowered or "bad" in lowered:
            return Emotion.ANGRY, 0.74
        if "sad" in lowered:
            return Emotion.SAD, 0.7
        if "thanks" in lowered or "good" in lowered:
            return Emotion.POSITIVE, 0.66
        return Emotion.NEUTRAL, 0.6
