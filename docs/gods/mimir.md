# Mimir

![Mimir portrait](../assets/avatars/mimir.png)

Mimir is Asgard's knowledge capability. It keeps durable knowledge
human-readable and makes it retrievable without treating a search result as
authority. This is a reference design: the required adapters and controls must
be validated before a deployment relies on them.

## At a glance

| Property | Description |
| --- | --- |
| Function | Canonical knowledge and retrieval |
| Reference tool(s) | AFFiNE and Mem0 |
| Authority | AFFiNE is the authoritative canonical record; Mem0 has no independent authority |
| Trust zone | Trusted knowledge |

## What Mimir does

AFFiNE holds accepted, human-readable knowledge, including its canonical
revisions. Mem0 is a disposable semantic index derived from accepted AFFiNE
revisions by a controlled indexer. The index improves retrieval and can be
erased and rebuilt from canonical content; it is not a second source of truth.

For an important claim, Ody first retrieves candidate references from Mem0 and
then reads the corresponding canonical AFFiNE content. If AFFiNE and Mem0
disagree, AFFiNE wins. This retrieval flow and the source metadata expected of
the index are described in the [architecture](../architecture.md#mimir-authority-model)
and [Mimir search contract](../integration-contracts.md#4-mimir-search).

## How Mimir interacts

Ody requests Mimir operations through [Heimdall](heimdall.md), which applies
the caller, classification, and tool policy before a permitted search or
canonical read. Mem0 returns references and relevance, while AFFiNE supplies
the canonical content used in material answers.

[Muninn](muninn.md) reviews durable conversation material and proposes
provenance-bearing drafts or changes through Heimdall. [Huginn](huginn.md)
collects external evidence but cannot directly promote that material into
canonical knowledge. A controlled indexer updates Mem0 only from accepted
AFFiNE revisions.

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
- [Tools, capabilities, and interaction boundaries](../tooling.md)
- [Data flows](../data-flows.md#user-question-and-knowledge-retrieval)
- [Integration contracts](../integration-contracts.md#4-mimir-search)
