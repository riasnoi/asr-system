from typing import Sequence

from asr_system.domain.ports import SpeakerAttributionPort


class AlternatingSpeakerAttribution(SpeakerAttributionPort):
    def assign_speakers(
        self, segments: Sequence[tuple[float, float, str]]
    ) -> list[tuple[float, float, str, str]]:
        result: list[tuple[float, float, str, str]] = []
        speakers = ["operator", "client"]
        for idx, (start_sec, end_sec, text) in enumerate(segments):
            result.append((start_sec, end_sec, text, speakers[idx % 2]))
        return result
