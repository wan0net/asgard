# Heimdall

![Heimdall portrait](../assets/avatars/heimdall.png)

Heimdall is Asgard's logical security boundary and tool choke point, not a
single product. Executor is the target enforcement point, supported by Asgard
policy, workload authentication, approval, and audit controls. This is a
reference design: those controls require deployment validation.

## At a glance

| Aspect | Description |
| --- | --- |
| Function | Mediate general agent and workflow tool discovery and execution. |
| Reference tool(s) | Executor plus Asgard policy, approval, identity-selection, and audit controls. |
| Authority | Derives the caller, permits capabilities, selects scoped connectors, and records action evidence; downstream services retain their own authorization. |
| Trust zone | Tools and execution boundary. |

## What Heimdall does

**Asgard policy:** Heimdall authenticates the workload caller and limits its
tool catalogue. It evaluates the requested semantic operation, normalized
arguments, target, classification, and approval state. It selects a fixed,
caller-scoped connector identity server-side; model-generated input cannot
choose credentials or another workload's connection.

Heimdall filters tool results before returning them to a model, since output
can contain sensitive data or prompt injection. It also records authoritative
action evidence that correlates caller, policy, approval, connector, action,
and result without recording secrets. 1Password provisions approved secrets to
runtimes; agents do not receive general vault access or raw connector secrets.
Grafana receives only redacted operational telemetry and is neither an
authorization engine nor the authoritative action record.

## How Heimdall interacts

Ody, Muninn, and Huginn send general tool requests through Heimdall using their
own authenticated workload identities. Heimdall mediates their scoped access to
connectors, workers, Mimir, and canonical knowledge operations. It must fail
closed: a denial, unavailable connector, or Heimdall failure never triggers a
direct-connector fallback.

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
