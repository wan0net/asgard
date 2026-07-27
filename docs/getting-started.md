# Getting started

## What this guide does

This is a reader-oriented deployment path for the **Pantheon Blueprint**. It
helps an operator establish a small, safe first deployment and decide what to
add next. It is a reference design, not a distribution or turnkey installation
manual. Upstream projects change independently; use their current documentation
and the detailed local references before choosing versions, configuration
syntax, or connector behavior.

Treat this guide as a sequence of design and deployment decisions. Pin the
versions you install, record the resulting inventory and rollback point, and
keep an integration disabled until its identity, data flow, failure behavior,
and acceptance evidence are understood. Do not put domains, addresses, account
names, tokens, passwords, OAuth secrets, recovery codes, or service-account
credentials in a repository. Examples such as `pantheon.example.com`,
`/opt/pantheon`, and `<PRIVATE_CONFIG_REPO>` are placeholders.

The goal is not to expose every feature early. Start with a coherent path that
keeps canonical knowledge, tool execution, agent behavior, secrets, and human
access separate. The architecture, threat assumptions, and integration
contracts remain the source of truth when this short guide leaves a choice
open.

## Choose the first milestone

Make the first release deliberately narrow. Its success criterion is:

`user -> Odine -> Heimdall -> Mem0 reference -> canonical AFFiNE -> same interface`

In practical terms, a user reaches Odine through one protected interface;
Odine authenticates to Heimdall; Heimdall searches Mem0 under Odine's workload
identity; and Odine retrieves the referenced current content from AFFiNE
through Heimdall before responding in that same interface. Direct Odine-to-
AFFiNE access must be blocked by the network and not merely discouraged by a
prompt or convention.

This path needs adapter and policy work; it is not supplied as one finished
product. Enable no outbound messaging, browser automation, infrastructure
changes, unattended knowledge writes, or destructive tool while establishing
it. Each later capability must have a documented purpose, caller identity,
least-privilege tool catalogue, expected result, and safe failure mode. The
[integration contracts](integration-contracts.md) explain what must be proven
for a connection.

Keep the data model clear from the start: AFFiNE is canonical knowledge and
the authority for its current content. Mem0 is a rebuildable retrieval aid that
may point to AFFiNE; it does not become the authority when a memory is stale or
missing. Heimdall is mandatory mediation for agent-initiated access to these
services and to tools. Do not create a convenience route that lets an agent
bypass it.

## Prepare three trust zones

Use three host roles even if the physical machines or cloud instances have
different names. The roles create reviewable boundaries, not a claim that one
host alone solves every security problem.

| Host role | Trust zone | Initial responsibility |
| --- | --- | --- |
| `agent-01` | Assistant runtime | Odine, its approved interface, and optional isolated workers |
| `knowledge-01` | Trusted knowledge | AFFiNE, Mem0, and controlled indexing services |
| `tools-01` | Tool execution and untrusted collection | Heimdall, executor services, and restricted connectors or browser workers |

Start each host from a supported, patched operating system with recovery access,
time synchronization, a non-root administrator, and deny-by-default inbound
rules. Give the deployment runtime a dedicated application root such as
`/opt/pantheon`, separate persistent-data storage, and backup staging that is
not the only copy of recoverable data. Record operating-system, runtime,
network, disk, and recovery details in the deployment inventory.

Use private networking and host policy so the normal initial paths are only
administrator-to-host, `agent-01`-to-Heimdall, the controlled knowledge
indexer-to-Heimdall, and `tools-01`-to-explicit downstream APIs. Everything
else begins denied until a documented workflow requires it. Private transport
can limit host reachability, but it does not establish the calling workload
inside a host: Heimdall must still authenticate and authorize callers.

Keep privileged deployment components separate from agent workloads. Do not
provide a container-engine socket, unrestricted host filesystem, SSH material,
or a secret store to Odine, an indexer, a connector, browser worker, AFFiNE,
Mem0, or workflow service. A deployment manager and ingress component may need
carefully limited privileged access; document that exception and review it.
See the [security model](security.md) for the boundaries and negative cases to
validate.

## Deploy the supporting platform

Establish the platform controls before exposing an application route.

- **Traefik** provides the per-host ingress boundary. Discover workloads by
  explicit opt-in, separate user-facing and administrative routes, and keep
  databases, internal APIs, Mem0, Heimdall, and deployment endpoints off public
  ingress.
- **Tailscale** provides private transport for administration and internal
  service paths. Use non-personal host identities and ACLs that match the trust
  zones.
- **Pangolin** is optional human-facing publication. Publish only a deliberately
  selected Traefik route after its private route works; it does not replace
  application authentication or authorization.
- **Komodo** manages deployment promotion. Keep its core outside these three
  roles where practical, restrict each host agent to `/opt/pantheon` and backup
  staging, and deploy pinned, reviewed releases rather than unreviewed moving
  targets. Store deployment definitions and non-secret templates in
  `<PRIVATE_CONFIG_REPO>`.
- **1Password** supplies deployment secrets through narrowly scoped service
  identities. It is not an agent tool and should not be exposed through
  Heimdall, prompts, or a general-purpose connector. Agents receive only the
  capabilities they need, never the vault as a source of arbitrary values.
- **Grafana** receives operational telemetry. Collect service health, resource
  pressure, restart state, request outcomes, correlated request/tool/deployment
  identifiers, and backup or restore results. Redact prompts, content,
  credentials, headers, and raw captures. Grafana is neither the authoritative
  audit record nor an authorization or approval system.

DNS, network reachability, TLS, user authentication, and application
authorization are separate controls. Use private names for internal services;
for example, a deliberately published user endpoint may use
`chat.pantheon.example.com`, while internal APIs remain private. Avoid treating
the existence of a DNS record or a tunnel as authorization.

Before advancing, verify that each host is reachable only through intended
paths, the deployment plane can return after a reboot, secrets stay out of
rendered configuration and logs, and telemetry does not become a copy of
application data. Record evidence rather than copying a generic checklist.

## Deploy service foundations in order

Use the recommended order: **`tools-01 -> knowledge-01 -> agent-01`**. It
makes downstream boundaries available before an agent is allowed to use them.
Each foundation should be running privately, on pinned versions, with its data
location, identity, backup scope, health signal, and rollback plan recorded.

### 1. `tools-01`: Heimdall and restricted execution

Deploy Heimdall before any agent runtime. Give it an explicit caller identity
for Odine and a default-deny catalogue: a caller receives only the tools it
needs, and an unrecognized caller or tool fails without reaching a downstream
system. Tool authorization must come from authenticated caller context, not a
caller name supplied in tool arguments. If executor, connector, browser, or
workflow components are needed later, keep them here and expose only
purpose-built Heimdall operations.

At this stage, do not import every available integration. Establish the
connector needed for the first read path and verify that a denied call has no
side effect. The detailed [tooling guide](tooling.md) and
[integration contracts](integration-contracts.md) define the expected
boundaries.

### 2. `knowledge-01`: canonical knowledge and retrieval

Deploy AFFiNE as the canonical store, including its required data services and
backup plan. Keep any human access behind the intended protected route. Deploy
Mem0 as a separate, rebuildable retrieval layer, with access restricted to its
approved service identities. Build or connect the controlled indexer only when
it can preserve provenance and recover from interruption without silently
changing canonical records.

The first retrieval contract should return a reference that resolves through
Heimdall to the applicable current AFFiNE content. If Mem0 is unavailable,
stale, or must be rebuilt, do not substitute its content for the canonical
record. Follow the [knowledge model](mimir-knowledge-model.md) and
[data flows](data-flows.md) when deciding how references, revision checks, and
future writes work.

### 3. `agent-01`: Odine and one protected interface

Deploy Odine with one workload identity and configure Heimdall as its ordinary
external tool path. Disable duplicate direct tools for AFFiNE, web access,
filesystem access, shell access, browser control, email, and infrastructure
changes unless and until a specific mediated capability has passed review.
Use the official interface first and ensure it keeps the request and response
in the same user-visible session.

An agent may have a narrowly defined local exception for managed skills or a
reviewed self-update, but that exception is not an open host workspace. Limit
its mounts and commands, require human approval where appropriate, stage and
verify updates, and preserve a pinned rollback target. Consult the
[operations guide](operations.md) before introducing update automation.

## Connect the first end-to-end request

With all three foundations private, connect only the minimum read path. A user
submits a request through the selected protected Odine interface. Odine calls
the read capability at Heimdall with its workload identity. Heimdall enforces
Odine's allowed catalogue, obtains a Mem0 reference, and retrieves the
referenced current AFFiNE content through the same mediated boundary. Odine
answers through the originating interface.

Prove both the allowed and denied paths for the installed versions. The allowed
path should preserve correlated, redacted operational identifiers. The denied
path should show that stopping Heimdall or attempting a direct Odine-to-AFFiNE
connection prevents the read; it must not quietly fall back to an alternative
route. Record the versions and evidence with the deployment inventory. Detailed
request and review sequences are in [data flows](data-flows.md).

Do not mistake a successful response for a finished security design. Confirm
the result is based on the canonical AFFiNE record, handles an unavailable or
stale Mem0 reference safely, and reveals no raw credentials to Odine or its
interface. Follow [security](security.md) for adversarial and failure-oriented
testing.

## Add optional capabilities one at a time

Expand from the proven path, not from a list of installed products. For every
optional capability, state its purpose, owner, trust zone, identity, ingress,
data classification, allowed Heimdall operations, approval behavior, rollback,
and proof of failure closure before enabling it.

- Add a community web interface or native client only after it demonstrably
  applies the same session, authorization, and approval semantics as the
  official interface. It is a client choice, not a way around Odine policy.
- Add a messaging channel such as Signal only with a dedicated identity,
  explicit sender allowlist, protected session mapping, and an approval flow
  bound to the originating user, request, tool, and normalized arguments.
- Add Muninn as an isolated, non-interactive worker with a distinct identity,
  state, and catalogue. Begin with manual, read-only work; future knowledge
  output belongs in traceable review candidates, not silent canonical changes.
- Add collection or workflow roles only in `tools-01`. Treat inbound material
  as untrusted, isolate it from canonical knowledge, and never let collection
  self-promote content into AFFiNE.
- Add controlled writes, browser work, infrastructure actions, and schedules
  last. They require specific contracts, approval and recovery design, and
  evidence that retries, timeouts, and denials do not cause unintended effects.

Each newly enabled channel or role is another security and operations surface.
Repeat its relevant integration and failure tests rather than assuming the
first interface proves the rest.

## Prove readiness

Readiness is evidence for your deployed versions and intended scope, not a
copied central gate matrix. Keep dependent capabilities disabled until their
applicable contracts and recovery paths have passed.

- Use [assurance](assurance.md) to organize the evidence and residual-risk
  decision.
- Use [security](security.md) to verify trust-zone boundaries, identities,
  secret handling, mediated access, and negative tests.
- Use [integration contracts](integration-contracts.md) to verify every enabled
  cross-service and channel contract.
- Use [backups](backups.md) to define backups, immutable copies, restore tests,
  recovery targets, and evidence of a usable restore.

At a minimum, be able to show the first milestone works through its intended
route, direct bypass is blocked, an unavailable dependency fails closed, data
and secrets are not leaked into observability, the deployment can be recovered,
and the canonical AFFiNE record remains distinct from rebuildable Mem0 data.

## Where to go next

Use the detailed references as the work requires them:

- [Architecture](architecture.md) for component roles and boundaries.
- [Data flows](data-flows.md) for request, approval, indexing, and review
  sequences.
- [Security](security.md) for threats, policies, and validation approach.
- [Integration contracts](integration-contracts.md) for integration-specific
  acceptance criteria.
- [Tooling](tooling.md) for mediated tool design.
- [Knowledge model](mimir-knowledge-model.md) for canonical content,
  references, and controlled knowledge changes.
- [Operations](operations.md) and [backups](backups.md) for change,
  monitoring, incident, backup, restore, and rollback practices.
- [Publishing](publishing.md) when deciding whether and how to expose a human
  interface.
