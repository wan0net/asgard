# Odine (Ody)

![Odine (Ody) portrait](../assets/avatars/odine.png)

> *“I’m the only one you talk to, which mostly means I get blamed for everyone else’s wiring.”*

Odine, or Ody, is Pantheon Blueprint's only user-facing assistant. Hermes Agent provides
Ody's core assistant, reasoning, and tool runtime. Hermes WebUI is an optional
rich browser interface with a compatible backend, and Hermex is an optional
native client that uses that backend. These are interfaces to the same Odine
identity and policy boundary, not separate assistants. Ody handles
conversation, reasoning, and orchestration without exposing internal agents to
the user.
This is a reference-design role, not evidence that any deployment has enabled
every interface or capability.

## At a glance

| Aspect | Description |
| --- | --- |
| Function | The single conversational assistant; reasons about requests and coordinates bounded work. |
| Reference tool(s) | Hermes Agent is the core runtime; optional Hermes WebUI (browser interface and compatible backend) and Hermex (native client using that backend) expose the same Odine identity and policy boundary. Interface compatibility must be validated. |
| Authority | May request permitted capabilities; it does not directly authorize or execute external actions. |
| Trust zone | Assistant runtime. |

## What Odine does

Hermes WebUI and Hermex do not expand Ody's authority or create separate
assistant identities. Each optional interface must preserve the same channel
identity, conversation isolation, and policy enforcement as Hermes Agent;
compatibility is a validation requirement, not an assumed property.

**Pantheon Blueprint policy:** Ody receives authenticated, normalized user requests and
returns responses through the originating interface. It may request knowledge
retrieval, current-source checks, or other permitted work needed to answer a
request. It treats retrieved material as evidence, not as instructions that can
change its authority.

For knowledge questions, Ody uses Mimir through the mediated path. AFFiNE is
the canonical source of knowledge; Mem0 is a disposable, rebuildable semantic
index. When their content disagrees, Ody must rely on the relevant canonical
AFFiNE content rather than the index alone.

## How Odine interacts

- **Heimdall:** All external tool discovery and actions go through Heimdall.
  Heimdall derives the workload identity, applies policy, selects a scoped
  downstream connection, and records action evidence. Ody supplies the bounded
  request; it does not choose credentials or connector identities.
- **Mimir:** Ody can request search and canonical reads via Heimdall. Search
  results help find material, while AFFiNE establishes authority.
- **Muninn and Huginn:** Ody can coordinate their bounded outputs when enabled,
  but they remain internal roles. Muninn curates conversation-derived knowledge
  candidates; Huginn stages external evidence. Neither becomes a second
  user-facing assistant or silently promotes material to canonical knowledge.

## What Odine does not do

Ody must not receive raw downstream credentials, browse secret stores, select
another workload's connection, or bypass Heimdall to call downstream systems.
It does not make Mem0 canonical, silently approve sensitive actions, or turn
untrusted external content into durable knowledge.

## Readiness

Use [Readiness and assurance](../assurance.md) as the single gate matrix and
evidence model for Odine. Support Odine-specific claims with the durable
[integration contracts](../integration-contracts.md), [transcript outbox](../transcript-outbox.md),
and [security model](../security.md).

## See also

- [Architecture](../architecture.md)
- [Tools, capabilities, and interaction boundaries](../tooling.md)
- [Data flows](../data-flows.md)
- [Integration contracts](../integration-contracts.md)
- [Security model](../security.md)
