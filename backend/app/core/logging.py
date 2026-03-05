from loguru import logger
import sys
from pathlib import Path

def setup_logging():

    logger.remove()

    logger.add(
        sys.stdout,
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
    )

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logger.add(
        log_dir / "app.log",
        rotation="10 MB",
        retention="10 days"
    )

    return logger