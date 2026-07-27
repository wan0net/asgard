# Readiness and assurance

Pantheon Blueprint is a reference design. It describes intended boundaries,
roles, and acceptance conditions; it is not evidence that those conditions
exist in any deployment. Installing a named product, rendering a configuration,
merging a change, or publishing a release can show progress, but none proves
that the installed versions, identities, routes, policies, and recovery paths
behave as intended. Evidence comes from repeatable checks against a specific
deployment, recorded separately and reviewed under the deployment's own
controls.

This page is the central index for readiness language. It deliberately does
not duplicate detailed test procedures. Component pages link here for the
meaning of readiness; domain documents retain the tests that only make sense in
their context: [Security](security.md), [Integration contracts](integration-contracts.md),
[Transcript outbox](transcript-outbox.md), and [Backups](backups.md).

## Claim labels

Use these labels consistently when reading or writing architecture material:

- **Upstream fact:** behaviour documented by an upstream project for a stated
  release. It does not prove the local configuration or surrounding controls.
- **Pantheon Blueprint policy:** a requirement of this reference design. A
  product may not enforce it on its own.
- **Optional:** a capability or component that is not required for the
  foundational path. Optional never means safe to enable without its gates.
- **Validation required:** behaviour a deployment must demonstrate for its
  exact versions, configuration, identities, and environment before relying on
  it as a control.

Labels distinguish the source and strength of a claim; they are not maturity
states and are not a record of a passed test.

## Maturity and lifecycle

Every capability should be described with one of these exact maturity states:

| State | Meaning | What it does not mean |
| --- | --- | --- |
| **Reference design** | The intended capability, constraints, and required evidence are documented. | It is built, configured, enabled, or safe to rely on. |
| **Implemented** | The deployment has a concrete, versioned implementation of the documented design or an approved equivalent. | Its behaviour has been demonstrated in the target environment. |
| **Verified** | Recorded evidence shows the required checks passed for a stated scope, versions, configuration, and test date. | The result automatically applies after a change, to another environment, or to an untested dependent capability. |

Do not replace these states with release terminology. **Merged** means a change
entered a source branch. **Released** means an artifact or version was made
available. **Deployed** means that artifact or configuration was applied to a
target environment. **Verified** means the relevant evidence was collected and
accepted for that target scope. These are distinct lifecycle states and may
occur in that order, but none implies the next. A merged or released design can
remain unimplemented; a deployment can remain unverified; a verified result can
be invalidated by a relevant change.

State claims need a bounded subject. Prefer “G5 is Verified for the pinned
connector and configuration recorded on this date” over “retrieval is secure.”
When an exception is accepted, record the affected capability, compensating
restriction, owner, review date, and the fact that the capability remains below
its normal gate.

## Readiness gates

The gates below are the common sequence for enabling capability. They are a
readiness index, not a claim that any gate has passed. A later gate depends on
the relevant earlier gates; if evidence is missing or fails, keep the dependent
capability disabled or reduced to its previously verified scope. A prompt,
documentation statement, or alert does not compensate for a failed control.

| Gate | Capability | Readiness condition |
| --- | --- | --- |
| G0 | Host baseline | Patched hosts, recovery access, firewall, private-overlay access rules, and disk alerts are established. |
| G1 | Private routing | Private routes work and internal APIs are not unintentionally public. |
| G2 | Deployment | The deployment plane recovers after reboot; pinned versions and a rollback target are recorded. |
| G3 | Secrets | Least-privilege secret identities are in use; agents and logs cannot retrieve raw secret values. |
| G4 | Heimdall read path | The private gateway bootstrap, caller separation or validated routing, default-deny catalogue, and failure-closed denial path are in place. |
| G5 | Canonical retrieval | The selected canonical connector contract passes and a retrieval reference resolves to current canonical content. |
| G6 | Interfaces | The web interface and every enabled messaging interface preserve sessions and policy safely. |
| G7 | Approval | A single-use approval binds the user, originating request, tool, normalized arguments, and expiry across enabled interfaces. |
| G8 | Muninn draft path | Checkpointed, idempotent review produces traceable drafts only. |
| G9 | Huginn staging | Untrusted capture is isolated, deduplicated, and unable to promote itself. |
| G10 | Controlled writes | Per-role downstream authorship, audit, recovery, and the required approval conditions are demonstrated. |
| G11 | Resilience | Restore, reboot recovery, failure isolation, and rollback checks pass. |

G0–G5 establish the bounded read foundation. G6–G9 add user-facing and
workflow paths only after their own evidence exists. G10 is deliberately later:
the ability to write durable or external state needs stronger attribution and
recovery evidence than retrieval. G11 is a continuing requirement, not a final
one-time sign-off. This page owns the gate matrix; consult
[Getting started](getting-started.md) for the deployment sequence.

## Role-specific check index

The following is the central index of role-specific readiness checks. It states
requirements only; it does not report results. Use the linked role and domain
material to define the test fixtures, negative cases, and evidence for a
particular deployment.

| Role | Check before enabling dependent capability | Primary detail |
| --- | --- | --- |
| [Odine](gods/odine.md) | Preserve channel identity and conversation isolation; prevent direct downstream access and cross-workload connection selection; keep credentials out of context and logs; bind approvals; confirm canonical reads after retrieval ranking and a canonical rebuild; fail without broader fallback authority. | [Role page](gods/odine.md); [Security](security.md); [Integration contracts](integration-contracts.md) |
| [Mimir](gods/mimir.md) | Omit unauthorized classifications from results; resolve every result to its indexed canonical page and revision; rebuild an empty retrieval index from canonical sources; block writes until downstream identity and attribution pass. | [Role page](gods/mimir.md); [Integration contracts](integration-contracts.md); [Backups](backups.md) |
| [Muninn](gods/muninn.md) | Keep schedules and transcript handling off until manual canaries prove isolated profile, checkpoint, and connector identity; gateway-only access; ordered leases and compare-and-swap checkpoints; idempotent replay; and failure-closed draft handling. | [Role page](gods/muninn.md); [Transcript outbox](transcript-outbox.md); [Integration contracts](integration-contracts.md) |
| [Huginn](gods/huginn.md) | Use a bounded canary to show one staged capture and idempotent event for changed content, no duplicate for unchanged content, no cross-connection access or private/canonical reach, and no premature event on failure. | [Role page](gods/huginn.md); [Security](security.md); [Integration contracts](integration-contracts.md) |
| [Heimdall](gods/heimdall.md) | Ensure unauthorized tools are absent and denied at invocation; prevent argument or target changes from selecting a connector; bind exact expiring approvals; retain action records through failures; test bypass, cross-workload access, unsafe inputs, result injection, replay, and failure-closed behaviour against pinned releases. | [Role page](gods/heimdall.md); [Security](security.md); [Integration contracts](integration-contracts.md) |

The checks overlap by design. For example, a gateway check may support G4,
G7, and G10, but its evidence must state exactly which scenario, release, and
scope it covers. A role's Reference design or Implemented state is not a reason
to mark any gate Verified.

## Evidence records

Store evidence outside this documentation repository in the deployment's
protected audit, change, or incident system. Keep repository references
redacted and non-sensitive. A minimal record contains:

```text
record ID; date and timezone; environment and scope
capability and gate(s); maturity-state decision; operator or approved automation
desired-state revision; component versions and image digests; configuration/policy identifiers
test or drill identifiers; expected and actual result; pass/fail decision
evidence location and retention class; approvals or exceptions; rollback/restore outcome
reviewer; follow-up actions and revalidation trigger
```

Do not store secret values, credentials, personal content, sensitive network
details, or raw logs in the record unless the protected evidence system and its
retention policy explicitly permit them. A record should instead reference a
controlled evidence location and identify the redaction applied. Changes to
versions, configuration, routes, identities, policies, connectors, backup
paths, or relevant dependencies should trigger a scope review and, where
needed, revalidation.

## Using this page

Role and component pages should link here when they state a policy or a
validation requirement, rather than restating lifecycle semantics. Keep
domain-specific acceptance criteria in the relevant domain document. Keep security boundaries and
negative tests in [Security](security.md); cross-product operations and
acceptance contracts in [Integration contracts](integration-contracts.md);
transcript-export compatibility and redaction checks in [Transcript outbox](transcript-outbox.md);
and recovery-point, restore, and retention checks in [Backups](backups.md).

This arrangement makes a simple assurance rule possible: architecture explains
what must be true, implementation shows what was built, and protected evidence
shows what was actually tested. Only the last can support a Verified claim.
