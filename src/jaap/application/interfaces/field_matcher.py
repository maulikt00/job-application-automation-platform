"""FieldMatcher interface (port) and the structured result it produces.

Defined as a Protocol specifically so a future AI-assisted matcher
(Phase 3's "question answering" capability, named in the original
project charter) can implement this same interface later. Unlike
BrowserAutomationEngine/FormFieldDetector, which only ever expect one
kind of implementation, matching logic is exactly where a smarter,
learned approach is expected to eventually supplement the conservative,
exact-match-only default (see application/services/field_matcher.py's
ExactFieldMatcher).

`match()`'s signature changed in Milestone 11 to add a `resume`
parameter: resume-matching (attaching a file to a detected file-upload
field) is conceptually the same responsibility as matching
full_name/email/phone against detected fields -- just a different data
source (a file path) and a different target action (upload_file()
instead of fill()) -- so it belongs in the same match() call rather
than a second mechanism a caller has to remember to invoke separately.
This is a breaking change to an interface introduced last milestone;
flagged explicitly since ExactFieldMatcher was, at the time, its only
implementation and consumer.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel

from jaap.application.interfaces.form_field_detector import DetectedField
from jaap.domain.models import Answer, Profile, Resume


class MatchedField(BaseModel):
    """A DetectedField paired with the value to fill and where that value
    came from.

    `source` exists for review/debugging transparency (e.g.
    "profile.email" or "answer:why-us") -- it's not used for any
    matching decision itself, just to make it obvious after the fact why
    a given field got filled with a given value. For a matched file
    upload, `value` is the resume's file path as a string (see
    AutofillApplicationUseCase._apply_fill(), which converts it back to
    a Path before calling upload_file()).
    """

    field: DetectedField
    value: str
    source: str


class FieldMatchResult(BaseModel):
    matched: list[MatchedField]
    unmatched: list[DetectedField]


class FieldMatcher(Protocol):
    def match(
        self,
        fields: list[DetectedField],
        profile: Profile,
        answers: list[Answer],
        resume: Resume | None = None,
    ) -> FieldMatchResult:
        """Match detected fields to values from `profile`/`answers`/`resume`.

        Fields with no `selector` are always left unmatched -- there
        would be no reliable way to act on them safely. Anything not
        confidently matched by the implementation's own criteria is left
        unmatched, never guessed. `resume` is optional: if omitted, any
        file-upload fields present are simply left unmatched, not an error.
        """
        ...
