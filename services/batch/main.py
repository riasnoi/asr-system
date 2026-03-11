from datetime import date

from asr_system.interfaces.batch.runner import BatchRunner


if __name__ == "__main__":
    processed = BatchRunner().run(date.today())
    print(f"processed_calls={len(processed)}")
