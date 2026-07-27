# Odine (Ody)

![Odine (Ody) portrait](../assets/avatars/odine.png)

Odine, or Ody, is Asgard's only user-facing assistant. The role is implemented
by Hermes Agent and its interfaces. Ody handles conversation, reasoning, and
orchestration without exposing internal agents to the user.
This is a reference-design role, not evidence that any deployment has enabled
every interface or capability.

## At a glance

| Aspect | Description |
| --- | --- |
| Function | The single conversational assistant; reasons about requests and coordinates bounded work. |
| Reference tool(s) | Hermes Agent and its interfaces. |
| Authority | May request permitted capabilities; it does not directly authorize or execute external actions. |
| Trust zone | Assistant runtime. |

## What Odine does

**Asgard policy:** Ody receives authenticated, normalized user requests and
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

## Validation before enabling sensitive capabilities

**Validation required:** Before enabling sensitive capabilities, demonstrate
that channel identity and conversation isolation are preserved; Ody cannot
directly reach downstream services; requests cannot select another workload's
connection; credentials are absent from Ody's context and logs; and denied,
expired, or changed approvals have no effect. Also test canonical reads after
Mem0 ranking, rebuild Mem0 from AFFiNE, and verify that failures do not fall
back to a broader identity or permission.

## See also

- [Architecture](../architecture.md)
- [Tools, capabilities, and interaction boundaries](../tooling.md)
- [Data flows](../data-flows.md)
- [Integration contracts](../integration-contracts.md)
- [Security model](../security.md)
