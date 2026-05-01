import json
import logging
import sys
from pathlib import Path

import structlog


_FILE_HANDLER: logging.FileHandler | None = None


def setup_logging(level: str = "INFO", log_file: str | None = None) -> None:
    global _FILE_HANDLER

    log_level = getattr(logging, level.upper(), logging.INFO)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    # If file logging requested, set up a dual-output processor
    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        _FILE_HANDLER = logging.FileHandler(str(path), encoding="utf-8")

        def _file_and_console(logger, method_name, event_dict):
            # Write JSON line to file
            file_line = json.dumps(event_dict, default=str, ensure_ascii=False)
            _FILE_HANDLER.stream.write(file_line + "\n")
            _FILE_HANDLER.stream.flush()
            # Continue to console rendering
            return event_dict

        processors = shared_processors + [_file_and_console, structlog.dev.ConsoleRenderer()]
    else:
        processors = shared_processors + [structlog.dev.ConsoleRenderer()]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
