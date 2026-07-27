# Getting started

This guide takes a competent operator—or a coding agent working under human
supervision—from three clean Debian or Ubuntu hosts to the upstream service
foundation for Asgard. It also identifies the integration work required to
connect those services safely. It is not a turnkey installer for the complete
system.

Asgard is a reference architecture, not a distribution. Upstream projects
change independently, so this guide deliberately avoids copying unstable
configuration keys and callback paths. Obtain the current release artifacts
and exact syntax from each linked upstream project, pin what you deploy, and
record the result in your deployment inventory. Track every cross-product
assumption against [Integration contracts](integration-contracts.md); keep an
integration disabled until its contract and acceptance tests are satisfied.

## How to read this guide

The following labels distinguish evidence from design intent:

- **Upstream fact** describes behavior documented by the linked project.
- **Asgard policy** is a requirement of this reference architecture. A product
  does not necessarily enforce it automatically.
- **Optional** identifies a component that is useful but not required for the
  first end-to-end path.
- **Validation required** marks an integration that must be demonstrated in
  your installed versions before it can be treated as a security control.

Do not put real domains, addresses, account names, tokens, passwords, OAuth
secrets, recovery codes, or service-account credentials in this repository.
Values such as `example.com`, `<VERSION>`, and `<SECRET_REFERENCE>` are
placeholders.

## The first integrated milestone

After the upstream foundations are running, the first integration target is
intentionally narrow:

1. A user can reach Ody over a protected web interface.
2. Ody can authenticate to Heimdall.
3. Heimdall can search Mem0 under Ody's workload identity.
4. Ody can retrieve the referenced canonical page from AFFiNE through
   Heimdall.
5. The response returns to the same user interface.
6. The complete path has correlated, redacted telemetry.
7. A direct Ody-to-AFFiNE connection is blocked by the network.

This path requires adapters and policy that are not supplied by this repository
as one finished product. Do not enable outbound messaging, browser automation,
infrastructure changes, or unattended knowledge writes until the relevant
integration contracts and validation gates pass.

## 1. Make the deployment decisions

Record these decisions before provisioning anything:

| Decision | Recommended starting value |
| --- | --- |
| Host operating system | One supported Debian or Ubuntu release across all three hosts |
| Container runtime | Docker Engine with the Compose plugin |
| Deployment manager | Existing Komodo Core, with Periphery on each Asgard host |
| HTTP ingress | One Traefik instance per host |
| Private transport | Tailscale on each host |
| Human remote ingress | Pangolin for deliberately published interfaces |
| Secret source | 1Password service accounts with least-privilege vault access |
| Observability | Grafana Alloy on each host, exporting to Grafana Cloud |
| Backups | Versioned or object-locked S3-compatible storage in a separate failure domain |
| Upgrade policy | Pinned release tags or digests, promoted after backup and smoke tests |
| Public DNS suffix | A subdomain you control, for example `asgard.example.com` |
| Internal DNS | Private records resolvable over the tailnet |
| Identity provider | An OIDC provider with separate human and workload identities |
| Approval surface | A user-visible interface reachable from every enabled Ody channel |

Also decide which features are in the first release:

- **Required:** Hermes, the official Hermes dashboard, AFFiNE, Mem0, Executor,
  Traefik, Tailscale, Komodo Periphery, 1Password secret provisioning, and
  Grafana Alloy.
- **Optional:** the community Hermes WebUI, Hermex, Signal, Pangolin-published
  routes, n8n/Huginn, and Muninn schedules.
- **Defer by default:** AFFiNE AI editing, unattended canonical writes,
  arbitrary browser automation, generic shell access, and destructive tools.

## 2. Prepare the three hosts

Use these host roles even if the underlying machines have different names:

| Host | Trust zone | Initial services |
| --- | --- | --- |
| `agent-01` | Assistant runtime | Hermes, official dashboard, optional community WebUI/Hermex backend, optional Signal gateway, Muninn worker |
| `knowledge-01` | Trusted knowledge | AFFiNE and its data services, Mem0 and its data services, controlled indexer |
| `tools-01` | Tool execution and untrusted collection | Executor, n8n, restricted connector/browser workers |

For each host:

1. Install all operating-system security updates.
2. Configure time synchronization and a consistent timezone.
3. Create a non-root administrative account and disable password-based remote
   administration after key-based access is confirmed.
4. Enable a host firewall with deny-by-default inbound rules.
5. Install Docker Engine and the Docker Compose plugin from Docker's official
   repository, following the current
   [Docker Engine installation guide](https://docs.docker.com/engine/install/).
6. Install Tailscale from the current
   [Linux installation guide](https://tailscale.com/docs/install/linux) and
   enroll the host with a tagged, non-personal identity.
7. Create an application root such as `/opt/asgard`, owned by the account used
   by Komodo Periphery.
8. Create separate persistent-data and backup-staging locations. Do not keep
   the only backup on the same filesystem as the application.
9. Install Grafana Alloy, but do not grant it access to application secret
   files. Grafana documents both
   [Linux](https://grafana.com/docs/alloy/latest/set-up/install/linux/) and
   [Docker](https://grafana.com/docs/alloy/latest/set-up/install/docker/)
   deployment methods.
10. Record the operating-system version, Docker version, Tailscale version,
    host identity, disk layout, and recovery access path.

**Asgard policy:** do not place a container-engine socket in an agent,
connector, browser, AFFiNE, Mem0, or n8n container. Traefik and Komodo
integration with Docker are privileged exceptions and should use the narrowest
documented access available.

### Host reachability

Build the following reachability before application deployment:

| Source | Destination | Purpose |
| --- | --- | --- |
| Administrator tailnet identity | All three hosts | Recovery and administration |
| `agent-01` | Heimdall endpoint on `tools-01` | Agent tool requests |
| `knowledge-01` indexer | Heimdall endpoint | Controlled reads and index writes |
| `tools-01` | Explicit downstream APIs | Tool execution |
| Pangolin connector | Selected Traefik routes | Human-facing access only |
| Grafana Alloy | Grafana Cloud endpoints | Telemetry export |

Everything else should be denied until a documented workflow requires it.
Tailscale ACLs reduce host-level reachability, but they do not prove which
container made a request. Heimdall still requires application-level caller
authentication.

## 3. Plan DNS and ingress

Example public and private names:

| Name | Service | Default exposure |
| --- | --- | --- |
| `chat.ody.asgard.example.com` | Ody web chat | Pangolin and/or Tailscale |
| `admin.ody.asgard.example.com` | Hermes administration | Tailscale only |
| `api.ody.asgard.example.com` | Hermes-compatible proxy/API | Private only |
| `mimir.asgard.example.com` | AFFiNE | Pangolin and/or Tailscale |
| `mem0.mimir.asgard.example.com` | Mem0 API | Private only |
| `heimdall.asgard.example.com` | Executor | Private only |
| `huginn.asgard.example.com` | n8n editor | Tailscale only |
| `hooks.huginn.asgard.example.com` | Selected n8n webhooks | Narrow, authenticated routes only |

These names are examples, not a required naming convention.

1. Create only the public records that must be reached through Pangolin.
2. Put internal API names in private DNS or make them resolvable only over
   Tailscale.
3. Configure one Traefik instance per host using the current
   [Traefik Docker provider documentation](https://doc.traefik.io/traefik/reference/install-configuration/providers/docker/).
4. Set Docker discovery to opt-in rather than exposing every container.
5. Place user-facing and administrative routers on separate entry points or
   otherwise enforce equivalent policy.
6. Publish Pangolin resources only after the corresponding private route works.
   Pangolin distinguishes public and private resources in its
   [resource model](https://docs.pangolin.net/manage/resources/understanding-resources).
7. Keep databases, container engines, Mem0, Executor, and internal Hermes APIs
   off public ingress.

**Asgard policy:** DNS existence, network reachability, TLS, user
authentication, and application authorization are five separate controls. Do
not treat any one of them as a substitute for the others.

## 4. Connect the hosts to Komodo

Komodo Core is assumed to exist outside the three Asgard hosts. Install only
Periphery on `agent-01`, `knowledge-01`, and `tools-01`.

1. Follow Komodo's current
   [Connect More Servers](https://komo.do/docs/setup/connect-servers)
   instructions for each host.
2. Prefer the documented system service when you need Periphery to survive
   Docker outages or restore the container stack after boot.
3. Give each server a stable Komodo name matching its architectural role.
4. Restrict Periphery's filesystem roots to the Asgard application and backup
   staging directories.
5. Verify Core-to-Periphery authentication before defining stacks.
6. Create one stack per independently upgradable application or tightly coupled
   upstream release set.
7. Keep deployment variables in environment templates containing secret
   references, not secret values.
8. Disable uncontrolled “latest commit” deployments. A deployment must refer
   to a reviewed release tag, image tag, or digest.

**Validation gate — deployment plane**

- Restart each host and confirm Periphery returns without manual intervention.
- Confirm Komodo can inspect and deploy only the intended host.
- Confirm a failed deployment preserves the previous Compose definition and
  produces a useful event in Grafana Cloud.
- Confirm no Komodo credential appears in a repository, rendered Compose file,
  or application log.

## 5. Establish version control and promotion

Create a deployment inventory before pulling application images:

```text
component
upstream repository or registry
release tag
image digest
configuration schema/revision
deployment date
backup identifier
validation result
rollback target
```

Use release tags for human readability and record the resolved digest for
reproducibility. Do not mix `latest` with pinned components in the same
application.

The update sequence is:

1. Detect a new upstream release.
2. Read release notes and migration instructions.
3. Create an immutable pre-change backup.
4. Update pins in a reviewed change.
5. Pull images without replacing the running deployment.
6. Run configuration and migration preflight checks.
7. Deploy one trust zone at a time.
8. Run the smoke tests in this guide.
9. Promote the release or roll back.
10. Append the deployment record and validation evidence.

Automatic nightly update checks are useful. Automatic, unreviewed installation
of every upstream release is not the default Asgard policy.

## 6. Provision secrets without giving agents a vault

1Password is the source of deployment secrets, not a general agent tool.

### Create service-account boundaries

Create separate service accounts or equivalent scoped identities for at least:

- deployment/bootstrap;
- Heimdall connector resolution;
- Ody runtime secrets;
- Mimir services;
- Huginn/n8n; and
- backup storage.

Grant each identity access only to the vaults and items it needs. The 1Password
CLI documentation recommends service accounts for least-privilege automation
and documents
[`op run`, `op read`, and `op inject`](https://developer.1password.com/docs/cli/secrets-scripts/).

### Choose the injection mode explicitly

There are two different patterns:

**One-shot injection**

- A trusted deployment or service launcher authenticates to 1Password.
- It resolves the small set of values required to start one service.
- It starts the process and discards the launcher environment.
- The service-account token is not mounted into the application container.

This is appropriate for secrets needed only at startup, but values passed as
container environment variables remain visible to administrators of the Docker
daemon and may appear in diagnostics. Treat the Docker control plane as
privileged.

**Runtime resolution**

- A trusted host-side broker resolves a credential only when a specific
  connector call is authorized.
- The raw value is injected into the outbound request outside the model-visible
  execution context.
- The agent, prompt, tool arguments, and tool result never receive the secret.

This is the desired design for Heimdall connector credentials.

**Validation required:** demonstrate the installed Executor and 1Password
integration end to end. If Executor does not have a verified runtime resolver,
use a small, audited host-side launcher or connector process and document the
exception. Do not hand Executor a broad 1Password vault browser, and never give
`OP_SERVICE_ACCOUNT_TOKEN` to Hermes, Muninn, n8n workflows, browser workers,
or model-generated code.

For unattended services, place the 1Password service-account token in an
operating-system credential facility or a root-readable service environment
outside the repository. Do not write the token into a Komodo environment
template, Compose file, or container image.

**Validation gate — secrets**

- An agent cannot invoke the 1Password CLI.
- An agent cannot read the launcher's process environment or credential file.
- A failed connector call does not return raw authorization headers.
- Logs and traces contain secret references or hashes, never secret values.
- Rotating one connector credential does not require changing agent
  configuration.
- Revoking one service account does not affect unrelated services.

## 7. Deploy `tools-01` first

Deploying the tool boundary before the agent prevents the first Hermes session
from acquiring direct credentials as a temporary shortcut.

### Executor / Heimdall

Executor describes itself as an MCP gateway and supports local, CLI, hosted,
and self-hosted modes. Start with the current
[Executor documentation](https://executor.sh/docs) and
[Executor project site](https://executor.sh/); do not infer self-hosted server
flags from a different release.

**Upstream fact:** Executor's
[self-hosted Docker guide](https://executor.sh/docs/hosted/docker) documents a
single-container server. Its container default binds to `0.0.0.0`. The first
person to register becomes the owner; after that, open signup closes and
additional users join through owner-created invitations. The same guide
documents a headless bootstrap method for creating the initial administrator.

Bootstrap is therefore a security-sensitive ceremony:

1. Select the upstream-supported deployment mode for the pinned release. A
   container is preferred when upstream supports the required functions. A
   tightly restricted system service is acceptable when connector execution or
   host-side secret resolution cannot safely run in the container.
2. During bootstrap, publish no Pangolin or public Traefik route. Bind the
   service to loopback or an isolated private network and use host-firewall
   rules to compensate if the container itself binds all interfaces.
3. Create the owner in an attended local session, or use the exact documented
   headless bootstrap method with one-shot secret injection.
4. Confirm the intended account is the owner, open signup is closed, and any
   invitation path is owner-controlled.
5. Back up the persistent data and generated keys described by the installed
   release.
6. Only then attach a private Tailscale/Traefik route and test authentication.
7. Import no tools by default. Treat every imported integration and operation
   as blocked until it is explicitly reviewed and allowed.
8. Add a read-only Mimir search path as the first integration.
9. Leave writes, destructive operations, private-network sandbox access, and
   general connector discovery disabled.
10. Route approvals to an interface that can return to the originating Hermes
    session.
11. Export redacted execution metadata to Grafana Cloud.

**Asgard policy:** per-workload catalogues, caller-to-connection selection,
argument policy, and cross-channel approval correlation are targets for a
custom Heimdall router/policy layer. They are not assumed to be documented
capabilities of the Executor Docker server.

The safe initial baseline is separate Executor instances, profiles, connector
processes, or endpoints for Ody, Muninn, and Huginn. Each baseline endpoint has
its own authentication, persistence, imported integrations, and downstream
account. Consolidate them only after a custom router has proved that it derives
the caller from authenticated transport, cannot be influenced by
model-generated identity fields, filters discovery as well as invocation, and
selects the correct downstream connection.

**Validation required:** prove the bootstrap, signup closure, endpoint
isolation, default-deny tool catalogue, connector selection, and approval path
for the exact Executor and router versions. If safe multiplexing is unavailable,
retain the separate-endpoint baseline.

### n8n / Huginn

n8n is optional for the first Ody-to-Mimir request but is the reference
implementation for Huginn. Use the official
[Docker installation documentation](https://docs.n8n.io/hosting/installation/docker/)
and pin an upstream release.

1. Give n8n a dedicated database and persistent data volume.
2. Put the editor behind Tailscale; do not expose it with public webhook routes.
3. Publish only specific webhook paths with their own authentication and rate
   limits.
4. Put fetch and browser work on a network with internet egress but no route to
   the knowledge databases or management plane.
5. Send captures to a controlled staging tool through Heimdall.
6. Do not grant n8n direct AFFiNE or Mem0 credentials.
7. Start without queue mode. Add the documented
   [queue mode](https://docs.n8n.io/hosting/scaling/queue-mode/) only when
   workload and failure-isolation requirements justify Redis and workers.

External content handled by n8n is untrusted. Store the source URL, capture
time, content hash, workflow ID, and collection policy with each capture.

### Grafana Alloy

Run Alloy on `tools-01` and send:

- container and service health;
- Executor request IDs, caller identity, tool name, decision, duration, and
  result classification;
- n8n workflow status and capture counts; and
- host capacity and disk alerts.

Do not send prompts, full tool arguments, raw captures, authorization headers,
or secret-bearing environment variables by default. Grafana's
[Docker monitoring example](https://grafana.com/docs/alloy/latest/monitor/monitor-docker-containers/)
is a starting point, not an Asgard-safe redaction policy.

## 8. Deploy `knowledge-01`

### AFFiNE / Mimir source of truth

Use AFFiNE's current release-matched self-hosted Compose definition from the
[AFFiNE repository](https://github.com/toeverything/AFFiNE) and follow its
self-host documentation for that release.

**Asgard policy:** all AFFiNE application, migration, worker, and supporting
containers that are intended to share a release must use the same pinned
release set. Do not combine a Compose file from `main`, a `latest` application
image, and an older migration container.

1. Create dedicated persistent volumes for the database, uploaded/blob data,
   and any other state named by the pinned upstream Compose definition.
2. Keep the database and cache on backend-only Docker networks.
3. Run the documented migration or pre-deploy step before serving traffic.
4. Verify the local administrative account and recovery path.
5. Back up both the database and blob/upload storage as one recoverable
    application state.

AFFiNE integration proceeds through three separate disabled-by-default gates.
Passing one gate does not validate the others.

#### Gate A — human OIDC authentication

**Validation required:** use only OIDC configuration documented for the exact
pinned AFFiNE release.

1. Keep OIDC disabled until local administration and recovery are proven.
2. Obtain the configuration schema and callback/redirect URI from that release's
   official documentation or running application; do not copy a path from this
   guide.
3. Register the exact external URL at the identity provider.
4. Test login, logout, token refresh, account linking, authorization, and
   recovery.
5. Preserve an emergency administrative path that does not depend on the same
   failing identity provider.

#### Gate B — agent connector or API

**Validation required:** select and pin an official API integration or a
specific third-party connector. Do not assume AFFiNE ships a native official
MCP server.

For the selected integration, record:

- source repository and exact version or commit;
- license and redistribution conditions;
- maintained API surface and authentication method;
- supported read and write operations;
- how Ody, Muninn, and Huginn obtain distinct downstream accounts;
- whether AFFiNE history records the intended author;
- rate-limit, retry, duplicate-write, and failure behavior; and
- backup, upgrade, and rollback impact.

Start with one separate, read-only connector endpoint for Ody. Add Muninn or
Huginn only after assigning a separate account and endpoint. Confirm that writes
made through any later connector appear in AFFiNE history as the intended
downstream user. If the integration records one shared identity, do not claim
per-agent authorship.

#### Gate C — experimental AFFiNE AI-to-Hermes compatibility

**Optional and validation required:** treat AFFiNE's AI editing surface and a
Hermes-compatible model proxy as an experimental compatibility project, not a
documented stable AFFiNE-to-Hermes integration.

Keep this path disabled during initial setup. Before enabling it, pin both
ends, document the protocol adapter, and test user identity propagation,
session isolation, streaming/error behavior, recursion prevention, data
retention, and prompt boundaries. The first test must use synthetic content
with all tools disabled. Do not enable tools until the same Heimdall and
approval policy used by other Ody interfaces is demonstrably enforced.

### Mem0 / rebuildable semantic index

Mem0 supports an open-source self-hosted server and documents a default
PostgreSQL/pgvector deployment in its
[open-source overview](https://docs.mem0.ai/open-source/overview).

1. Deploy Mem0 on a private Docker network with a dedicated database.
2. Pin the Mem0 server, embedding provider/model, vector-store schema, and
   dimensionality.
3. Disable direct public access.
4. Create separate API identities or enforce equivalent authorization at
   Heimdall.
5. Index only accepted AFFiNE content for canonical retrieval.
6. Store the AFFiNE workspace/page identifier, source revision, content hash,
   classification, status, and indexing time with every indexed object.
7. Make the indexer deterministic: replace all chunks for a page revision
   rather than accumulating ambiguous copies.
8. Build and test a full rebuild job before treating Mem0 as operational.

Mem0 is not authoritative. Search results identify relevant sources; important
answers must retrieve the current canonical content from AFFiNE. If AFFiNE and
Mem0 disagree, AFFiNE wins.

### Knowledge smoke test

1. Create a harmless test page in AFFiNE.
2. Run the controlled indexer.
3. Search Mem0 for a unique phrase from that page.
4. Confirm the result contains the correct AFFiNE identifier and revision.
5. Change the page, re-index it, and confirm old chunks are no longer returned.
6. Delete the Mem0 test index, rebuild it, and repeat the search.
7. Confirm Mem0 has no credentials that permit an AFFiNE write.

## 9. Deploy `agent-01`

### Hermes and the official dashboard

Hermes Agent's official project is
[`NousResearch/hermes-agent`](https://github.com/NousResearch/hermes-agent).
Use the current
[installation documentation](https://hermes-agent.nousresearch.com/docs/getting-started/installation)
and pin a release rather than following the repository's moving default branch.

The official
[Hermes web dashboard](https://hermes-agent.nousresearch.com/docs/user-guide/features/web-dashboard)
provides browser-based configuration, status, sessions, and chat. Upstream
warns that non-local binding is dangerous because the dashboard can expose
sensitive configuration. Place it behind Tailscale and an independent
authentication layer; do not publish it as the normal Ody interface.

1. Create a dedicated Ody operating-system account, Hermes home, state
   directory, and workspace.
2. Install the pinned Hermes release and the upstream extras required by the
   dashboard and selected messaging transports.
3. Configure the model provider through a scoped credential.
4. Configure a single Heimdall MCP endpoint as the ordinary external tool path.
5. Disable direct web, email, AFFiNE, API, shell, filesystem, and browser tools
   that duplicate Heimdall capabilities.
6. Start Hermes and its gateway under a boot-managed service or a pinned
   container supported by the chosen release.
7. Run `hermes doctor` and record its output with secrets redacted.
8. Verify a no-tool conversation before adding any connector.

### Scope the unavoidable local tools

Hermes may need local capabilities to create skills and perform a managed
self-update. Treat these as narrow exceptions:

- mount only a dedicated skills directory and an update staging directory;
- make all other host paths absent or read-only;
- do not mount the Docker socket, SSH directory, secret store, application
  data, or arbitrary home directory;
- allow only the documented updater and skill-management commands;
- require a human approval for an update;
- download into staging, verify the release, back up state, then activate it;
- keep a known-good pinned rollback target; and
- log the request ID, approved release, old version, new version, and result.

**Validation required:** Hermes' exact sandbox and tool configuration evolves.
Use the installed release's tool inspection commands and perform negative tests.
A directory named “workspace” is not a security boundary by itself.

### Community Hermes WebUI and Hermex

**Optional.** The community
[`nesquena/hermes-webui`](https://github.com/nesquena/hermes-webui) project
offers a richer browser experience and a backend used by Hermex. It is not the
official Hermes dashboard.

The WebUI's documentation notes that its default mode runs the Hermes agent
in-process and is coupled to Hermes internals. Follow its compatibility policy:
pin WebUI and Hermes together as a tested release pair, and do not assume it is
a thin frontend for an external Hermes API.

1. Choose an upstream-documented deployment mode.
2. Ensure all user interfaces reach the same intended Ody profile and policy.
3. Protect the WebUI with its own authentication and Pangolin or Tailscale.
4. Verify attachment paths, workspace mounts, session separation, and tool
   execution location.
5. Confirm approvals render and return correctly before enabling a sensitive
   tool.

Hermex is a native client, not a replacement server. Point it at the protected
WebUI endpoint only after the WebUI authentication and session behavior have
passed validation.

### Signal

**Optional.** Hermes documents Signal as a messaging gateway transport. Use the
current
[Signal integration guide](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/signal)
for the pinned Hermes release.

1. Use a dedicated Signal number or identity.
2. Store registration and transport credentials outside the repository.
3. Restrict the allowlist to explicitly authorized sender identifiers.
4. Verify an inbound message creates or resumes the expected Ody session.
5. Verify an outbound reply returns to the same Signal conversation.
6. Test `/stop`, reset/new-session behavior, and administrative command
   restrictions.
7. Trigger a harmless approval-required tool request and prove that approval
   can be completed from Signal or via a correlated protected approval link.
8. Reject any design that requires an unbound `/approve` command capable of
   approving a different pending action.

**Validation required:** Signal and the community WebUI must share the same
authorization semantics even if their presentation differs. Test concurrent
requests so an approval from one channel cannot be applied to another channel's
action.

### Muninn

Muninn is not a second user-facing assistant. It is an isolated, non-interactive
Hermes worker on `agent-01`.

1. Give Muninn its own Hermes profile, state directory, workload identity, and
   downstream AFFiNE account.
2. Do not share Ody's live conversation session or connector configuration.
3. Start with schedules disabled.
4. Run one manual, read-only review from a durable conversation checkpoint.
5. Write candidates only to an AFFiNE review inbox through Heimdall.
6. Enable an hourly incremental schedule after the manual run is idempotent.
7. Add a nightly consolidation schedule only after overlapping execution,
   checkpoint recovery, and duplicate suppression are tested.

See [Data flows](data-flows.md) for the conversation-review sequence.

## 10. Add observability without creating a secret mirror

Run Grafana Alloy on all three hosts and export only the telemetry needed to
operate the deployment.

Minimum useful signals:

- host CPU, memory, disk, inode, clock, and restart status;
- container health and restart count;
- HTTP request rate, error rate, and latency;
- correlated task, conversation, approval, tool, workflow, and deployment IDs;
- backup creation and restore-test outcomes;
- index freshness and Muninn checkpoint age; and
- version drift from the deployment inventory.

Redact or omit:

- prompts and conversation bodies;
- tool arguments containing user data;
- raw n8n captures;
- OAuth codes, cookies, bearer tokens, API keys, and authorization headers;
- environment dumps; and
- complete AFFiNE or Mem0 content.

Grafana Cloud is observability only. A dashboard event is not the authoritative
tool audit, an approval decision, or a backup.

## 11. Run end-to-end smoke tests

Run these tests after every initial deployment and material upgrade.

### Access and identity

- Ody chat is reachable only through the intended access plane.
- Hermes administration is unreachable without Tailscale and administrator
  authorization.
- Every enabled AFFiNE human authentication method passes login, logout,
  refresh, authorization, and recovery tests.
- Mem0, Executor, n8n editor, and databases are not reachable from the public
  internet.
- Each service presents the expected certificate and host name.

### Tool boundary

- Each agent reaches only its separate baseline Heimdall endpoint, or a custom
  router whose caller isolation has passed validation.
- Every imported tool is blocked until explicitly allowed for that endpoint.
- Ody can list only its allowed Heimdall tools; Muninn and Huginn receive
  independently controlled catalogues when enabled.
- A forged caller name in tool arguments cannot select another identity.
- A denied tool call has no downstream side effect.
- Ody cannot reach AFFiNE directly when Heimdall is stopped.
- No agent can read a raw third-party token.

### Knowledge

- A Mem0 search returns an AFFiNE page reference.
- Ody retrieves the canonical AFFiNE revision before answering.
- A stale Mem0 revision is detected.
- Rebuilding Mem0 from AFFiNE produces usable results.
- Huginn cannot promote a capture directly to canonical knowledge.
- Muninn can create a provenance-bearing candidate without silently replacing a
  canonical page.

### Interfaces and approvals

- A harmless request through the required official dashboard receives the
  intended policy.
- Repeat the same policy test for each optional interface that is enabled:
  community WebUI, Hermex, and Signal.
- Approval IDs are single-use, expire, and are bound to the user, originating
  request, tool, and normalized arguments.
- Concurrent approval requests cannot be crossed between channels or sessions.
- A timed-out or rejected approval produces no side effect.

### Operations

- Reboot each host and confirm required services return in dependency order.
- Stop one dependency at a time and confirm callers fail closed.
- Fill a test filesystem threshold and confirm alerting before exhaustion.
- Create an immutable backup, restore it to an isolated environment, and verify
  AFFiNE database and blob consistency.
- Roll back one pinned component and confirm the documented recovery path.

Record pass/fail evidence. A configuration becomes **verified** only for the
specific versions and test date in that record.

## 12. Production-enablement gates

Do not move to the next capability until the preceding gate passes:

| Gate | Required evidence |
| --- | --- |
| G0 — host baseline | Patched hosts, recovery access, firewall, Tailscale ACLs, disk alerts |
| G1 — private routing | Traefik routes work privately; internal APIs are not public |
| G2 — deployment | Komodo Periphery survives reboot; versions and rollback target recorded |
| G3 — secrets | Least-privilege 1Password identities; no agent or log can retrieve raw secrets |
| G4 — Heimdall read path | Private Executor bootstrap complete; separate Ody endpoint or validated custom router; default-deny catalogue; denial fails closed |
| G5 — canonical retrieval | Selected AFFiNE connector contract passes; Mem0 reference resolves to current AFFiNE content |
| G6 — interfaces | Web and enabled messaging channels share sessions and policy safely |
| G7 — approval | Single-use, bound approval works across every enabled channel |
| G8 — Muninn draft path | Checkpointed, idempotent review creates traceable drafts only |
| G9 — Huginn staging | Untrusted capture is isolated, deduplicated, and cannot self-promote |
| G10 — controlled writes | Per-agent downstream authorship and recovery are proven |
| G11 — resilience | Backup restore, reboot recovery, failure isolation, and rollback pass |

If a gate cannot be demonstrated, keep the dependent capability disabled and
document the exception. Do not compensate with a prompt instruction.

## 13. Handoff checklist for a coding agent

A coding agent assisting with this deployment should:

1. Read [Architecture](architecture.md), [Data flows](data-flows.md), and
   [Security model](security.md) before editing deployment files.
2. Inspect the pinned upstream release documentation rather than assuming
   configuration keys from model memory.
3. Produce placeholders and 1Password references, never real secrets.
4. Show the operator the exact hosts, routes, mounts, identities, and egress
   paths a change will add.
5. Stop for human authentication, OAuth consent, destructive actions,
   publication of a route, and approval-policy changes.
6. Validate rendered Compose configuration without printing secret values.
7. Run the applicable smoke tests and attach redacted evidence.
8. Update the deployment inventory and rollback instructions.
9. Leave an integration disabled when its identity or failure behavior has not
   been proven.

See [Agent-assisted installation](agent-assisted-install.md) for the complete
operator/agent contract.

## Next steps

- Read the detailed [Architecture](architecture.md).
- Review and implement the required
  [Integration contracts](integration-contracts.md).
- Follow the request, approval, indexing, and review sequences in
  [Data flows](data-flows.md).
- Apply the threat assumptions and negative tests in
  [Security model](security.md).
- Define updates, backups, restore testing, and incident handling in
  [Operations](operations.md).
- Use [Agent-assisted installation](agent-assisted-install.md) when delegating
  setup work to ChatGPT, Claude, Codex, or another coding agent.

## Official upstream references

- [Hermes Agent documentation](https://hermes-agent.nousresearch.com/docs/)
- [Hermes Agent repository](https://github.com/NousResearch/hermes-agent)
- [Community Hermes WebUI](https://github.com/nesquena/hermes-webui)
- [AFFiNE repository](https://github.com/toeverything/AFFiNE)
- [Mem0 open-source documentation](https://docs.mem0.ai/open-source/overview)
- [Executor documentation](https://executor.sh/docs)
- [Executor self-hosted Docker documentation](https://executor.sh/docs/hosted/docker)
- [n8n self-hosting documentation](https://docs.n8n.io/hosting/)
- [Traefik documentation](https://doc.traefik.io/traefik/)
- [Tailscale Docker documentation](https://tailscale.com/docs/features/containers/docker)
- [Pangolin documentation](https://docs.pangolin.net/)
- [Komodo documentation](https://komo.do/docs/intro)
- [1Password CLI documentation](https://developer.1password.com/docs/cli/)
- [Grafana Alloy documentation](https://grafana.com/docs/alloy/latest/)
- [Docker Engine documentation](https://docs.docker.com/engine/)
