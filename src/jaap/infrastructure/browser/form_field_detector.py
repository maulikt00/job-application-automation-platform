"""Playwright-backed FormFieldDetector implementation.

Composed with a BrowserAutomationEngine (constructor injection), not
Playwright directly, and not a subclass of PlaywrightBrowserEngine --
this class only ever calls engine.evaluate(), the one generic primitive
BrowserAutomationEngine exposes. It would work identically against any
other BrowserAutomationEngine implementation, which is the whole point
of not depending on Playwright's own API here.
"""

from __future__ import annotations

from jaap.application.interfaces.browser_engine import BrowserAutomationEngine
from jaap.application.interfaces.form_field_detector import DetectedField

# Runs entirely in the browser via engine.evaluate(). Returns a plain
# JSON-compatible array of objects matching DetectedField's fields
# exactly, so Python-side parsing is a direct model_validate() per item.
_DETECTION_SCRIPT = r"""
(() => {
  const EXCLUDED_INPUT_TYPES = new Set(["hidden", "submit", "button", "reset", "image"]);

  function labelFor(el) {
    // Explicit association: <label for="id">Text</label> ... <input id="id">
    if (el.id) {
      const associated = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (associated) {
        const text = textExcludingNestedControls(associated);
        if (text) return text;
      }
    }
    // Implicit association: <label>Text<input></label> -- an equally
    // valid, standard HTML pattern with no `for`/`id` at all. Found
    // missing during real-world validation against a live Lever
    // application form (2026-08): Lever wraps its "Full name"/"Email"
    // inputs and each individual checkbox option this way, with no
    // `for`/`id` pairing and no aria-label -- every one of those fields
    // was previously reported with no label at all.
    const wrappingLabel = el.closest("label");
    if (wrappingLabel) {
      const text = textExcludingNestedControls(wrappingLabel);
      if (text) return text;
    }
    const ariaLabel = el.getAttribute("aria-label");
    if (ariaLabel && ariaLabel.trim()) return ariaLabel.trim();
    const placeholder = el.getAttribute("placeholder");
    if (placeholder && placeholder.trim()) return placeholder.trim();
    return null;
  }

  function textExcludingNestedControls(labelEl) {
    // Clone and strip any nested form controls before reading
    // textContent -- a <label> can wrap a <select> with many <option>
    // children (whose text would otherwise leak into the label), or,
    // as found in the same real-world validation, wrap the field
    // itself alongside the label text.
    const clone = labelEl.cloneNode(true);
    clone.querySelectorAll("input, select, textarea, button").forEach((node) => node.remove());
    let text = clone.textContent.trim();
    // Strip a common trailing "required" marker glyph (e.g. a literal
    // asterisk or the "✱" character seen on the real Lever field this
    // was verified against) so the label reads cleanly rather than
    // "Full name✱".
    text = text.replace(/[*✱]\s*$/, "").trim();
    return text || null;
  }

  function selectorFor(el) {
    // EEO / voluntary self-identification fields (gender, race, veteran
    // status, disability status, and the disability disclosure's own
    // signature/date fields) must NEVER be auto-fillable, regardless of
    // what their label says. Found via real-world validation against a
    // live Lever posting (2026-08, see ADR-0026): a disability
    // self-identification SIGNATURE field is commonly labeled "Full
    // Name" (the standard federal CC-305 form template's own wording)
    // -- indistinguishable, by label text alone, from an ordinary
    // contact-info "full name" field. Forcing selector=null here is the
    // same structural safety pattern already used for Workday's
    // ARIA-combobox fields (ADR-0023): the existing, already-tested
    // invariant that a field with no selector can never be matched or
    // filled (see application/services/field_matcher.py) makes this a
    // hard guarantee, not something that depends on every FieldMatcher
    // implementation separately remembering to special-case it.
    if (isEeoField(el)) return null;
    if (el.id) return `#${CSS.escape(el.id)}`;
    if (el.name) return `[name="${CSS.escape(el.name)}"]`;
    return null;
  }

  function isEeoField(el) {
    // Verified against real Lever markup: eeo[gender], eeo[race],
    // eeo[veteran], eeo[disability], eeo[disabilitySignature],
    // eeo[disabilitySignatureDate] all share this literal "eeo["
    // prefix. This is Lever's own naming convention, confirmed on one
    // real platform -- not yet verified against Greenhouse/Workday's
    // own voluntary-disclosure field naming, which may differ and would
    // need this check extended once validated for real (see ADR-0026).
    const name = (el.name || "").toLowerCase();
    return name.startsWith("eeo[") || name.startsWith("eeo_") || name.startsWith("eeo-");
  }

  function fieldType(el) {
    const tag = el.tagName.toLowerCase();
    if (tag === "select") return el.multiple ? "select-multiple" : "select-one";
    if (tag === "textarea") return "textarea";
    return (el.type || "text").toLowerCase();
  }

  function currentValue(el) {
    const tag = el.tagName.toLowerCase();
    if (tag === "input" && (el.type === "checkbox" || el.type === "radio")) {
      return el.checked ? "true" : "false";
    }
    return el.value != null ? String(el.value) : null;
  }

  const elements = Array.from(document.querySelectorAll("input, select, textarea"));

  return elements
    .filter((el) => {
      if (el.disabled) return false;
      if (el.tagName.toLowerCase() === "input") {
        const type = (el.type || "").toLowerCase();
        if (EXCLUDED_INPUT_TYPES.has(type)) return false;
      }
      return true;
    })
    .map((el) => ({
      tag: el.tagName.toLowerCase(),
      field_type: fieldType(el),
      name: el.name || null,
      element_id: el.id || null,
      selector: selectorFor(el),
      label: labelFor(el),
      required: Boolean(el.required),
      current_value: currentValue(el),
    }));
})()
"""


class PlaywrightFormFieldDetector:
    """Satisfies application.interfaces.form_field_detector.FormFieldDetector."""

    def __init__(self, engine: BrowserAutomationEngine) -> None:
        self._engine = engine

    def detect_fields(self) -> list[DetectedField]:
        raw_fields = self._engine.evaluate(_DETECTION_SCRIPT)
        return [DetectedField.model_validate(item) for item in raw_fields]
