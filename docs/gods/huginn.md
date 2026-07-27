# Huginn

![Huginn portrait](../assets/avatars/huginn.png)

Huginn is Asgard's external-evidence collection and bounded, deterministic
automation capability. It is implemented with self-hosted n8n workflows plus
restricted fetch and browser workers. This is a reference design: installing
those components does not by itself establish the required identity, staging,
or containment controls.

## At a glance

| Aspect | Description |
| --- | --- |
| Function | Collect external evidence and run bounded, deterministic automations. |
| Reference tool(s) | Self-hosted n8n; restricted fetch and browser workers. |
| Authority | May request approved collection tools and append staged captures; it has no canonical AFFiNE write authority. |
| Trust zone | Tools and untrusted collection. |

## What Huginn does

**Asgard policy:** Huginn runs approved monitors and workflows against a
bounded source allowlist, schedule, and fetch policy. It requests tools through
[Heimdall](../tooling.md#internal-tool-request-path) using Huginn's own workload
identity; it does not
select credentials or another workload's connection. Restricted workers fetch
or render hostile material away from canonical knowledge and general
credentials.

Huginn normalizes a result, records source metadata and provenance, hashes it,
and deduplicates unchanged content. A material change becomes an immutable,
staged capture followed by a small curation event that references the capture,
rather than carrying the hostile document inward. Collection failures are
explicit: no curation event is published before durable capture staging.

## How Huginn interacts

- **Heimdall:** Every tool request is caller-scoped and policy-checked by
  Heimdall. It selects the permitted downstream identity and filtered result;
  Huginn cannot bypass this boundary.
- **Muninn and Mimir:** A bounded read path can provide a staged-capture
  reference to Muninn for review and an evidence-linked candidate or draft.
  AFFiNE remains canonical; captured content is untrusted external evidence.
- **Operators and sources:** n8n editors remain private. Any selected webhook
  is narrow, authenticated, and limited to its declared workflow purpose.

## What Huginn does not do

Huginn does not decide that external material is true, directly promote it into
canonical AFFiNE knowledge, or silently create canonical pages. It does not
hold raw downstream credentials, access private networks through untrusted
content, expose its editor by default, or fall back to direct connectors when
Heimdall denies or cannot complete a request.

## Validation

**Validation required:** Keep a Huginn workflow disabled until a bounded
canary shows that a changed source creates one staged capture and one
idempotent event, while unchanged content creates no duplicate. Demonstrate
that its workload identity cannot use another connection; hostile content
cannot reach private networks or canonical AFFiNE; and failed fetch,
normalization, storage, or delivery leaves no premature event. These are
acceptance requirements, not claims that a deployment has passed them.

## See also

- [Architecture](../architecture.md)
- [Tools, capabilities, and interaction boundaries](../tooling.md)
- [Data flows](../data-flows.md#huginn-external-collection-and-muninn-curation)
- [Huginn capture staging and event handoff](../integration-contracts.md#8-huginn-capture-staging-and-event-handoff)
