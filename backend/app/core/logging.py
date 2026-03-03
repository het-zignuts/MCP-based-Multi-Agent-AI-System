from loguru import logger
import System

def setup_logging():
    logger.remove()
    logger.add(
        sys.stdout,
        format="{time} | {level} | {message}",
        level="INFO"
    )