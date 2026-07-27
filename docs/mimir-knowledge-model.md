# Mimir knowledge model

This page defines the reference knowledge model for Mimir. AFFiNE is the
canonical, human-readable source of truth. A controlled indexer projects
permitted content into disposable, rebuildable Mem0 semantic retrieval.

This page is the shared public conceptual and contract model. Deployment-specific
identities, hostnames, credentials, connector versions, runtime status, and
operational evidence belong only in the private `pantheon-private` operations
repository.

This reference design is not a claim that an integration is operational.
Deployments must pin and validate their AFFiNE and Mem0 integrations before use;
unsupported behavior must not be advertised.

## Hybrid design

Mimir combines four specific patterns:

- a **Capacities-inspired conventional object model inside AFFiNE**, implemented
  with templates, tags, properties, links, and saved collections;
- a **PARA-like human navigation shell** for approachable work-oriented entry
  points;
- a **GBrain-style entity page**, with rewritable current understanding and
  current state above an append-only, source-backed evidence timeline; and
- **LLMWiki-style research ingestion only**, where collected Sources are
  synthesized into cited Topic pages.

These patterns have limited roles. PARA-like views are not exclusive folders,
and LLMWiki-style folder organization does not structure the knowledge base.
AFFiNE remains the implementation and authority.

## Human-facing navigation

The human-facing front door is a small set of AFFiNE dashboards or saved collections:

```text
Mimir
├── Home
├── Inbox
├── Projects
├── Areas
├── People & Organisations
├── Knowledge
├── Decisions & Procedures
├── Sources
├── Archive
└── System
```

These are navigation views, not exclusive folders or ownership containers. One
page can appear in Projects, Recent decisions, a person's related work, and
Recent changes without duplication or movement between folders.

Home presents the most useful current views and search entry points. Inbox is
the staging and triage surface for new knowledge, contradictions, and material
awaiting review.

## Canonical object model

AFFiNE does not become a native typed-object database by declaration. Types are
conventions implemented with templates, tags, supported properties, linked
pages, and saved collections. Backlinks and ordinary AFFiNE links are the
portable relationship baseline; stronger behavior requires validation.

Mimir starts with exactly seven conventional primary types:

| Primary type | Purpose |
| --- | --- |
| **Project** | A goal-oriented effort with an outcome, status, scope, participants, related decisions, and next actions |
| **Area** | An ongoing responsibility or domain without a defined completion point |
| **Person/Organisation** | Current relationship context, roles, interactions, related work, and open loops |
| **Topic** | The current accepted understanding of a subject, supported by cited sources |
| **Decision** | A decision, rationale, status, evidence, consequences, and supersession history |
| **Source** | An attributable input such as a document, conversation, email, meeting, or external capture |
| **Procedure** | Repeatable instructions with prerequisites, ordered steps, validation, and recovery guidance |

Meetings, conversations, email, and external captures are `Source` subtypes, not
new primary types. A new primary type requires explicit human review and
approval. Muninn may propose one after repeated observed use, but it cannot
create one autonomously. This constraint prevents taxonomy sprawl.

### Type templates

Each primary type has a concise set of expected sections:

| Type | Expected type-specific sections |
| --- | --- |
| Project | Outcome and scope; current status; next actions; participants; related decisions; milestones |
| Area | Purpose and standards; current health; responsibilities; active projects; recurring reviews |
| Person/Organisation | Relationship and roles; current context; interactions; related projects/topics; open loops |
| Topic | Current understanding; key claims; related concepts; open questions; cited evidence |
| Decision | Decision and status; rationale; alternatives; consequences; evidence; supersedes/superseded by |
| Source | Origin and author; captured/published dates; source location; summary; extracted claims; processing state |
| Procedure | Purpose; prerequisites; ordered steps; validation; rollback/recovery; owner and review date |

### GBrain entity page pattern

Canonical entity pages follow this structure:

```text
# Entity title

## Current understanding
The concise, rewritable, currently accepted view, with provenance.

## Current state
Status, ownership, risks, and pending work.

## Relationships
Linked projects, areas, people, organisations, topics, decisions, procedures,
and sources.

## Open questions
Unknowns, conflicts, and items requiring investigation or review.

## Evidence timeline
Append-only, dated, source-backed observations and changes.
```

The top sections are concise and rewritable. Together they present the current
accepted view and must identify its provenance. The Evidence timeline is not
canonical truth by itself: it preserves dated, source-backed observations,
including evidence later contradicted or superseded.

Muninn reconciles new evidence into the current understanding and current state
without erasing evidence history. For research ingestion, collected Sources are
synthesized into cited Topic pages; new evidence updates or reconciles an
existing Topic rather than creating an unrelated research-folder hierarchy.

## Common properties

Every canonical object has this common logical property baseline:

```yaml
type: Project | Area | Person/Organisation | Topic | Decision | Source | Procedure
status:
owner:
sensitivity: general | private | sensitive
canonical_state: candidate | canonical | superseded | archived
review_state: unreviewed | reviewed | needs-review | contradictory
created_at:
updated_at:
reviewed_at:
review_due:
related_projects: []
related_areas: []
related_people_organisations: []
related_topics: []
source_ids: []
provenance: []
supersedes: []
superseded_by: []
```

Type-specific properties may extend this baseline. For example, a Decision can
have a decision date and alternatives, while a Source can have an origin URL,
capture timestamp, author, content hash, and subtype.

If the pinned AFFiNE version does not expose every field as a native property,
the logical schema may use a consistent metadata block until a native mapping
is proven. The mapping must not assume an unvalidated property primitive,
relation behavior, or query capability.

## Saved views

The initial saved AFFiNE collections or views are:

- Active projects
- Areas needing attention
- Recent decisions
- People recently mentioned
- Knowledge due for review
- New/untriaged sources
- Recent changes
- Contradictions/Awaiting review

These are filtered views over the conventions, not containers that own pages.
Each proposed filter must be tested against the selected AFFiNE version. Where
a property is not queryable, use a maintained index page rather than claiming
automatic collection membership.

## Search and retrieval

Mimir provides three complementary search modes:

1. **AFFiNE native navigation:** title, tag, database-row, full-body, and
   property search capabilities actually proven in the selected AFFiNE version.
2. **Saved filtered collections:** repeatable operational questions such as
   active projects, recent decisions, or knowledge due for review.
3. **Ask Ody:** semantic answering through
   `Ody -> Heimdall -> Mem0 -> canonical AFFiNE pages`.

For Ask Ody, Mem0 returns candidate references, Heimdall applies authorization,
and Ody resolves relevant results to canonical AFFiNE content before answering
with citations. A similarity match never grants access. If a Mem0 result cannot
be resolved to an authorized canonical page, or is not explicitly labeled as a
transient candidate under an allowed policy, it cannot be presented as accepted
knowledge.

## Mem0 index record

Each indexed object includes metadata equivalent to:

```yaml
memory_id: generated-uuid
source_type: affine_page
source_id: stable-affine-page-id
source_url: https://mimir.pantheon.example.com/...
revision: source-revision-or-hash
classification: private
status: canonical
valid_from:
valid_until:
indexed_at:
content_hash: sha256
chunk_number: 0
index_generation: 2026-07-25T000000Z
```

Canonical AFFiNE chunks are written to Mem0 with `infer=false`. Mem0 stores the
deterministic canonical text without independently extracting or rewriting facts. This uses the raw-memory option in [Mem0's add operation](https://docs.mem0.ai/core-concepts/memory-operations/add).

Inference is allowed only for separately governed transient candidates, in a
separate namespace with its own retention and access policy. It is not used for
canonical chunks. Heimdall applies access controls before results reach Ody;
Mem0 namespaces and similarity scores are not authorization systems.

## Deterministic AFFiNE-to-Mem0 reindexing

1. An AFFiNE page is created, changed, accepted, superseded, or deleted.
2. A checkpointed periodic scanner identifies the page and revision. A native
   change event may optimize this later, but is not assumed.
3. The indexer requests page export through Heimdall.
4. Heimdall authorizes `<MIMIR_INDEXER_IDENTITY>`, the workspace, page, and
   operation.
5. The indexer normalizes content while preserving headings, relationships,
   source metadata, classification, and the canonical page ID.
6. The indexer creates deterministic chunks and content hashes.
7. The index catalogue records page ID, source revision or hash, chunk hashes,
   Mem0 memory IDs, classification, active generation, and status.
8. New chunks are written with `infer=false` into a new index generation
   through Heimdall.
9. Representative queries and count/hash reconciliation validate the new
   generation; the read alias then switches atomically.
10. Old-generation chunks are retired by their recorded memory IDs only after
    the switch. A shared or global Mem0 reset is prohibited.
11. Index status, revision, timestamp, generation, and any error are recorded.
12. A failed reindex leaves AFFiNE authoritative and generates an alert. It
    does not roll back an accepted canonical change.

A deterministic source key can follow:

```text
affine:{workspace_id}:{page_id}:{revision}:{chunk_number}
```

Generation activation is blue-green: validation failure leaves the current
read generation untouched. Mem0 can be erased and rebuilt from permitted
canonical AFFiNE pages and retained source records. When AFFiNE and Mem0
disagree, AFFiNE wins.

## Bootstrap and controlled evolution

Bootstrap Mimir with only:

- Home and Inbox;
- the seven primary object types and their concise templates;
- the common property baseline;
- a handful of the highest-value saved collections; and
- native AFFiNE search plus the first Ask Ody retrieval path.

Do not prebuild a deep folder tree, ontology, or large tag vocabulary. Observe
real use first. Muninn may then propose new properties, relationships, saved
views, Source subtypes, or, only when the existing model repeatedly fails, a
new primary type. Changes that expand the primary taxonomy require explicit
human review and approval.

## Related design

- [Mimir role](gods/mimir.md)
- [Mimir authority model](architecture.md#mimir-authority-model)
- [Mimir search contract](integration-contracts.md#4-mimir-search)
- [Data flows](data-flows.md)
- [Readiness and assurance](assurance.md)
- [Security model](security.md)
