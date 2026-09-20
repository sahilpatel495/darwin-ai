"""The one error ingestion raises.

It lives in its own module so the readers can raise it without importing the package
that imports them. `app.ingest` re-exports it; import it from there.
"""

from __future__ import annotations


class IngestError(ValueError):
    """Raised with a human-readable message (shown to the user as-is).

    Every message says what happened and, where there is one, what to do next. It never
    carries a stack trace, a server path or text taken from inside the file.
    """
