import logging
from app.utils.logging_context import get_correlation_id


class CorrelationIdFilter(logging.Filter):
    """Filter that injects the request correlation ID into every log record."""

    def filter(self, record) -> bool:
        corr_id = get_correlation_id()
        record.correlation_id = corr_id if corr_id else "-"
        return True


def setup_logging() -> None:
    """Configures structured logs prefixed with the dynamic correlation ID."""
    root = logging.getLogger()
    
    # Format pattern to display: timestamp level [correlation_id] logger - message
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(correlation_id)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.addFilter(CorrelationIdFilter())
    
    # Clean previous handlers to avoid duplicate output streams
    for h in list(root.handlers):
        root.removeHandler(h)
        
    root.addHandler(handler)
    root.setLevel(logging.INFO)
