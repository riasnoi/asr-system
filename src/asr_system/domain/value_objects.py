from enum import Enum


class Emotion(str, Enum):
    POSITIVE = "positive"
    SAD = "sad"
    ANGRY = "angry"
    NEUTRAL = "neutral"
