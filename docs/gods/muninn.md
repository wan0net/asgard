# Muninn

![Muninn portrait](../assets/avatars/muninn.png)

Muninn is Asgard's isolated, scheduled, non-interactive Hermes worker for
conversation-derived knowledge curation. It reviews completed conversation
windows from durable checkpoints and prepares traceable knowledge candidates.
This is a reference design: its transcript bridge, schedules, and write path
remain gated until their validation requirements pass.

## At a glance

| Aspect | Description |
| --- | --- |
| Function | Review durable conversation windows, reconcile material with knowledge, and prepare curated candidates or drafts. |
| Reference tool(s) | Scheduled, isolated Hermes worker; Heimdall-mediated AFFiNE and Mem0 operations. |
| Authority | May request permitted reads and create policy-allowed provenance-bearing candidates or drafts; AFFiNE remains canonical. |
| Trust zone | Isolated Muninn runtime in the assistant trust zone; tool actions cross into Heimdall. |

## What Muninn does

**Asgard policy:** Muninn processes only durable, ordered conversation windows
made available through the checkpointed handoff. It extracts durable material,
such as explicit decisions, corrections, enduring preferences, commitments,
open questions, and architecture changes. It searches the rebuildable Mem0
index to find related material, then reads relevant canonical AFFiNE pages
before classifying each candidate as new, supporting, duplicate, update,
contradiction, temporary, or sensitive.

For material worth retaining, Muninn creates a review-inbox item or draft with
its source-window and canonical-revision provenance. Candidate and draft
creation must be idempotent: a replay of the same immutable input must not
produce a second knowledge change.

## How Muninn interacts

- **Transcript outbox:** Muninn receives the exact next minimized conversation
  window through Heimdall's authenticated handoff, with a bounded lease and
  durable checkpoint. It does not read Hermes state, databases, or workspaces
  directly.
- **Heimdall:** Every tool request goes through Heimdall using Muninn's distinct
  workload identity. Heimdall derives that identity, applies policy, and
  selects the scoped downstream connection; Muninn cannot select credentials.
- **Mimir:** Mem0 assists reconciliation, but AFFiNE is authoritative. Muninn
  writes only policy-allowed drafts or candidates through Heimdall.

## What Muninn does not do

Muninn is not a user-facing assistant and does not run interactive work. It
does not silently promote, overwrite, or delete canonical knowledge, nor infer
a deletion from a conversation omitting an older fact. It does not bypass
Heimdall, receive raw credentials, or treat Mem0 as canonical authority.

## Validation

**Validation required:** Keep Muninn schedules and its transcript path disabled
until the applicable manual canaries pass. Demonstrate isolated profile,
checkpoint, and connector identity; Heimdall-only access; ordered lease and
compare-and-swap checkpoint behavior; and idempotent replay. Missing evidence,
invalid provenance, failed validation, unavailable handoff, or failed draft
persistence must fail closed and leave the checkpoint unchanged.

## See also

- [Architecture](../architecture.md)
- [Tools, capabilities, and interaction boundaries](../tooling.md)
- [Data flows](../data-flows.md)
- [Integration contracts](../integration-contracts.md)
- [Hermes-to-Muninn transcript outbox](../transcript-outbox.md)
