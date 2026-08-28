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
    // Walks the label's actual, LIVE descendants (a TreeWalker over real
    // text nodes), not a detached clone -- found necessary during
    // real-world validation against a live Lever posting: a label can
    // legitimately contain several state-dependent status messages all
    // present in the DOM simultaneously (e.g. a resume-upload widget's
    // "Analyzing resume...", "Success!", and a location-autocomplete
    // widget's "Loading"/"No location found" text), with only one
    // visible at a time via CSS. A detached clone has no meaningful
    // computed style at all (it isn't attached to the document's layout
    // tree), so visibility can only be checked against the real,
    // attached elements -- this is why cloning was abandoned in favor of
    // walking the live tree directly. Nested form controls
    // (input/select/textarea/button) are still excluded, exactly as
    // the clone-based version did.
    const parts = [];
    const walker = document.createTreeWalker(labelEl, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        let el = node.parentElement;
        while (el) {
          const tag = el.tagName.toLowerCase();
          if (tag === "input" || tag === "select" || tag === "textarea" || tag === "button") {
            return NodeFilter.FILTER_REJECT;
          }
          if (!isVisible(el)) return NodeFilter.FILTER_REJECT;
          if (el === labelEl) break;
          el = el.parentElement;
        }
        return NodeFilter.FILTER_ACCEPT;
      },
    });
    let node;
    while ((node = walker.nextNode())) {
      const text = node.textContent.trim();
      if (text) parts.push(text);
    }
    let text = parts.join(" ").trim();
    // Strip a common trailing "required" marker glyph (e.g. a literal
    // asterisk or the "✱" character seen on the real Lever field this
    // was verified against) so the label reads cleanly rather than
    // "Full name✱".
    if (text.endsWith("*") || text.endsWith("\u2731")) {
      text = text.slice(0, -1).trim();
    }
    return text || null;
  }

  function isVisible(el) {
    // offsetParent is null for display:none (and for any element with
    // a display:none ancestor) -- a cheap, single-property check that
    // covers the real cases found during validation. Also checks
    // visibility:hidden directly, since offsetParent alone does not
    // catch that case (a visibility:hidden element still participates
    // in layout).
    if (el.offsetParent === null) return false;
    if (window.getComputedStyle(el).visibility === "hidden") return false;
    return true;
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
