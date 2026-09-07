"""Narrow recovery for dropped MySQL connections on known read-only paths."""

from functools import wraps
import logging

from django.db import DEFAULT_DB_ALIAS, connections


logger = logging.getLogger(__name__)
MYSQL_DISCONNECT_ERROR_CODES = frozenset({2002, 2006, 2013, 2055})
_NO_FALLBACK = object()


def is_mysql_disconnect_error(exc):
    """Return whether ``exc`` is one of the reconnect-safe MySQL failures."""
    pending = [exc]
    seen = set()
    while pending:
        current = pending.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        args = getattr(current, "args", ())
        if args:
            try:
                if int(args[0]) in MYSQL_DISCONNECT_ERROR_CODES:
                    return True
            except (TypeError, ValueError):
                pass
        pending.extend(
            nested
            for nested in (
                getattr(current, "__cause__", None),
                getattr(current, "__context__", None),
            )
            if nested is not None
        )
    return False


def retry_mysql_read(operation, *, fallback=_NO_FALLBACK, using=DEFAULT_DB_ALIAS):
    """Retry one explicitly read-only operation after a dropped connection.

    This is intentionally not a generic database retry: callers must opt in
    only for read-only work, and transaction blocks are never repeated.
    """
    connection = connections[using]
    for attempt in range(2):
        try:
            return operation()
        except Exception as exc:
            if not is_mysql_disconnect_error(exc) or connection.in_atomic_block:
                raise

            try:
                connection.close()
            except Exception:
                # ``close()`` can itself hit the same broken driver cursor;
                # Django still discards the underlying connection in ``finally``.
                pass

            if attempt == 0:
                logger.warning("Dropped MySQL connection on read; retrying once")
                continue
            if fallback is not _NO_FALLBACK:
                logger.warning("Dropped MySQL connection on read after retry")
                return fallback
            raise


def retry_mysql_auth_view(*, fallback=None, using=DEFAULT_DB_ALIAS):
    """Retry only lazy authentication for safe HTTP methods.

    AuthenticationMiddleware resolves ``request.user`` lazily. A dropped
    connection at that boundary happens before a view's own read retry can
    run. Resolve it once through the reconnect-safe helper, then invoke the
    view exactly once so a GET with conditional reconciliation is never
    replayed after it has started.
    """
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method not in {"GET", "HEAD"}:
                return view(request, *args, **kwargs)
            try:
                retry_mysql_read(
                    lambda: bool(request.user.is_authenticated),
                    using=using,
                )
            except Exception as exc:
                if not is_mysql_disconnect_error(exc) or fallback is None:
                    raise
                return fallback(request, *args, **kwargs)
            return view(request, *args, **kwargs)

        return wrapped

    return decorator


def retry_mysql_read_view(view):
    """Apply the read retry only to GET/HEAD views with no write contract."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.method not in {"GET", "HEAD"}:
            return view(request, *args, **kwargs)
        return retry_mysql_read(lambda: view(request, *args, **kwargs))

    return wrapped
