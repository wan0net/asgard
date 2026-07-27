# Mimir

![Mimir portrait](../assets/avatars/mimir.png)

Mimir is Asgard's architectural knowledge role, not a chatbot or single
product. It closes two distinct gaps: AFFiNE keeps accepted durable knowledge
human-readable as the canonical record, while Mem0 provides semantic retrieval
from a disposable index without making search results authoritative. A
controlled indexer derives Mem0 entries only from accepted AFFiNE revisions.
This is a reference design: the required adapters and controls must be
validated before a deployment relies on them.

## At a glance

| Property | Description |
| --- | --- |
| Function | One knowledge role: human-readable canonical knowledge plus semantic retrieval |
| Reference tool(s) | AFFiNE fills the canonical-record gap; controlled indexing derives Mem0, which fills the semantic-retrieval gap |
| Authority | AFFiNE is the authoritative canonical record; Mem0 is disposable, rebuildable, and has no independent authority |
| Trust zone | Trusted knowledge |

## What Mimir does

AFFiNE holds accepted, human-readable knowledge, including its canonical
revisions. The controlled indexer derives Mem0 entries only from those accepted
revisions. Mem0 is therefore a disposable semantic retrieval index: it helps
find relevant material and can be erased and rebuilt from canonical content,
but it is not a second source of truth.

Mimir organizes canonical knowledge with a hybrid [Mimir knowledge
model](../mimir-knowledge-model.md): a Capacities-inspired conventional object
model starts with exactly seven primary types: Project, Area,
Person/Organisation, Topic, Decision, Source, and Procedure. PARA-like
dashboards are navigation views rather than exclusive folders. Canonical entity
pages pair GBrain-style rewritable current understanding and state with an
append-only evidence timeline, while LLMWiki-style synthesis is used only for
research ingestion.

For an important claim, Ody first retrieves candidate references from Mem0 and
then reads the corresponding canonical AFFiNE content. If AFFiNE and Mem0
disagree, AFFiNE wins. This retrieval flow and the source metadata expected of
the index are described in the [architecture](../architecture.md#mimir-authority-model)
and [Mimir search contract](../integration-contracts.md#4-mimir-search).

## How Mimir interacts

Ody requests Mimir operations through [Heimdall](heimdall.md), which applies
the caller, classification, and tool policy before a permitted search or
canonical read. Mem0 returns references and relevance, while AFFiNE supplies
the canonical content used in material answers; Heimdall mediates access to
both rather than making either component an autonomous agent.

[Muninn](muninn.md) reviews durable conversation material and proposes
provenance-bearing candidates or drafts through Heimdall; acceptance remains
subject to the applicable review policy before AFFiNE becomes canonical.
[Huginn](huginn.md) only stages untrusted external evidence and cannot directly
promote that material into canonical knowledge. Once a revision is accepted in
AFFiNE, the controlled indexer may update Mem0 from it; neither Muninn nor
Huginn writes directly to the retrieval index as an authority source.

## What Mimir does not do

Mimir does not treat indexed excerpts, relevance scores, or external captures
as canonical facts. It does not let Mem0 authorize AFFiNE writes, and it does
not let agents bypass Heimdall for general knowledge operations. It also does
not silently replace, delete, or supersede canonical knowledge; those changes
require the applicable review or retention policy.

## Validation

Before enabling a dependent capability, a deployment must demonstrate that
unauthorized classifications are omitted from search results, each result
resolves to its indexed AFFiNE page and revision, and an empty Mem0 index can
be rebuilt solely from canonical sources. AFFiNE writes remain blocked until
downstream identity and attribution validation passes. These are validation
requirements, not claims about an installed product.

## See also

- [Architecture](../architecture.md#mimir-authority-model)
- [Mimir knowledge model](../mimir-knowledge-model.md)
- [Tools, capabilities, and interaction boundaries](../tooling.md)
- [Data flows](../data-flows.md#user-question-and-knowledge-retrieval)
- [Integration contracts](../integration-contracts.md#4-mimir-search)
