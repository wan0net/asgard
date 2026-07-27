# Mimir knowledge model

This page defines the logical information model for Mimir. AFFiNE stores the canonical, human-readable record; a controlled indexer projects permitted,
accepted revisions into disposable Mem0 semantic retrieval. This is a reference design, not a claim that an integration is operational.
Each deployment must pin and validate its AFFiNE mapping, connector, normalizer, chunker, and Mem0 adapter before enabling writes or indexing.

## Why a hybrid model

Knowledge needs three independent answers:

1. **Where is this useful?** PARA supplies work context and navigation.
2. **What kind of knowledge is it?** Typed records supply meaning and required fields.
3. **How trusted and current is it?** The governance lifecycle supplies review state.

Combining these axes avoids treating a folder as record meaning or an archived project as deleted knowledge. A decision can relate to a Project and an Area,
remain canonical after the Project becomes inactive, and later be superseded.

## Design principles

- AFFiNE is the canonical, human-editable source of truth.
- Stable record and page identifiers, not titles or locations, carry identity.
- PARA context, record type, and lifecycle status are independent axes.
- Records may relate to several contexts and have at most one primary context.
- Provenance is retained through promotion, consolidation, and supersession.
- Material conflicts are represented; they are not silently overwritten.
- Destructive changes require explicit authority, review, and an audit trail.
- Classification applies to canonical content and every derived representation.
- Mem0 contains deterministic, permitted projections, never independent facts.

## Axis 1: PARA work context

PARA describes why material is relevant to current work. It is context and navigation, not a semantic record type. Moving a record between PARA views does not change its type.

| Context | Meaning | Required distinguishing fields |
| --- | --- | --- |
| Project | Time-bounded outcome with a finish condition | `context_id`, `name`, `outcome`, `state`, `started_at`, optional `target_at` |
| Area | Ongoing responsibility or standard to maintain | `context_id`, `name`, `responsibility`, `owner_refs`, `state` |
| Resource | Topic or material retained for possible use | `context_id`, `name`, `topic`, `state` |
| Archive | Inactive context retained for history and retrieval | `context_id`, `name`, `prior_kind`, `archived_at`, `archive_reason`, `state` |

`state` distinguishes active from inactive context. Archive means inactive
context, not deletion, tombstoning, lost provenance, or lost canonicality.
Archived contexts and linked records remain governed independently.

A record may link to zero or more PARA contexts through stable `context_refs`.
One may be the `primary_context` for presentation and must match one entry in
`context_refs`. Changing it is navigation, not a claim that an entity belongs in
one folder.

Context containers may themselves be typed `context` records when they need a description, owner, history, relations, or review. Their `para_kind` does not replace their record type.

## Axis 2: typed knowledge records

The record type selects validation rules. The common envelope applies to every type; `typed_fields` contains the minimum type-specific fields below.

| Type | Purpose | Type-specific minimum fields |
| --- | --- | --- |
| `note` | Bounded observation or explanation not represented by a stronger type | `body`, `note_kind` |
| `decision` | Chosen course of action and its rationale | `decision`, `rationale`, `decided_at`, `decision_status`, `decision_maker_refs` |
| `person` | Knowledge about a person relevant to permitted work | `display_name`, `identity_scope` |
| `organization` | Knowledge about a group or legal/operating entity | `name`, `organization_kind` |
| `meeting` | A time-bounded interaction and its durable outcomes | `started_at`, `participant_refs`, `agenda_or_purpose`, `outcome_summary` |
| `commitment` | A promised outcome with an accountable owner | `commitment`, `owner_refs`, `commitment_status`, optional `due_at` |
| `preference` | A stated or inferred choice that may need reconfirmation | `subject_ref`, `preference`, `confidence`, `basis`, `last_confirmed_at` |
| `procedure` | Repeatable steps and their operating conditions | `objective`, `steps`, `preconditions`, `verification` |
| `source` | A citable origin or retained evidence reference | `source_kind`, `locator`, `captured_at`, `content_hash` |
| `concept` | A defined term, model, or durable idea | `definition`, `scope` |
| `context` | A PARA container that also needs record governance | `para_kind`, `context_id`, `description`, `state` |

Deployments may add versioned types but must not reinterpret an existing type without a schema migration. Do not use `note` to avoid a more precise type.

## Axis 3: governance lifecycle

Lifecycle says whether material was reviewed and remains the active canonical statement. It is separate from PARA Archive.

| Status | Meaning | Indexing rule |
| --- | --- | --- |
| `candidate` | Newly extracted or proposed material with provenance, not yet ready for acceptance | Do not place in the active Mem0 generation |
| `review` | Validated candidate awaiting the required human or policy decision | Do not place in the active Mem0 generation |
| `canonical` | Accepted durable record in AFFiNE | Index only when classification permits |
| `superseded` | Retained canonical history replaced by an explicitly linked canonical record | Exclude by default; allow historical search |
| `tombstoned` | Content intentionally withdrawn under authorized deletion or retention policy | Remove content from active search; retain only permitted tombstone metadata |

### Review and promotion rules

1. A candidate needs a stable ID, provenance, classification, content hash, and type-valid minimum fields before `review`.
2. Deduplication and conflict checks compare current AFFiNE revisions, not only Mem0 excerpts.
3. `candidate` to `review` may be automated when validation succeeds.
4. `review` to `canonical` requires an attributable reviewer or a narrowly defined, tested promotion policy for that change class.
5. Contradictions, sensitive material, deletion, major decision changes, and supersession require explicit review.
6. Promotion records reviewer or policy ID, decision time, source revision, and idempotency key.
7. Canonical mutation uses an expected revision, fails when stale, and never silently overwrites concurrent edits.
8. Supersession and tombstoning are governed separately; neither follows from omission, age, low retrieval score, or PARA Archive.

## Canonical record envelope

This logical schema does not prescribe AFFiNE API operations or physical columns.

```yaml
schema: asgard.mimir-record.v1
record_id: "rec_01JEXAMPLEDECISION"
schema_version: 1
type: decision
title: "Use deterministic Mimir index generations"
summary: "Rebuild Mem0 from accepted AFFiNE revisions."
primary_context:
  kind: project
  record_id: "ctx_project_mimir"
context_refs:
  - kind: project
    record_id: "ctx_project_mimir"
  - kind: area
    record_id: "ctx_area_knowledge-operations"
lifecycle:
  status: canonical
  promoted_at: "2026-07-27T10:30:00Z"
  promoted_by: "principal:owner"
  policy_ref: "policy:knowledge-review-v1"
classification: private
provenance:
  - source_ref: "src_conversation_01JEXAMPLE"
    source_revision: "manifest:42"
    asserted_by: "principal:owner"
    observed_at: "2026-07-27T09:55:00Z"
    extraction_ref: "muninn:candidate:sha256:example"
typed_fields:
  decision: "Use generation-based deterministic AFFiNE-to-Mem0 indexing."
  rationale: "It permits validation and complete reconstruction."
  decided_at: "2026-07-27T09:55:00Z"
  decision_status: adopted
  decision_maker_refs:
    - "person:owner"
relations:
  - type: decided_in
    target_ref: "meeting:index-design-review"
  - type: supports
    target_ref: "concept:affine-canonical-authority"
  - type: related_to
    target_ref: "procedure:mem0-rebuild"
tags:
  - mimir
  - indexing
temporal:
  valid_from: "2026-07-27T09:55:00Z"
  valid_to: null
timestamps:
  created_at: "2026-07-27T10:00:00Z"
  updated_at: "2026-07-27T10:30:00Z"
review:
  next_review_at: "2027-01-27T00:00:00Z"
  last_reviewed_at: "2026-07-27T10:30:00Z"
  review_reason: "architecture decision"
supersession:
  supersedes_refs: []
  superseded_by_ref: null
content_hash: "sha256:<canonical-normalized-content>"
idempotency_key: "mimir:manifest-42:decision-7"
```

`record_id` is stable across title, PARA, and presentation changes.
`schema_version` identifies the envelope version. AFFiNE page ID and revision
are storage mappings and must not be reconstructed from a title.

## Controlled relationships

Relationships are directed, typed edges between stable IDs:

| Relation | Meaning |
| --- | --- |
| `belongs_to` | Record is governed or contained by the target context/entity |
| `about` | Record's primary subject is the target |
| `supports` | Record supplies compatible reasoning or evidence |
| `contradicts` | Record materially conflicts with the target |
| `decided_in` | Decision was made in the target meeting or event |
| `owner_of` | Person or organization is accountable for the target |
| `fulfills` | Record or action satisfies the target commitment |
| `derived_from` | Record was transformed or extracted from the target source |
| `supersedes` | Canonical record explicitly replaces the target |
| `related_to` | Relevant association with no stronger defined relation |

Use the strongest accurate relation. `related_to` is a fallback. Targets use
stable record, context, source, or principal IDs; titles and paths are labels.

## Integrity and governance rules

### Conflicts and duplication

- Exact replay is detected by idempotency key and source reference.
- Content hashes detect normalized duplicates; semantic similarity finds near-duplicates but does not authorize merging.
- Duplicate candidates converge on one review item while retaining every provenance edge.
- Compatible claims may use `supports`; material disagreement uses `contradicts` and remains visible until reviewed.
- Replacement requires reciprocal supersession metadata in one governed change.

### Provenance, classification, and time

- Every candidate names a source reference, revision, observation time, and asserting principal when known.
- Transformations append provenance; they do not replace the original chain.
- Classification uses `general`, `private`, `sensitive`, or `restricted` as defined in [Security](security.md#data-classification).
- Restricted material never enters AFFiNE, Mem0, prompts, chat, or telemetry; rejection audits must not reproduce it.
- Derived summaries, chunks, embeddings, locators, and metadata inherit the highest applicable classification unless approved declassification proves otherwise.
- Time-sensitive claims use `valid_from` and `valid_to`; `observed_at` does not assert that a claim remains true.

### Preferences and reconfirmation

- A preference records whether its basis is `stated`, `observed`, or `inferred`.
- Confidence is a bounded value or controlled label defined by the deployment.
- Inferred preferences start below stated preferences and cannot override them without review.
- Material preferences need `last_confirmed_at` and an impact-based review interval. Expiry triggers reconfirmation and policy-defined lower reliance, not deletion.

### Deletion, tombstones, and idempotency

- Deletion requires explicit owner or retention-policy authority and an attributable audit event.
- Tombstones retain only permitted identity, reason, time, authority, and supersession references; policy removes sensitive content.
- The indexer removes tombstoned content and forbidden metadata from the next active Mem0 generation.
- Reusing an idempotency key with different content conflicts; identical content returns the prior result.
- Derive candidate IDs from immutable source and manifest references where available.

## AFFiNE canonical mapping

The logical record maps to a canonical AFFiNE page. Its body holds the full
meaning; database properties, relations, and tags (or equivalents) hold
queryable envelope fields. Reviewers must see provenance and governance.

Implement PARA as views, collections, or equivalent navigation over
`context_refs` and context state. Folder or view is not authority and does not
determine type or lifecycle.

Asgard does not invent an AFFiNE API, MCP endpoint, property primitive, or
revision behavior. The mapping must pin the AFFiNE release and connector,
document operations, and validate IDs, revisions, relations, attribution,
optimistic concurrency, and idempotency before writes are enabled.

## Mem0 projection

The controlled indexer reads only permitted accepted AFFiNE revisions,
normalizes them without changing meaning, and emits deterministic chunks. Each
chunk carries safe metadata sufficient to resolve and validate its source:

- logical `record_id` and record `type`;
- AFFiNE workspace/page ID and exact source revision;
- deterministic chunk ID and content hash;
- permitted context references;
- lifecycle status and classification;
- indexing timestamp and index generation;
- pinned normalizer and chunker versions where needed for reconstruction.

Only `canonical` content enters normal active retrieval. Superseded content may
enter a separately filtered historical mode; candidates, review drafts, and
tombstoned content do not. The indexer must omit any data outside the index
identity's permitted classifications. Mem0 namespaces and relevance scores are
not authorization.

Generation validation checks counts, hashes, classifications, source
references, and representative queries before activation. Failure leaves the
current generation untouched. Mem0 can be erased and rebuilt from AFFiNE; when
the two disagree, AFFiNE wins.

## Creation and review flow

1. Ody identifies durable owner-provided material, Muninn reviews eligible
   conversation exports, or Huginn stages external evidence.
2. Huginn retains untrusted captures and provenance only; it cannot write
   canonical knowledge.
3. Ody or Muninn submits a provenance-bearing candidate through Heimdall using
   its authenticated workload identity and an idempotency key.
4. Heimdall enforces caller, classification, connector, policy, expected
   revision, and attribution before the selected AFFiNE connector creates or
   updates a review draft.
5. Muninn compares the candidate with Mem0 references, then reads the relevant
   canonical AFFiNE revisions to classify duplicates, support, contradiction,
   or proposed change.
6. A reviewer or explicitly approved low-risk policy promotes a valid review
   record. Major, contradictory, sensitive, destructive, and superseding
   changes require explicit review.
7. AFFiNE records the accepted canonical revision and audit identity.
8. The controlled indexer projects that permitted revision into a staged Mem0
   generation, validates it, and only then activates it.

## Worked decision example

`decision:index-generations` is a canonical `decision` whose primary context is
`project:mimir-rebuild` and whose additional context is
`area:knowledge-operations`. Its provenance points to
`meeting:index-design-review` and the immutable conversation manifest from
which Muninn prepared the candidate. Moving the Project to PARA Archive leaves
the decision canonical and linked to the active Area.

Later, `decision:incremental-index-contract-v2` may replace it. After explicit
review, the new canonical record has
`supersedes -> decision:index-generations`; the old record becomes
`superseded` with `superseded_by_ref` pointing back. Both retain provenance.
Normal search returns the new decision, while authorized historical retrieval
can resolve the old one. Neither record is deleted or made noncanonical merely
because the Project was archived.

## Validation checklist

- [ ] PARA kind, record type, and lifecycle can change independently.
- [ ] Multi-context records preserve an optional, valid primary context.
- [ ] Every type rejects records missing its minimum fields.
- [ ] Candidate promotion preserves provenance, reviewer, policy, and revision.
- [ ] Contradictions, supersession, and tombstones require explicit review.
- [ ] Archive changes navigation only and never implies deletion.
- [ ] Stable IDs resolve despite title, page, and view changes.
- [ ] Classification filters canonical reads and every Mem0 projection.
- [ ] Restricted material is rejected before AFFiNE or Mem0 persistence.
- [ ] Replayed inputs are idempotent and mismatched replays fail.
- [ ] Mem0 chunks resolve to the exact AFFiNE page and revision.
- [ ] Two clean rebuilds produce matching deterministic manifests.
- [ ] An empty Mem0 can be rebuilt solely from canonical permitted sources.
- [ ] Connector attribution and optimistic concurrency pass for the pinned
      AFFiNE deployment before writes are enabled.

## Related design

- [Mimir role](gods/mimir.md)
- [Mimir authority model](architecture.md#mimir-authority-model)
- [Mimir search](integration-contracts.md#4-mimir-search)
- [Data flows](data-flows.md)
- [Security](security.md)
