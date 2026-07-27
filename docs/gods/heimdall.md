# Heimdall

![Heimdall portrait](../assets/avatars/heimdall.png)

Heimdall is Asgard's logical security boundary and tool choke point, not a
single product. Executor is the target enforcement point for agent tool
discovery and invocation. It must be paired with the controls Executor does
not supply alone: Asgard policy, workload authentication, approvals,
identity-selection, result filtering, and authoritative action-record
adapters. 1Password provides only the minimum approved secrets to runtimes,
without agent vault browsing; Grafana Alloy/Cloud provides redacted telemetry
and observability only, not authorization or the authoritative action audit.
This is a reference design: those controls and integrations require deployment
validation.

## At a glance

| Aspect | Description |
| --- | --- |
| Function | Mediate general agent and workflow tool discovery and invocation through Executor. |
| Reference tool(s) | Executor for enforcement; 1Password for minimum secret provisioning; Grafana Alloy/Cloud for redacted telemetry; plus Asgard policy, approval, identity-selection, result-filtering, and authoritative action-record adapters. |
| Authority | Derives the caller, permits capabilities, selects scoped connector identities, filters results, and records action evidence; downstream services retain their own authorization. |
| Trust zone | Tools and execution boundary. |

## What Heimdall does

**Asgard policy:** Executor enforces Heimdall's mediated tool discovery and
invocation path. Asgard policy and workload authentication authenticate the
caller and limit its tool catalogue. They evaluate the requested semantic
operation, normalized arguments, target, classification, and approval state.
Identity-selection selects a fixed, caller-scoped connector identity
server-side; model-generated input cannot choose credentials or another
workload's connection.

Result-filtering prevents sensitive data or prompt injection in tool output
from reaching a model. Authoritative action-record adapters record evidence
correlating caller, policy, approval, connector, action, and result without
recording secrets. 1Password provisions approved secrets only to the runtime;
agents do not receive general vault access or raw connector secrets. Grafana
Alloy/Cloud receives only redacted operational telemetry and is neither an
authorization engine nor the authoritative action record.

## How Heimdall interacts

Ody, Muninn, and Huginn send general tool requests through Heimdall using
distinct authenticated workload identities. Executor enforces their discovery
and invocation path while the surrounding controls authenticate the caller,
evaluate policy and approvals, select the scoped connector identity, filter
results, and preserve authoritative action records. Heimdall mediates their
scoped access to connectors, workers, Mimir, and canonical knowledge
operations. It must fail closed: a denial, unavailable connector, or Heimdall
failure never triggers a direct-connector fallback or identity fallback.

## What Heimdall does not do

Heimdall does not make Executor a complete sandbox, replace downstream
authorization, or turn network reachability into permission. It does not let
agents browse 1Password, allow Grafana to approve or resume actions, or trust
tool output without filtering. It does not treat a shared connector catalogue
as safe merely because a model is asked to select the right connection.

## Validation

**Validation required:** Before enabling dependent capabilities, demonstrate
that unauthorized tools are absent from discovery and fail at invocation;
arguments and targets cannot change connector selection; approvals bind one
exact, expiring action; and action records survive the required failure cases.
Test direct bypass paths from every agent, cross-workload access, malformed or
unsafe targets, result-injection handling, approval replay, and failure-closed
behavior. Validate Executor and any supporting adapters against pinned releases;
these tests are required evidence, not claims already established here.

## See also

- [Architecture](../architecture.md)
- [Tools, capabilities, and interaction boundaries](../tooling.md)
- [Security model](../security.md)
- [Data flows](../data-flows.md)
- [Workload authentication to Heimdall](../integration-contracts.md#2-workload-authentication-to-heimdall)
- [Audit record sink](../integration-contracts.md#11-audit-record-sink)
