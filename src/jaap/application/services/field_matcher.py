"""ExactFieldMatcher: the default, conservative FieldMatcher implementation.

Matches only on structural signals (the HTML input type) and exact,
normalized string equality (a field's name/label against a small,
explicit known-synonym set, or a field's label against an existing
Answer.question_key) -- never fuzzy/similarity scoring. Per this
project's own stated philosophy ("unmatched fields surfaced to the user
rather than guessed" -- PROJECT_ROADMAP.md), a similarity threshold is
itself a form of guessing, just a quantified one; this implementation
avoids that entirely. Anything not confidently, exactly matched is left
unmatched.

Does NOT attempt to split Profile.full_name into first/last name parts
for forms with separate fields -- doing so would itself be guessing
which part maps to which.

File-upload fields (Milestone 11) are matched ONLY by an explicit
resume-related synonym on the field's name/label, never by
`field_type == "file"` alone: a real form can have file uploads for a
cover letter, portfolio, or transcript, and blindly uploading a resume
into any file input would be a correctness bug, not just an unmatched
field.
"""

from __future__ import annotations

from jaap.application.interfaces.field_matcher import FieldMatchResult, MatchedField
from jaap.application.interfaces.form_field_detector import DetectedField
from jaap.domain.models import Answer, Profile, Resume
from jaap.utils.slugify import slugify

# Small, explicit, human-reviewable synonym sets -- not exhaustive by
# design. Everything not listed here is intentionally left unmatched
# rather than guessed at. Written already in slug form (hyphens, not
# spaces) since both sides of the comparison are normalized with the
# same slugify() function.
_FULL_NAME_SYNONYMS = frozenset({"name", "full-name", "fullname", "your-name", "applicant-name"})
_EMAIL_SYNONYMS = frozenset({"email", "e-mail", "email-address"})
_PHONE_SYNONYMS = frozenset({"phone", "phone-number", "telephone", "mobile", "mobile-number"})
_RESUME_SYNONYMS = frozenset(
    {"resume", "cv", "resume-upload", "upload-resume", "attach-resume", "resume-file", "your-resume"}
)


class ExactFieldMatcher:
    """Satisfies application.interfaces.field_matcher.FieldMatcher."""

    def match(
        self,
        fields: list[DetectedField],
        profile: Profile,
        answers: list[Answer],
        resume: Resume | None = None,
    ) -> FieldMatchResult:
        answers_by_key = {answer.question_key: answer for answer in answers}
        matched: list[MatchedField] = []
        unmatched: list[DetectedField] = []

        for field in fields:
            result = self._match_one(field, profile, answers_by_key, resume)
            if result is not None:
                matched.append(result)
            else:
                unmatched.append(field)

        return FieldMatchResult(matched=matched, unmatched=unmatched)

    def _match_one(
        self,
        field: DetectedField,
        profile: Profile,
        answers_by_key: dict[str, Answer],
        resume: Resume | None,
    ) -> MatchedField | None:
        if field.selector is None:
            return None  # never fill something we can't reliably target

        name_slug = slugify(field.name) if field.name else None
        label_slug = slugify(field.label) if field.label else None

        # File uploads: matched ONLY by an explicit resume synonym, never
        # by field_type == "file" alone (see module docstring).
        if field.field_type == "file":
            if resume is not None and (
                name_slug in _RESUME_SYNONYMS or label_slug in _RESUME_SYNONYMS
            ):
                return MatchedField(
                    field=field, value=resume.file_path.as_posix(), source="resume.file_path"
                )
            return None

        # 1. Structural signal: the HTML input type is the strongest,
        # least ambiguous match available -- it's authoritative metadata
        # the form author set deliberately, not a guess on our part.
        if field.field_type == "email":
            return MatchedField(field=field, value=profile.email, source="profile.email")
        if field.field_type == "tel" and profile.phone is not None:
            return MatchedField(field=field, value=profile.phone, source="profile.phone")

        # 2. Exact name/label match against a small, explicit synonym set.
        if name_slug in _FULL_NAME_SYNONYMS or label_slug in _FULL_NAME_SYNONYMS:
            return MatchedField(field=field, value=profile.full_name, source="profile.full_name")
        if name_slug in _EMAIL_SYNONYMS or label_slug in _EMAIL_SYNONYMS:
            return MatchedField(field=field, value=profile.email, source="profile.email")
        if (
            name_slug in _PHONE_SYNONYMS or label_slug in _PHONE_SYNONYMS
        ) and profile.phone is not None:
            return MatchedField(field=field, value=profile.phone, source="profile.phone")

        # 3. Exact label match against an existing reusable Answer,
        # normalized with the SAME slugify() Answer.question_key itself
        # uses (see utils/slugify.py) -- not a separately-maintained rule
        # that could silently drift from it.
        if label_slug is not None and label_slug in answers_by_key:
            answer = answers_by_key[label_slug]
            return MatchedField(
                field=field, value=answer.answer_text, source=f"answer:{answer.question_key}"
            )

        return None
