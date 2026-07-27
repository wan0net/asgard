# Integration contracts

Asgard is an architecture assembled from upstream products and a small set of
required adapters, policies, and durable workflows.

> No supplied upstream component automatically provides the complete Asgard
> wiring.

Installing Hermes, Executor, AFFiNE, Mem0, and n8n does not by itself create the
identity, authority, provenance, approval, indexing, update, or audit behavior
described in the architecture. The base installation must keep each dependent
capability disabled until its contract in this document is implemented and its
acceptance test passes.

This document defines logical operations. Names such as `mimir.search` are
Asgard contract names, not claims that an upstream product exposes an endpoint
with that name.

## Classification

Each integration is classified as one of:

| Classification | Meaning |
| --- | --- |
| **Upstream-supported** | The pinned upstream product documents the underlying capability. Asgard still configures and constrains it. |
| **Asgard custom adapter/policy** | Asgard must supply glue, a wrapper, a schema, policy, or durable workflow. |
| **Optional/experimental** | Useful, but not required for the secure base system and not enabled by default. |
| **Blocked pending validation** | Keep the dependent capability off until behavior is proven against the pinned release. |

One contract may use an upstream-supported substrate while still requiring an
Asgard adapter.

## Contract inventory

| Contract | Upstream substrate | Asgard classification | Default enablement |
| --- | --- | --- | --- |
| Channel normalization | Hermes messaging gateway and sessions | Upstream-supported substrate + custom policy | Read-only interfaces after identity tests |
| Workload authentication to Heimdall | Executor MCP endpoint and connection catalogue | Custom adapter; shared-caller multiplexing blocked pending validation | Separate workload endpoints only |
| Per-agent Executor separation | Multiple deployable Executor processes/instances | Asgard security baseline | Required until multiplexing passes |
| Mimir search | Mem0 search capability | Custom adapter | Read-only after classification tests |
| Canonical AFFiNE read/write | Version-pinned AFFiNE connector selected by the deployer | Custom adapter; writes blocked pending identity validation | Reads first; writes off |
| AFFiNE-to-Mem0 indexing | AFFiNE export/connector + Mem0 storage/search | Custom adapter | Off until full rebuild passes |
| Conversation completion and Muninn checkpoints | Hermes session persistence, API, and export | Upstream-supported export + custom completion/checkpoint adapter | Manual runs first |
| Huginn capture handoff | n8n workflows, webhooks, and task nodes | Custom workflow contract | One unauthenticated read-only source first |
| Durable approval and channel resume | Executor policy substrate + Hermes delivery surfaces | Custom service; blocked pending end-to-end validation | High-risk tools off |
| Ody update broker | Hermes update surface and deployment controller | Custom privileged broker | Off until rollback test passes |
| Audit record sink | Product logs and Grafana-compatible telemetry | Custom security record path | Local append first; remote redacted copy |

## Common conventions

### Envelopes

All requests crossing a trust boundary use a versioned envelope:

```json
{
  "schema": "asgard.request.v1",
  "request_id": "<opaque-request-id>",
  "task_id": "<opaque-task-id>",
  "occurred_at": "<rfc3339-timestamp>",
  "caller": {
    "workload": "<derived-workload-id>",
    "user": "<derived-user-id>"
  },
  "purpose": "<bounded-purpose>",
  "classification": "private",
  "payload": {}
}
```

`caller` is populated by trusted ingress or transport authentication. The model
must not be able to override it.

### Errors

Adapters return stable error classes without leaking credentials or private
content:

```json
{
  "schema": "asgard.error.v1",
  "request_id": "<opaque-request-id>",
  "code": "policy_denied",
  "retryable": false,
  "safe_message": "<human-safe-summary>",
  "detail_reference": "<private-audit-reference>"
}
```

Suggested codes include:

- `authentication_failed`
- `policy_denied`
- `approval_required`
- `approval_expired`
- `connector_unavailable`
- `upstream_version_unsupported`
- `classification_denied`
- `conflict`
- `validation_failed`
- `rate_limited`
- `internal_error`

### Idempotency

Externally visible writes, draft creation, capture storage, approval
consumption, indexing, and update requests need idempotency keys derived from
stable source identifiers and normalized intent. A retry must not create a
second action.

### Version pins

The private deployment manifest records:

```yaml
components:
  hermes: "<pinned-version-or-digest>"
  executor: "<pinned-version-or-digest>"
  affine: "<pinned-version-or-digest>"
  mem0: "<pinned-version-or-digest>"
  n8n: "<pinned-version-or-digest>"
contracts:
  channel_normalization: "v1"
  workload_authentication: "v1"
  mimir_search: "v1"
  knowledge_write: "v1"
  approval: "v1"
```

Revalidate affected contracts before promoting a component or contract version.

## 1. Channel normalization

Hermes documents a unified messaging gateway, persisted sessions, and multiple
channel sources. Asgard adds a normalized owner and reply-route contract.

**Classification:** Upstream-supported substrate + Asgard custom policy.

| Property | Contract |
| --- | --- |
| Inputs | Authenticated browser/Hermex request, Signal event, scoped email event, or AFFiNE AI proxy request |
| Outputs | Normalized channel envelope delivered to the correct Ody profile and conversation |
| Authority | The channel adapter authenticates or maps the sender; Ody cannot choose its own owner or reply route |
| Persistence | Hermes session plus a minimal channel-routing record; raw channel credentials remain outside the session |
| Failure behavior | Reject unknown senders, ambiguous shared-room identity, malformed attachments, and unavailable reply routes; never merge into a different owner's session |
| Acceptance test | The same owner reaches Ody on each enabled interface; another sender cannot inherit history; replies return only to the originating route |

Example:

```yaml
schema: asgard.channel-message.v1
message_id: "<opaque-message-id>"
owner_id: "<derived-owner-id>"
channel: "signal"
channel_session: "<opaque-channel-session>"
ody_session: "<opaque-hermes-session>"
received_at: "<rfc3339-timestamp>"
text_reference: "<private-content-reference>"
attachment_references: []
reply_route: "<opaque-route-token>"
classification: "private"
```

The adapter should store or transmit content only where required. Telemetry uses
opaque references, sizes, and hashes rather than message text.

Upstream basis:

- [Hermes Messaging Gateway](https://hermes-agent.nousresearch.com/docs/user-guide/messaging)
- [Hermes Sessions](https://hermes-agent.nousresearch.com/docs/user-guide/sessions)
- [Hermes Gateway Internals](https://hermes-agent.nousresearch.com/docs/developer-guide/gateway-internals/)

## 2. Workload authentication to Heimdall

Executor provides the integration, connection, policy, and MCP gateway
substrate. Asgard requires a trusted binding between the calling workload and
the Executor endpoint or connection set.

**Classification:** Asgard custom adapter/policy. Authenticated shared-caller
multiplexing is blocked pending validation.

| Property | Contract |
| --- | --- |
| Inputs | Mutually authenticated or signed request from one fixed workload endpoint |
| Outputs | Authenticated caller context attached to tool discovery and invocation |
| Authority | The transport or trusted gateway derives workload identity; model arguments have no authority |
| Persistence | Workload public keys or token hashes, policy version, and revocation state |
| Failure behavior | Missing, invalid, expired, or mismatched identity fails closed before tool discovery |
| Acceptance test | Each workload can use only its endpoint and catalogue; replay and cross-workload credentials fail; logs show the derived caller |

Logical request:

```json
{
  "schema": "asgard.tool-request.v1",
  "request_id": "<opaque-request-id>",
  "tool": "<registered-semantic-tool>",
  "arguments": {},
  "task_id": "<opaque-task-id>",
  "purpose": "<bounded-purpose>"
}
```

The request deliberately has no connector profile, downstream account, owner
email, or secret field.

Upstream basis:

- [Executor introduction](https://executor.sh/docs)
- [Executor connections](https://executor.sh/docs/concepts/connections)
- [Executor policies](https://executor.sh/docs/concepts/policies)

The exact documentation paths may move. Pin behavior to the deployed release
and its source, not merely the current website.

## 3. Safe baseline: separate Executor path per agent

Until authenticated caller multiplexing is proven, use a separate Executor
instance, process, profile, or isolated connector endpoint for each workload.
An instance is the strongest default where a profile is not documented as a
security boundary.

**Classification:** Asgard custom deployment policy.

Reference layout:

```yaml
heimdall_endpoints:
  ody:
    endpoint: "<private-endpoint-a>"
    allowed_connections:
      - "<ody-connection-reference>"
  muninn:
    endpoint: "<private-endpoint-b>"
    allowed_connections:
      - "<muninn-connection-reference>"
  huginn:
    endpoint: "<private-endpoint-c>"
    allowed_connections:
      - "<huginn-connection-reference>"
```

| Property | Contract |
| --- | --- |
| Inputs | Tool request arriving on a workload-specific private endpoint |
| Outputs | Catalogue and execution limited to that endpoint's fixed connectors |
| Authority | Network policy, workload authentication, and instance configuration jointly select the downstream identity |
| Persistence | Separate connection state, OAuth state, policies, and audit stream per workload |
| Failure behavior | One instance or connection failure does not fall back to another workload's identity |
| Acceptance test | Attempts to request, name, or route to another workload's connection fail; revoking one identity does not affect the others |

Do not place three connections in one shared catalogue and rely on the model to
choose the correct one.

This baseline may be replaced by a shared Executor service only after the exact
release demonstrates authenticated caller-to-connection mapping, non-overridable
selection, separate refresh-token state, correct downstream attribution, and
complete audit correlation.

## 4. Mimir search

Mem0 supplies the search substrate. Asgard constrains results to references to
canonical AFFiNE pages.

**Classification:** Upstream-supported substrate + Asgard custom adapter.

The [Mimir knowledge model](mimir-knowledge-model.md) defines the page
conventions behind this index. Canonical AFFiNE pages use exactly seven
conventional primary object types: `Project`, `Area`, `Person/Organisation`,
`Topic`, `Decision`, `Source`, and `Procedure`. Search results and index
metadata preserve the stable AFFiNE page ID and revision, classification,
`canonical_state`, `review_state`, permitted provenance and source references,
and deterministic content hash where relevant and policy permits them as safe
metadata.

| Property | Contract |
| --- | --- |
| Inputs | Query, authenticated owner, workload, permitted classification set, result limit, and task purpose |
| Outputs | Ranked AFFiNE references with indexed revision, canonical and review state where policy permits, score, and safe excerpt |
| Authority | Heimdall filters namespaces and classifications; Mem0 relevance never grants access |
| Persistence | Mem0 index generations plus source-revision metadata; the request is auditable |
| Failure behavior | Stale, malformed, unauthorized, or orphaned references are omitted; unavailable Mem0 produces an explicit retrieval failure rather than fabricated memory |
| Acceptance test | Cross-classification queries return nothing unauthorized; each result resolves to the indexed AFFiNE page and revision |

Example result:

```json
{
  "schema": "asgard.mimir-search-result.v1",
  "query_id": "<opaque-query-id>",
  "index_generation": "<opaque-generation-id>",
  "results": [
    {
      "affine_page_id": "<stable-page-id>",
      "affine_revision": "<source-revision>",
      "chunk_id": "<deterministic-chunk-id>",
      "content_hash": "<sha256>",
      "classification": "private",
      "score": 0.82,
      "excerpt": "<bounded-safe-excerpt>"
    }
  ]
}
```

The result object is bounded transport metadata, not a second canonical record
schema. Provenance and source references are returned only when authorized and
safe for the caller.

Ody must fetch material canonical content through the AFFiNE reader before
making an important claim. Mem0 does not become a second source of truth.

Upstream basis:

- [Mem0 open-source overview](https://docs.mem0.ai/open-source/overview)

## 5. Canonical AFFiNE reader and writer

Asgard requires a version-pinned connector that can read and, when explicitly
enabled, write the selected AFFiNE deployment while preserving downstream user
attribution.

**Classification:** Asgard custom adapter. Writes are blocked pending connector,
identity, and audit validation.

Asgard does not prescribe or invent an AFFiNE API or MCP endpoint in this
contract. The deployer must select an actively maintained connector, pin its
version and source, document its supported operations, and validate it against
the pinned AFFiNE release.

Canonical reads and writes operate on AFFiNE pages following the conventions in
the [Mimir knowledge model](mimir-knowledge-model.md). AFFiNE remains the
canonical representation; this contract does not introduce a separate Mimir
record envelope. The deployment-selected connector operations remain
version-pinned and validated, and this contract does not prescribe their
implementation.

| Property | Contract |
| --- | --- |
| Inputs | Stable workspace/page reference, expected revision, semantic read or proposed diff, provenance, classification, and idempotency key |
| Outputs | Canonical page content and revision for reads; new revision and downstream audit identity for writes |
| Authority | Heimdall selects a fixed caller-specific connector identity and applies read/write scope |
| Persistence | AFFiNE remains canonical; adapter stores only connector state, idempotency, and audit references |
| Failure behavior | Revision conflict, missing attribution, unsupported operation, or partial update fails without silent overwrite |
| Acceptance test | Read returns the expected canonical revision; writes preserve the expected downstream user, reject stale revisions, and are idempotent |

Logical write request:

```yaml
schema: asgard.affine-change.v1
change_id: "<opaque-change-id>"
workspace_id: "<stable-workspace-id>"
page_id: "<stable-page-id>"
expected_revision: "<source-revision>"
mode: "create-review-draft"
provenance:
  source_type: "conversation"
  source_id: "<opaque-source-id>"
diff_reference: "<private-diff-reference>"
classification: "private"
idempotency_key: "<opaque-idempotency-key>"
```

`asgard.affine-change.v1` remains the change transport envelope. The referenced
diff proposes an AFFiNE page that follows the Mimir page conventions, including
the applicable conventional type, `canonical_state`, `review_state`,
classification, and authorized provenance or source references. Sensitive
content is not embedded in the transport envelope.

The initial writer should support only review-inbox draft creation. Canonical
page mutation, supersession, and deletion are separately gated capabilities.

Upstream basis:

- [AFFiNE self-hosting](https://affine.pro/self-host)

Consult the selected AFFiNE and connector documentation for actual installation
and operation names.

## 6. Deterministic AFFiNE-to-Mem0 indexer

The indexer translates accepted AFFiNE content into a rebuildable Mem0
generation. Neither upstream product supplies the complete Asgard authority and
generation contract.

**Classification:** Asgard custom adapter.

| Property | Contract |
| --- | --- |
| Inputs | Consistent set of canonical AFFiNE pages with stable page IDs and revisions, one of the seven conventional object types, `canonical_state`, `review_state`, classification, and provenance or source references |
| Outputs | New Mem0 generation containing deterministic chunks and content hashes, only classification-permitted page metadata, and a validation manifest |
| Authority | Read-only AFFiNE indexer identity; write-only or generation-scoped Mem0 identity |
| Persistence | Generation manifest, page/chunk hashes, validation outcome, active-generation pointer |
| Failure behavior | Malformed page conventions or metadata fail validation; a failed or partial generation remains inactive and the current active index remains untouched |
| Acceptance test | Delete a disposable index, rebuild it twice, and obtain identical source/chunk manifests and representative search behavior |

Manifest:

```yaml
schema: asgard.index-generation.v1
generation_id: "<opaque-generation-id>"
created_at: "<rfc3339-timestamp>"
affine_snapshot: "<opaque-snapshot-reference>"
normalizer_version: "<pinned-normalizer-version>"
chunker_version: "<pinned-chunker-version>"
page_count: 42
chunk_count: 128
manifest_hash: "<sha256>"
validation:
  references_valid: true
  classifications_valid: true
  representative_queries_passed: true
status: "staged"
```

Promotion changes only the active index generation. It does not edit or delete
AFFiNE. Old index-generation retention follows an explicit operational policy.
The Mem0 projection is disposable and rebuildable. Canonical AFFiNE chunks are
written with `infer=false` so Mem0 stores deterministic canonical text without
independently extracting or rewriting facts.

## 7. Hermes transcript outbox and Muninn checkpoints

> **Gated foundation — not deployed production behavior.**

Hermes documents persisted sessions and a session API. The pinned Hermes
`v0.19.0` compatibility review found no suitable built-in redacted incremental
export or reliable completion event for long-lived Signal and WebUI sessions,
so Asgard supplies a narrow compatibility adapter. This is a version-specific
finding, not a claim about current or future Hermes releases.

**Classification:** Upstream-supported session/API substrate + gated Asgard
compatibility adapter.

| Property | Contract |
| --- | --- |
| Inputs | Explicitly allowed transcript windows whose source and owner are policy-allowlisted |
| Outputs | Minimized, HMAC-pseudonymized immutable transcript objects plus ordered, hash-chained manifests |
| Authority | Exporter reads only the documented Hermes API; Muninn never reads Hermes or the outbox directly; Heimdall mediates authenticated read, lease, checkpoint, and compare-and-swap operations |
| Persistence | Content-addressed append-only objects, immutable manifests, bounded leases, and a contiguous compare-and-swap checkpoint |
| Qualification | At least one user and final-assistant message, no pending tool call, a configured quiet period, and the identical source revision observed twice |
| Failure behavior | Identity ambiguity, malformed content, redaction failure, or a credential-bearing URL defers the window without publication; checkpoint never skips or rewinds |
| Acceptance test | Repeat a bounded synthetic export, prove idempotent publication and ordered leasing, then advance the checkpoint only after the corresponding AFFiNE draft persists |

Generic manifest:

```yaml
schema: asgard.transcript-manifest.v1
sequence: 7
previous_manifest_hash: "<sha256>"
objects:
  - object_hash: "<sha256>"
    source_class: "<allowed-source-class>"
    owner_reference: "<hmac-pseudonym>"
    session_reference: "<hmac-pseudonym>"
    source_revision: "<hmac-pseudonym>"
manifest_hash: "<sha256>"
```

Generic checkpoint:

```yaml
schema: asgard.muninn-checkpoint.v1
committed_sequence: 7
committed_manifest_hash: "<sha256>"
lease_reference: "<opaque-lease-reference>"
last_success_at: "<rfc3339-timestamp>"
```

The handoff accepts only the exact next sequence and matching manifest hash
under an active lease. It advances only after successful draft persistence;
failure leaves the checkpoint unchanged for an idempotent retry.

**WebUI limitation:** the reviewed `v0.19.0` path does not provide the trusted
user identity required for unattended owner allowlisting. Unattended WebUI
export therefore remains disabled; only an explicitly selected synthetic or
manual canary is permitted.

**Validation required:** prove twice-observed quiescence, redaction and
credential-URL rejection, manifest-chain integrity, lease conflicts, and
skip/rewind rejection. Prove the exporter has no Hermes state, workspace, or
database mount, and that only Heimdall can reach the private handoff. Atomic
publication also depends on same-filesystem hard-link semantics. Private HTTP
remains a residual risk and requires a private encrypted network plus explicit
host-firewall enforcement.

See [Hermes-to-Muninn transcript outbox](transcript-outbox.md) for the complete
state flow, canary sequence, disabled-by-default controls, and residual risks.

Upstream basis:

- [Hermes Sessions](https://hermes-agent.nousresearch.com/docs/user-guide/sessions)
- [Hermes Session Storage](https://hermes-agent.nousresearch.com/docs/developer-guide/session-storage)
- [Hermes API Server](https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server/)

## 8. Huginn capture staging and event handoff

n8n supplies scheduling, workflow, webhook, and connector building blocks.
Asgard defines the immutable capture and curation-event boundary.

**Classification:** Upstream-supported workflow substrate + Asgard custom
workflow contract.

| Property | Contract |
| --- | --- |
| Inputs | Approved monitor definition, source allowlist, schedule, fetch policy, and previous capture reference |
| Outputs | Immutable raw capture plus a small curation event |
| Authority | Huginn may fetch only through approved workers and append captures; it has no canonical AFFiNE write authority |
| Persistence | n8n workflow/run state, immutable capture object, hash chain or prior reference, event delivery state |
| Failure behavior | Fetch, normalization, storage, or event failure is explicit; no event is published before durable capture persistence |
| Acceptance test | Changed content produces one staged capture and one idempotent event; unchanged content produces no duplicate; hostile content cannot reach private networks or canonical AFFiNE |

Monitor:

```yaml
schema: asgard.monitor.v1
monitor_id: "<opaque-monitor-id>"
source: "<approved-public-url>"
schedule: "<bounded-schedule>"
retrieval_profile: "<fixed-worker-profile>"
maximum_bytes: 1048576
change_policy: "content-hash"
enabled: false
```

Capture event:

```json
{
  "schema": "asgard.capture-ready.v1",
  "event_id": "<opaque-event-id>",
  "capture_id": "<opaque-capture-id>",
  "monitor_id": "<opaque-monitor-id>",
  "captured_at": "<rfc3339-timestamp>",
  "content_hash": "<sha256>",
  "media_type": "text/html",
  "classification": "untrusted-external",
  "prior_capture_id": "<optional-opaque-id>"
}
```

The event contains a reference, not the full hostile document. Muninn retrieves
the capture through a bounded read path and creates a review draft only.

Upstream basis:

- [n8n hosting documentation](https://docs.n8n.io/hosting/)
- [n8n Webhook node](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/)

## 9. Durable approval and WebUI/Signal resume

Executor documents per-tool policy as an upstream concept. Asgard requires
durable pending state, exact action binding, and delivery/resume bridges for
Hermes WebUI and Signal.

**Classification:** Asgard custom service; blocked pending end-to-end
validation.

| Property | Contract |
| --- | --- |
| Inputs | Exact normalized tool request, caller, owner, connector identity, risk, and semantic summary |
| Outputs | Pending approval ID, final decision, and at most one resumed execution |
| Authority | Only the authenticated owner can decide; the approval service verifies stored hashes and allowed interfaces |
| Persistence | Durable state machine, decision timestamps, nonce, action hash, expiry, consumption, and delivery ledger |
| Failure behavior | Restart preserves or safely expires pending state; changed, replayed, expired, denied, or ambiguous requests fail closed |
| Acceptance test | Approve, deny, expire, replay, mutate, restart, and cross-interface cases behave exactly as documented with no duplicate action |

Approval record:

```yaml
schema: asgard.approval.v1
approval_id: "<opaque-approval-id>"
short_id: "<non-secret-short-id>"
owner_id: "<derived-owner-id>"
workload_id: "<derived-workload-id>"
task_id: "<opaque-task-id>"
tool_id: "<registered-tool-id>"
connector_reference: "<server-selected-reference>"
argument_hash: "<sha256>"
semantic_summary: "<safe-human-summary>"
risk: "high"
state: "pending"
created_at: "<rfc3339-timestamp>"
expires_at: "<rfc3339-timestamp>"
allowed_interfaces:
  - "webui"
  - "signal"
```

Resume:

```json
{
  "schema": "asgard.approval-decision.v1",
  "approval_id": "<opaque-approval-id>",
  "decision": "approve_once",
  "owner_id": "<derived-from-interface-authentication>",
  "decided_at": "<rfc3339-timestamp>"
}
```

A Signal command such as `/approve <short-id>` is a desired user experience.
Parsing the command is not enough: it must resolve the same durable record,
verify the Signal sender, consume one exact stored action, and update the WebUI.

Keep write and high-risk tools disabled until this contract passes. Do not
reconstruct a pending tool call from conversational memory.

Upstream basis:

- [Executor policies](https://executor.sh/docs/concepts/policies)
- [Hermes Messaging Gateway](https://hermes-agent.nousresearch.com/docs/user-guide/messaging)

## 10. Ody update broker

Hermes and the deployment platform may each provide update operations. Asgard
requires a narrow broker that converts an owner request into a pinned,
reviewable, recoverable stack update.

**Classification:** Asgard custom privileged adapter.

| Property | Contract |
| --- | --- |
| Inputs | Allowed component, release channel, current version, requested target or check-for-update intent |
| Outputs | Pinned deployment proposal, approval request when required, health result, and rollback result |
| Authority | Broker has access only to predefined stacks and release sources; Ody cannot supply arbitrary commands, paths, images, or deployment resource IDs |
| Persistence | Proposal, version/digest, prior recovery point, policy, approval, deployment job, health evidence |
| Failure behavior | Unsupported target or failed verification does not deploy; failed health gate rolls back or stops for human recovery |
| Acceptance test | Reject arbitrary stack/image input; perform a safe pinned update; force a health failure and restore the recorded previous version |

Request:

```yaml
schema: asgard.update-request.v1
request_id: "<opaque-request-id>"
component: "ody"
intent: "check-and-propose"
channel: "stable"
current_version: "<pinned-current-version>"
requested_by: "<derived-owner-id>"
```

Proposal:

```yaml
schema: asgard.update-proposal.v1
proposal_id: "<opaque-proposal-id>"
component: "ody"
from: "<pinned-current-version>"
to: "<pinned-target-version-or-digest>"
source: "<authoritative-release-source>"
change_summary_reference: "<private-summary-reference>"
recovery_point: "<opaque-recovery-reference>"
health_suite: "<versioned-test-suite>"
state: "awaiting-approval"
```

The broker, not the model, maps `component: ody` to the private deployment
resource. The agent never receives the deployment controller's administrative
credential.

## 11. Audit record sink

Product logs and Grafana Cloud are useful observability sources. Asgard requires
a security record that correlates authenticated caller, policy, approval,
connector, action, and result without recording secrets.

**Classification:** Asgard custom adapter/policy.

| Property | Contract |
| --- | --- |
| Inputs | Authenticated gateway lifecycle events and decisions |
| Outputs | Append-oriented local security records plus a redacted observability copy |
| Authority | Only trusted gateway/adapter identities append; agents cannot edit or delete records |
| Persistence | Durable local or object-backed record with explicit retention; Grafana Cloud receives a reduced copy |
| Failure behavior | High-risk actions fail closed if the required durable record cannot be written; lower-risk behavior follows documented policy |
| Acceptance test | Trace a complete action through request, policy, approval, connector, downstream identity, and result; verify tamper/replay signals and absence of secrets |

Record:

```json
{
  "schema": "asgard.audit.v1",
  "event_id": "<opaque-event-id>",
  "event_type": "tool.completed",
  "occurred_at": "<rfc3339-timestamp>",
  "request_id": "<opaque-request-id>",
  "task_id": "<opaque-task-id>",
  "workload_id": "<derived-workload-id>",
  "owner_id": "<pseudonymous-owner-id>",
  "tool_id": "<registered-tool-id>",
  "connector_reference": "<server-selected-reference>",
  "policy_version": "<policy-version>",
  "decision": "allowed",
  "approval_id": "<optional-opaque-id>",
  "argument_hash": "<sha256>",
  "result_hash": "<sha256>",
  "result_classification": "private",
  "status": "success"
}
```

Do not place full prompts, arguments, results, recipient addresses, URLs with
tokens, credentials, cookies, or model reasoning in this record.

Executor-specific caveat:

> Executor logs may be useful without satisfying durable security-audit
> requirements.

Validate pre-action durability, post-action completion, crash gaps, redaction,
connection attribution, approval correlation, idempotency, retention, and
tamper evidence. Add a trusted wrapper or independent append sink where the
pinned release is insufficient. Grafana Cloud observes the redacted copy and
never authorizes or resumes an action.

## Optional and experimental contracts

These capabilities are not part of the minimum secure installation:

| Capability | Status | Enablement gate |
| --- | --- | --- |
| Shared Executor with authenticated caller multiplexing | Blocked pending validation | All identity-selection and revocation tests pass |
| AFFiNE AI with Ody's normal tool catalogue | Optional/experimental | Identity, recursion, tool-policy, and write-attribution tests pass |
| Authenticated browser sessions | Optional/experimental | Disposable isolation, credential scope, and private-network denial pass |
| Automatic low-risk canonical promotion | Optional/experimental | Explicit policy classes, provenance, conflict, rollback, and audit tests pass |
| Automatic application updates | Optional/experimental | Pinned proposal, approval, health, rollback, and audit tests pass |
| Model-based injection or action screening | Optional/experimental | Used only as defense in depth; deterministic policy remains authoritative |

## Capability gating

The base setup should expose the smallest useful path:

```text
owner
    → browser Ody interface
    → workload-specific Heimdall endpoint
    → read-only Mimir search
    → canonical AFFiNE read
    → answer
```

Enable additional contracts in this order:

1. Channel normalization for one interface
2. Separate workload-specific Heimdall paths
3. Read-only Mimir search and canonical AFFiNE reads
4. Deterministic AFFiNE-to-Mem0 rebuild
5. Manual Muninn export and draft creation
6. Hourly and nightly Muninn schedules
7. One unauthenticated Huginn monitor and capture handoff
8. Durable browser approval
9. Signal approval resume
10. One low-impact attributed write
11. Update broker and append-oriented audit

For every step:

- record the pinned upstream and contract versions;
- run positive, negative, restart, and retry tests;
- store redacted evidence in the private repository;
- keep the prior capability state recoverable;
- leave the capability disabled if any authority or failure behavior is
  ambiguous.

## Integration readiness record

The private deployment should maintain one record per contract:

```yaml
schema: asgard.integration-readiness.v1
contract: "canonical-affine-writer"
contract_version: "v1"
classification: "asgard-custom-adapter"
upstream:
  product: "<product-name>"
  version: "<pinned-version-or-digest>"
implementation_reference: "<private-code-or-config-reference>"
enabled: false
authority_reviewed: false
failure_behavior_tested: false
restart_tested: false
acceptance_evidence: []
known_gaps:
  - "<non-secret-gap-description>"
last_reviewed_at: "<rfc3339-timestamp>"
```

An empty evidence list means the capability is not ready, regardless of whether
the relevant containers are running.

## Official upstream sources

Use upstream sources to confirm the substrate available in the pinned release:

- [Hermes Agent documentation](https://hermes-agent.nousresearch.com/docs/)
- [Hermes Messaging Gateway](https://hermes-agent.nousresearch.com/docs/user-guide/messaging)
- [Hermes Sessions](https://hermes-agent.nousresearch.com/docs/user-guide/sessions)
- [Hermes API Server](https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server/)
- [Executor documentation](https://executor.sh/docs)
- [AFFiNE self-hosting](https://affine.pro/self-host)
- [Mem0 open-source overview](https://docs.mem0.ai/open-source/overview)
- [n8n hosting documentation](https://docs.n8n.io/hosting/)

Upstream documentation describes product behavior. This document defines how
Asgard composes those behaviors into a bounded system.
