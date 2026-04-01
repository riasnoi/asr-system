import uvicorn

from asr_system.config import get_settings
from asr_system.logging_config import setup_logging

if __name__ == "__main__":
    settings = get_settings()
    setup_logging(settings.app.log_level)

    from asr_system.interfaces.online.api import app

    uvicorn.run(app, host=settings.api.host, port=settings.api.port)
