import functools
import logging
import time

import requests

logger = logging.getLogger(__name__)


def log_execution(func):
    """Log function name and elapsed time (ms) at INFO level."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info("%s finished in %.1f ms", func.__name__, elapsed_ms)
        return result
    return wrapper


def handle_api_errors(default_factory):
    """Catch network / parsing errors; log with traceback; return default_factory()."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except (requests.Timeout, requests.RequestException, ValueError, KeyError) as exc:
                logging.exception("API error in %s: %s", func.__name__, exc)
                return default_factory()
        return wrapper
    return decorator
