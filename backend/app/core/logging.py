from loguru import logger
import sys

def setup_logging():
    logger.remove()
    logger.add(
        sys.stdout,
        format="{time} | {level} | {message}",
        level="INFO"
    )