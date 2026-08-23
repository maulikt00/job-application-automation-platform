"""Slug normalization, shared by any code that needs to canonicalize
free text into a stable, comparable key.

Originally lived only in domain/models/answer.py (Milestone 2); extracted
here in Milestone 10 so ExactFieldMatcher can normalize a DetectedField's
label using the exact same rule Answer.question_key already uses.
Duplicating this regex in two places would risk them silently drifting
out of sync, which would break "does this field's label match this
answer's question_key" in a hard-to-diagnose way -- exactly the kind of
duplication this project's own review process (see ADR-0005's mapper
extraction) has caught before.

Pure function, no I/O, no dependency -- fits utils/'s own rule
(dependency-free, no I/O; see utils/__init__.py).
"""

from __future__ import annotations

import re

_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """Normalize `text` into a lowercase, hyphen-separated slug.

    E.g. "Why do you want to work here?" -> "why-do-you-want-to-work-here".
    Returns an empty string if `text` contains no alphanumeric characters.
    """
    return _SLUG_PATTERN.sub("-", text.strip().lower()).strip("-")
