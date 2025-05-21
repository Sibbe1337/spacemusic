# libs/py_common/logging.py

import logging
import sys
import structlog

def setup_logging(log_level: str = "INFO"):
    """Configures structlog for JSON logging."""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level.upper(),
    )

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name, # useful for identifying module
            structlog.stdlib.add_log_level, # adds 'level' key, e.g. 'info'
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"), # ISO 8601 timestamp
            structlog.processors.StackInfoRenderer(), # useful for exceptions
            structlog.processors.format_exc_info, # formats exception info
            structlog.processors.UnicodeDecoder(), # decodes unicode
            # Key-value formatting for JSON logs
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    print(f"Structlog configured for JSON logging at level {log_level.upper()}.")

# Call setup_logging() early in your application startup,
# for example in main.py of your services.
# setup_logging() 