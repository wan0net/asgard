# Pantheon Blueprint software

This directory contains reusable, deployment-neutral implementations of
Pantheon Blueprint capabilities. Software here is public source, not production
desired state and not evidence that any deployment has passed its acceptance
tests.

## Public-safety boundary

Software and tests in this directory must use synthetic identities and
placeholder infrastructure. They must not contain private repository names,
secret-manager references, live domains, account identifiers, deployment
inventory, credentials, logs, or operational evidence.

Private deployments consume reviewed releases or immutable container digests
and retain their environment-specific configuration in a separate private
repository.

## Components

- [Browser egress proxy](browser-egress-proxy/) denies private, loopback,
  metadata, reserved, and DNS-rebinding destinations.
- [Executor launcher](executor-launcher/) assembles a pinned upstream Executor
  image and injects runtime secrets from files immediately before execution.
- [Huginn handoff](huginn-handoff/) validates untrusted captures before placing
  them in an immutable, leased outbox.
- [Email control](email-control/) enforces authenticated-sender and thread-bound
  reply rules over validated captures.
- [Maintenance-session authority](maintenance-session/) records explicit,
  time-bounded maintenance scope and issues narrow, expiring grants.
- [Komodo maintenance adapter](komodo-maintenance-adapter/) binds one configured
  deployment procedure to an exact maintenance-session scope.

## License

Unless a component states otherwise, this directory is licensed under the
[BSD 3-Clause License](../LICENSES/BSD-3-Clause.txt). Third-party source and
dependencies retain their own licences.
