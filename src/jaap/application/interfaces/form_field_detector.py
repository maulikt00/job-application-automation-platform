"""FormFieldDetector interface (port) and DetectedField, the structured
data it produces.

Composed with a BrowserAutomationEngine via constructor injection, not
added as a new BrowserAutomationEngine method -- see
docs/adr/0009-form-field-detector.md for why: form-field detection is
domain-specific logic (what counts as a "field", how to guess a label,
which types to exclude), and the engine itself is meant to stay a
generic automation toolkit with no knowledge of forms. This mirrors how
mappers were split out from repositories (ADR-0005): a focused component
composed with the lower-level primitive, not folded into it.

DetectedField is not a domain model (domain/models/): it isn't a
persisted business concept, it's structured data flowing from the
browser layer toward a future autofill use case (Milestone 10) -- the
concrete consumer ADR-0006 deferred DTOs until one existed.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class DetectedField(BaseModel):
    """A single fillable field detected on the current page.

    Attributes:
        tag: The HTML tag name -- "input", "select", or "textarea".
        field_type: For "input", the element's `type` attribute
            (defaulting to "text" if unset), lowercased -- e.g. "email",
            "checkbox", "tel". For "select", "select-one" or
            "select-multiple". For "textarea", literally "textarea".
        name: The element's `name` attribute, if set.
        element_id: The element's `id` attribute, if set.
        label: A best-effort label guess, in priority order: an
            associated `<label for="...">` element's text, then
            `aria-label`, then `placeholder`. None if none of these exist.
        required: Whether the element has the `required` attribute.
        current_value: The field's current value as a string. For
            checkboxes/radios, "true"/"false" reflecting `.checked`
            (there's no single meaningful "value" otherwise, since the
            HTML `value` attribute on a checkbox is unrelated to whether
            it's checked). For everything else, the element's `.value`.
    """

    tag: str
    field_type: str
    name: str | None = None
    element_id: str | None = None
    label: str | None = None
    required: bool = False
    current_value: str | None = None


class FormFieldDetector(Protocol):
    def detect_fields(self) -> list[DetectedField]:
        """Detect fillable fields on the current page.

        Excludes hidden fields (`type="hidden"`), disabled fields, and
        button-like input types (`submit`, `button`, `reset`, `image`) --
        none of these are user-fillable form fields, and a submit button
        showing up in "fields to fill" would be actively wrong.
        """
        ...
