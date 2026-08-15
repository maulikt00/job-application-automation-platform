"""Base class for domain entities.

Unlike Pydantic's default field-by-field equality, domain entities are
defined by identity: two Entity instances represent the same real-world
object if they share the same type and id, regardless of what any other
field currently holds (e.g. a freshly loaded copy vs. a locally mutated
one). See docs/adr/0003-entity-identity-and-connector-extensibility.md
for the reasoning.

Value objects (e.g. ApplicationStatusEvent) intentionally do NOT inherit
from this class -- their equality should remain structural, since they
have no identity independent of their attribute values.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class Entity(BaseModel):
    """Base class for aggregate roots and other identity-bearing domain
    objects.

    Subclasses must declare their own, more specific `id` field (e.g.
    `id: ProfileId`), which narrows this placeholder annotation -- Pydantic
    supports overriding a field's type in a subclass. Equality and hashing
    are based solely on (type, id), never on any other field.
    """

    id: Any

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        return type(self) is type(other) and self.id == other.id

    def __hash__(self) -> int:
        return hash((type(self), self.id))
