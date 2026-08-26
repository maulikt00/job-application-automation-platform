"""Workday-aware FormFieldDetector: composes the generic detector for
native fields, and additionally detects ARIA `role="combobox"` elements
-- Workday's well-known custom dropdown/combobox widgets, which the
generic detector cannot see at all (it only queries
`input, select, textarea`; a combobox is typically a `<div>` or
`<button>`).

**An honest confidence distinction from GreenhouseConnector/LeverConnector,
stated plainly**: Greenhouse's `name="first_name"` and Lever's
`hostedUrl`/`applyUrl` relationship were confirmed directly from each
platform's own published documentation. This combobox detection is
NOT a confirmed Workday-specific selector -- it is based on the
standard, cross-platform ARIA pattern for accessible custom dropdowns
(`role="combobox"`, paired with `role="listbox"`/`role="option"`), which
Workday is widely discussed as using in the browser-automation
community, but which was not independently confirmed against a live
Workday tenant (this project has no such access). Documented as a
reasonable, standards-based inference, not verified platform-specific
knowledge -- see ADR-0023.

**A safety design following directly from that honest uncertainty**:
every combobox field this detector reports has `selector=None`. Per the
established, already-tested invariant from Milestone 9/10
(`ExactFieldMatcher` never matches a field with no selector), this
guarantees a detected combobox can NEVER be automatically matched or
filled -- it can only ever surface as a visible "unmatched field"
requiring human attention. This milestone's honest scope is DETECTION
ONLY: `AutofillApplicationUseCase` (Milestone 10) has no dispatch branch
for interacting with a combobox-style widget (open it, then click a
matching option) -- adding one is real, separate future work, not
something this connector attempts or assumes.
"""

from __future__ import annotations

from jaap.application.interfaces.browser_engine import BrowserAutomationEngine
from jaap.application.interfaces.form_field_detector import DetectedField
from jaap.infrastructure.browser.form_field_detector import PlaywrightFormFieldDetector

# Finds ARIA role="combobox" elements -- a standard, cross-platform
# pattern for accessible custom dropdowns, not a confirmed
# Workday-specific selector (see this module's docstring). Deliberately
# does NOT attempt to compute a selector for these elements: `selector`
# is always None, by design, so a detected combobox can never be
# automatically matched or filled (see module docstring).
_COMBOBOX_DETECTION_SCRIPT = """
(() => {
  function labelFor(el) {
    const labelledBy = el.getAttribute("aria-labelledby");
    if (labelledBy) {
      const labelEl = document.getElementById(labelledBy);
      if (labelEl && labelEl.textContent.trim()) return labelEl.textContent.trim();
    }
    const ariaLabel = el.getAttribute("aria-label");
    if (ariaLabel && ariaLabel.trim()) return ariaLabel.trim();
    return null;
  }

  const comboboxes = Array.from(document.querySelectorAll('[role="combobox"]'));

  return comboboxes.map((el) => ({
    tag: el.tagName.toLowerCase(),
    field_type: "combobox",
    name: el.getAttribute("data-automation-id") || null,
    element_id: el.id || null,
    selector: null,
    label: labelFor(el),
    required: el.getAttribute("aria-required") === "true",
    current_value: el.textContent ? el.textContent.trim() || null : null,
  }));
})()
"""


class WorkdayFormFieldDetector:
    """Satisfies application.interfaces.form_field_detector.FormFieldDetector.

    Composed with a BrowserAutomationEngine (constructor injection), and
    internally composes PlaywrightFormFieldDetector for native fields --
    not a subclass, matching the established composition-over-duplication
    pattern (ADR-0009).
    """

    def __init__(self, engine: BrowserAutomationEngine) -> None:
        self._engine = engine
        self._generic_detector = PlaywrightFormFieldDetector(engine)

    def detect_fields(self) -> list[DetectedField]:
        native_fields = self._generic_detector.detect_fields()
        combobox_fields = self._detect_comboboxes()
        return native_fields + combobox_fields

    def _detect_comboboxes(self) -> list[DetectedField]:
        raw_fields = self._engine.evaluate(_COMBOBOX_DETECTION_SCRIPT)
        return [DetectedField.model_validate(item) for item in raw_fields]
