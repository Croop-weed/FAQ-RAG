import structlog

from support_assistant.core.config import Settings
from support_assistant.core.logging import configure_logging


def test_logging_initialization_does_not_crash() -> None:
    configure_logging(Settings(environment="test"))

    structlog.get_logger(__name__).info("foundation logging test")
