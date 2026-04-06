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

    project_root = Path(__file__).resolve().parents[2]
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)

    logger.add(
        log_dir / "app.log",
        level="INFO",
        rotation="10 MB",
        retention="10 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    )

    return logger
