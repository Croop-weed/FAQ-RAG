import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

from support_assistant.core.config import Settings


def configure_logging(settings: Settings) -> None:
    """Configure JSON structured logs with request context and environment."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    def add_environment(
        logger: Any, method_name: str, event_dict: MutableMapping[str, Any]
    ) -> MutableMapping[str, Any]:
        event_dict["environment"] = settings.environment
        return event_dict

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.add_log_level,
            add_environment,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(file=sys.__stderr__),
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )
