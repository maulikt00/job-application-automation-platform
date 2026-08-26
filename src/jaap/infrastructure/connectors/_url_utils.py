"""Shared URL manipulation helpers for connector implementations.

Extracted from lever_connector.py once workday_connector.py needed the
identical logic: both Lever and Workday document a `/apply`-suffix
relationship between a job posting's URL and its application form's URL
(confirmed independently for each platform -- see ADR-0022/0023), so the
path-appending logic itself is genuinely shared, not coincidentally
similar. Kept as a private module (`_` prefix) since this is internal
to `infrastructure/connectors/`, not part of any public interface.
"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit


def append_apply_path(url: str) -> str:
    """Appends `/apply` to `url`'s path, preserving any query string and
    handling a trailing slash or an already-present `/apply` suffix
    idempotently.
    """
    parts = urlsplit(url)
    path = parts.path.rstrip("/")
    if path.endswith("/apply"):
        return url
    return urlunsplit((parts.scheme, parts.netloc, path + "/apply", parts.query, parts.fragment))
