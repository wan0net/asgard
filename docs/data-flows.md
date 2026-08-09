# Data flows

This page shows how requests, knowledge, evidence, approvals, and deployments
move through Pantheon Blueprint.

Every flow follows the same rules:

- Ody is the only user-facing assistant.
- Agent and workflow actions pass through Heimdall.
- Workload identity selects the allowed tools and downstream account.
- AFFiNE is accepted knowledge; Mem0 is only a rebuildable search index.
- External content starts as untrusted evidence.
- Sensitive actions pause for one exact approval.
- Checkpoints move only after the corresponding result is durably stored.
- Telemetry observes the flow but never authorizes it.

These are **Pantheon Blueprint policy** and **validation requirements**, not a
claim that a deployment already passes them.

## User question and knowledge retrieval

The owner can talk to Ody through a browser, Hermex, Signal, or another
approved channel. The channel authenticates the owner and preserves the reply
route. It does not give the model channel credentials.

```mermaid
sequenceDiagram
    actor Owner
    participant Channel as "Browser, Hermex, or messaging"
    participant Ody
    participant Heimdall
    participant Mem0 as "Mem0 search index"
    participant AFFiNE as "AFFiNE canonical knowledge"

    Owner->>Channel: "Ask a question"
    Channel->>Ody: "Authenticated message and reply route"
    Ody->>Heimdall: "Search request"
    Heimdall->>Mem0: "Search permitted namespace"
    Mem0-->>Heimdall: "Candidate page IDs"
    Heimdall-->>Ody: "Candidate references"
    Ody->>Heimdall: "Read material pages"
    Heimdall->>AFFiNE: "Read as Ody"
    AFFiNE-->>Heimdall: "Canonical pages and revisions"
    Heimdall-->>Ody: "Filtered canonical content"
    Ody-->>Channel: "One answer"
    Channel-->>Owner: "Reply on the originating channel"
```

Mem0 helps Ody find likely pages. Ody reads the corresponding AFFiNE pages
before treating the content as accepted knowledge. If Mem0 and AFFiNE disagree,
AFFiNE wins.

Routine permitted reads should not ask the owner for approval. A policy denial
or missing identity stops the request; it does not cause a fallback to a direct
connection.

## Tool action

Ody, Muninn, and Huginn each have their own workload identity. Heimdall maps
that identity to a fixed tool catalogue and fixed downstream connections.

```mermaid
flowchart LR
    Caller["Authenticated workload"] --> Request["Capability request"]
    Request --> Heimdall["Heimdall"]
    Heimdall --> Identity["Fixed caller and connection mapping"]
    Identity --> Policy{"Policy decision"}
    Policy -->|"allow"| Tool["Scoped tool action"]
    Policy -->|"approval required"| Pause["Exact approval pause"]
    Policy -->|"deny or unknown"| Deny["No action"]
    Pause -->|"valid approval"| Tool
    Pause -->|"deny, expire, replay, or change"| Deny
    Tool --> Result["Filtered result and action evidence"]
```

The model may choose a permitted capability and provide its bounded business
arguments. It must not choose credentials, another role's connector, a broader
repository, or an unapproved deployment target.

An approval prompt shows the meaningful effect: action, target, material
arguments or diff, expiry, and whether it is once-only. A conversational “yes”
is not approval. See [Approvals](approvals.md).

## Conversation to knowledge

Muninn reviews completed conversation windows outside the interactive reply
path. It receives a minimized, redacted, append-only handoff rather than direct
access to Ody's mutable runtime state.

```mermaid
sequenceDiagram
    participant Ody
    participant Outbox as "Append-only transcript outbox"
    participant Muninn
    participant Heimdall
    participant AFFiNE as "AFFiNE review inbox"
    participant Owner

    Ody->>Outbox: "Eligible minimized conversation window"
    Muninn->>Heimdall: "Acquire lease and request exact-next window"
    Heimdall->>Outbox: "Authenticated bounded read"
    Outbox-->>Muninn: "Window and provenance"
    Muninn->>Muninn: "Extract and classify durable candidates"
    Muninn->>Heimdall: "Create traceable draft"
    Heimdall->>AFFiNE: "Write as Muninn"
    AFFiNE-->>Muninn: "Draft ID and revision"
    Muninn->>Heimdall: "Commit exact-next checkpoint"
    opt "Policy requires human review"
        AFFiNE-->>Owner: "Present proposed change and provenance"
        Owner->>AFFiNE: "Accept, reject, or edit"
    end
```

Muninn classifies each candidate as a duplicate, supporting evidence, new
knowledge, an update, a contradiction, temporary information, or sensitive
material. Initial output goes to a review inbox or draft area.

Low-risk policy may allow carefully bounded draft creation or append-only
annotation. Contradictions, sensitive material, deletions, and material changes
to accepted decisions require review. Muninn must not silently replace or
delete canonical pages.

If draft persistence fails, the checkpoint stays unchanged. Replay uses stable
source and candidate IDs so it does not create duplicate drafts.

## Huginn external collection and Muninn curation

Huginn collects; Muninn interprets; AFFiNE accepts. Keeping these stages
separate prevents hostile content from promoting itself into trusted knowledge.

```mermaid
flowchart LR
    Source["External source"] --> Huginn["Huginn collection"]
    Huginn --> Validate["Validate, limit, and classify"]
    Validate -->|"unsafe"| Quarantine["Quarantine or reject"]
    Validate -->|"allowed"| Capture["Immutable capture with provenance"]
    Capture --> Compare["Deduplicate and compare"]
    Compare -->|"unchanged"| Noop["No new event"]
    Compare -->|"changed"| Muninn["Muninn review candidate"]
    Muninn --> Draft["AFFiNE draft or review inbox"]
    Draft --> Decision{"Review policy"}
    Decision -->|"accept"| Canonical["AFFiNE accepted knowledge"]
    Decision -->|"reject or defer"| Inbox["Remain in review"]
    Canonical --> Index["Update rebuildable Mem0 index"]
```

A reviewed workflow may fetch a fixed anonymous public source directly.
Authenticated connectors, browser actions, and agent-requested operations still
pass through Heimdall with Huginn's fixed identity.

The captured page can contain instructions, scripts, credentials, or misleading
claims. None of that content may change collection policy, tool selection,
approval state, or canonical knowledge authority.

## Accepted knowledge to search

AFFiNE-to-Mem0 synchronization is one-way. The indexer consumes accepted
revisions and records which canonical revision each index entry represents.

```mermaid
flowchart LR
    AFFiNE["AFFiNE accepted revision"] --> Event["Revision event"]
    Event --> Indexer["Controlled indexer"]
    Indexer --> Build["Build next Mem0 generation"]
    Build --> Check{"Completeness and sample checks pass?"}
    Check -->|"yes"| Switch["Atomically activate generation"]
    Check -->|"no"| Keep["Keep current generation"]
    Switch --> Mem0["Mem0 search index"]
```

Mem0 never writes accepted knowledge back into AFFiNE. Rebuild starts from
AFFiNE, not from the old index. A failed or incomplete generation is not
activated.

## Prepare, merge, and deploy

Maintenance uses separate authority from normal conversation. Read-only
diagnosis needs no maintenance session. Preparing a bounded change requires an
approved session. Merge and deployment then require separate exact approvals.

```mermaid
sequenceDiagram
    actor Owner
    participant Ody
    participant Control as "Maintenance control"
    participant Worker as "Disposable coding worker"
    participant Git as "Git forge and CI"
    participant Deploy as "Deployment broker"

    Owner->>Ody: "Diagnose a problem"
    Ody-->>Owner: "Read-only findings"
    Owner->>Ody: "Prepare a bounded fix"
    Ody->>Control: "Propose exact scope, limits, tests, and expiry"
    Control-->>Owner: "Request session approval"
    Owner->>Control: "Approve exact preparation scope"
    Control->>Worker: "Issue bounded grants"
    Worker->>Git: "Branch, patch, tests, and draft pull request"
    Git-->>Control: "Pinned commits and check results"
    Control-->>Owner: "Request exact merge approval"
    Owner->>Control: "Approve exact merge"
    Control->>Git: "Merge once"
    Control-->>Owner: "Request exact deployment approval"
    Owner->>Control: "Approve pinned deployment and rollback"
    Control->>Deploy: "Deploy approved desired-state revision"
    Deploy-->>Control: "Health, evidence, and rollback result"
```

The preparation session does not imply permission to merge. Merge does not
imply permission to deploy. A changed commit, target, image, policy revision,
backup, or rollback point invalidates the corresponding approval.

Deployment stops when the required backup cannot be verified, the canary
fails, the maintenance lease is lost, or health and semantic checks disagree.
See [Scoped maintenance sessions](maintenance-sessions.md) for the complete
contract.

## Backup and restore

Backups move application-consistent staged data to a separate failure domain.
The backup writer should append new objects but should not be able to erase
history.

```mermaid
flowchart LR
    Services["Application state"] --> Stage["Consistent local stage"]
    Stage --> VerifyLocal["Validate staged set"]
    VerifyLocal --> Writer["Append-oriented backup writer"]
    Writer --> Remote["Separate backup target"]
    Remote --> VerifyRemote["Independent remote verification"]
    VerifyRemote --> Drill["Isolated restore drill"]
    Drill --> Evidence["RPO, RTO, integrity, and identity evidence"]
```

An uploaded object is not a verified backup. Production cutover after a
restore requires a human decision because it replaces live state. See
[Backups and restore](backups.md).

## Quick failure table

| Failure | Required result |
| --- | --- |
| Heimdall unavailable | Agent action stops; no direct-connector fallback |
| Approval missing, altered, expired, or replayed | No tool invocation |
| External capture malformed or unsafe | Reject or quarantine; canonical knowledge unchanged |
| AFFiNE draft write fails | Checkpoint unchanged; bounded retry or operator review |
| Mem0 rebuild fails | Current generation stays active; AFFiNE remains authoritative |
| Tool outcome is ambiguous | Reconcile by idempotency key before retry |
| Backup or canary verification fails | Deployment blocked |
| Health is uncertain after deployment | Stop rollout and use the approved rollback or recovery path |

## Validation

A deployment should test each flow with synthetic data and record both the
success and failure paths. At minimum, prove caller separation, connector
selection, approval replay resistance, canonical authorship, idempotent replay,
checkpoint ordering, quarantine behavior, index rebuild, backup verification,
and recovery after restart.

Use [Readiness and assurance](assurance.md) for evidence records and promotion
gates, and [Integration contracts](integration-contracts.md) for detailed
component requirements.
