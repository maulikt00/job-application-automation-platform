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
    if (el.id) return `#${CSS.escape(el.id)}`;
    if (el.name) return `[name="${CSS.escape(el.name)}"]`;
    return null;
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
