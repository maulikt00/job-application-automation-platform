# Domain Model: Aggregates, Relationships, and Repositories

This document precedes Milestone 2 (domain model implementation) and defines
the aggregate boundaries the Pydantic models must respect. See
[ARCHITECTURE.md](../../ARCHITECTURE.md) for how the domain layer fits into
the overall system.

## Aggregate Boundary Reasoning

Each entity below was evaluated against one question: **does it have a
lifecycle and identity worth managing independently?**

- **Profile** — root of "who is applying." Aggregate root.
- **Resume** — independently created, listed, and selected across many
  applications; too substantial to embed inside `Profile`. Aggregate root,
  references `Profile` by ID.
- **CoverLetterTemplate** — same reasoning as Resume. Aggregate root,
  references `Profile` by ID.
- **Answer** — a reusable answer is created once and reused across many
  applications; needs independent search/reuse. Aggregate root, references
  `Profile` by ID.
- **JobPosting** — externally-sourced data (scraped/connector-provided),
  not owned by any Profile. Keeping it un-owned now avoids a restructure
  when multi-user support (Phase 5) arrives. Aggregate root, no owner
  reference.
- **Application** — the central transactional record tying a profile,
  resume, job posting, optional template, and answers together, with its
  own status lifecycle. Aggregate root.
- **ApplicationStatus** / **ApplicationStatusEvent** — value objects with
  no independent identity; persisted as part of the `Application`
  aggregate, never fetched on their own.

**Governing rule:** aggregates reference other aggregates only by ID, never
by embedded object. This is what allows each repository to load, save, and
enforce invariants on only its own aggregate, independent of the rest.

## Diagram

```mermaid
classDiagram
    class Profile {
        <<AggregateRoot>>
        +ProfileId id
        +str full_name
        +str email
        +str phone
    }

    class Resume {
        <<AggregateRoot>>
        +ResumeId id
        +ProfileId profile_id
        +str label
        +Path file_path
        +datetime uploaded_at
    }

    class CoverLetterTemplate {
        <<AggregateRoot>>
        +TemplateId id
        +ProfileId profile_id
        +str name
        +str body_template
    }

    class Answer {
        <<AggregateRoot>>
        +AnswerId id
        +ProfileId profile_id
        +str question_key
        +str answer_text
        +list~str~ tags
    }

    class JobPosting {
        <<AggregateRoot>>
        +JobPostingId id
        +str company_name
        +str title
        +str url
        +str platform
        +str description
    }

    class Application {
        <<AggregateRoot>>
        +ApplicationId id
        +ProfileId profile_id
        +ResumeId resume_id
        +JobPostingId job_posting_id
        +TemplateId cover_letter_template_id
        +list~AnswerId~ answer_ids
        +ApplicationStatus current_status
        +datetime created_at
    }

    class ApplicationStatus {
        <<ValueObject: Enum>>
        DRAFT
        SUBMITTED
        INTERVIEWING
        OFFER
        REJECTED
        WITHDRAWN
    }

    class ApplicationStatusEvent {
        <<ValueObject>>
        +ApplicationStatus status
        +datetime changed_at
        +str note
    }

    Profile "1" --> "0..*" Resume : owns
    Profile "1" --> "0..*" CoverLetterTemplate : owns
    Profile "1" --> "0..*" Answer : owns
    Profile "1" --> "0..*" Application : submits

    JobPosting "1" --> "0..*" Application : targeted by

    Application "0..*" --> "1" Resume : uses (by id)
    Application "0..*" --> "0..1" CoverLetterTemplate : uses (by id)
    Application "0..*" --> "0..*" Answer : uses (by id)

    Application "1" *-- "1..*" ApplicationStatusEvent : status history
    Application "1" --> "1" ApplicationStatus : current status
```

`-->` = reference-by-ID association across aggregate boundaries.
`*--` = composition, owned with no independent identity.

## Cardinality Summary

| Relationship | Cardinality | Notes |
|---|---|---|
| Profile → Resume | 1 → 0..* | one profile, many resumes |
| Profile → CoverLetterTemplate | 1 → 0..* | one profile, many templates |
| Profile → Answer | 1 → 0..* | one profile, many reusable answers |
| Profile → Application | 1 → 0..* | one profile, many applications over time |
| JobPosting → Application | 1 → 0..* | same posting can have multiple attempts |
| Application → Resume | 0..* → 1 | many applications can reuse the same resume |
| Application → CoverLetterTemplate | 0..* → 0..1 | optional; may use an unsaved one-off letter |
| Application → Answer | 0..* ↔ 0..* | true many-to-many; needs a join table once persisted (Milestone 4) |
| Application → ApplicationStatusEvent | 1 → 1..* | append-only history, always ≥1 event (`DRAFT`) |

## Repositories

One per aggregate root — six total:

- `ProfileRepository`
- `ResumeRepository`
- `CoverLetterTemplateRepository`
- `AnswerRepository`
- `JobPostingRepository`
- `ApplicationRepository`

No repository exists for `ApplicationStatus` or `ApplicationStatusEvent` —
they are value objects persisted as part of `ApplicationRepository`'s
responsibility. Cross-aggregate composition (e.g., assembling a full
"review this application" view) is done by use cases calling multiple
repositories — never by a repository reaching into another aggregate.
