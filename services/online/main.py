import sys
from pathlib import Path

# Allows local execution without editable install.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import uvicorn  # noqa: E402

from asr_system.config import get_settings  # noqa: E402
from asr_system.interfaces.online.api import app  # noqa: E402

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(app, host=settings.api.host, port=settings.api.port)
