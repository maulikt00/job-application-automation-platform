"""SaveCoverLetterTemplateUseCase: upsert a CoverLetterTemplate for a Profile.

Named for the reusable-template CRUD operation, not AI generation --
that's a separate future use case (Phase 3, likely
generate_cover_letter.py) that produces bespoke content for a specific
application, which is a different responsibility from managing the
reusable templates this use case handles.
"""

from __future__ import annotations

from jaap.application.exceptions import ProfileNotFoundError
from jaap.application.interfaces.repositories import (
    CoverLetterTemplateRepository,
    ProfileRepository,
)
from jaap.domain.models import (
    CoverLetterTemplate,
    CoverLetterTemplateId,
    ProfileId,
    new_cover_letter_template_id,
)


class SaveCoverLetterTemplateUseCase:
    """Creates or updates a CoverLetterTemplate.

    Verifies the Profile exists first, same reasoning as AddResumeUseCase.
    Pass `template_id` to update an existing template; omit it to create
    a new one -- matches CoverLetterTemplateRepository.save()'s own
    upsert semantics (see ADR-0005).
    """

    def __init__(
        self,
        template_repository: CoverLetterTemplateRepository,
        profile_repository: ProfileRepository,
    ) -> None:
        self._template_repository = template_repository
        self._profile_repository = profile_repository

    def execute(
        self,
        profile_id: ProfileId,
        name: str,
        body_template: str,
        template_id: CoverLetterTemplateId | None = None,
    ) -> CoverLetterTemplate:
        if self._profile_repository.get(profile_id) is None:
            raise ProfileNotFoundError(profile_id)

        template = CoverLetterTemplate(
            id=template_id or new_cover_letter_template_id(),
            profile_id=profile_id,
            name=name,
            body_template=body_template,
        )
        self._template_repository.save(template)
        return template
