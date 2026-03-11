from asr_system.domain.ports import ASRPort


class MockAsrAdapter(ASRPort):
    """Stub adapter to keep MVP architecture executable before real model integration."""

    def transcribe(self, audio_path: str) -> list[tuple[float, float, str]]:
        return [
            (0.0, 2.0, f"hello from {audio_path}"),
            (2.0, 5.0, "client says there is an issue"),
        ]
