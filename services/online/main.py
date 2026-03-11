import uvicorn

from asr_system.config import get_settings
from asr_system.interfaces.online.api import app


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(app, host=settings.api.host, port=settings.api.port)
