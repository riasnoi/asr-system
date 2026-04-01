"""Domain-level exceptions."""


class DomainError(Exception):
    """Base for all domain errors."""


class CallNotFoundError(DomainError):
    def __init__(self, call_id: str) -> None:
        self.call_id = call_id
        super().__init__(f"Call {call_id!r} not found")


class TranscriptionError(DomainError):
    def __init__(self, audio_path: str, reason: str) -> None:
        self.audio_path = audio_path
        super().__init__(f"Transcription failed for {audio_path!r}: {reason}")


class IngestError(DomainError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
