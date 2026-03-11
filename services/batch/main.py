import sys
from datetime import date
from pathlib import Path

# Allows local execution without editable install.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from asr_system.interfaces.batch.runner import BatchRunner  # noqa: E402

if __name__ == "__main__":
    processed = BatchRunner().run(date.today())
    print(f"processed_calls={len(processed)}")
