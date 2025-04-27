from app.utils.logger import logger

class ToolError(Exception):
    """Raised when a tool encounters an error."""

    def __init__(self, message):
        logger.error("Tool Error message")
        self.message = message

class LLMError(Exception):
    """Raised when a LLM encounters an error."""

    def __init__(self, message):
        logger.error("LLM Error message")
        self.message = message