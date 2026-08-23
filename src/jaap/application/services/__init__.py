"""Concrete implementations of application-layer interfaces that have no
external/infrastructure dependency -- pure logic only.

Contrast with infrastructure/, which holds implementations that DO
depend on external systems (databases, browsers, third-party SDKs).
ExactFieldMatcher (field_matcher.py) is the first example: it depends
only on domain models and application/interfaces types, nothing
external, so it has no reason to live in infrastructure/ alongside
Playwright/SQLAlchemy-backed adapters.
"""
