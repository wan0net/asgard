# Security policy

Pantheon Blueprint is a reference architecture and documentation project for a
personal AI assistant. Security reports about this repository are welcome.

For deployment hardening and the project threat model, see
[docs/security.md](docs/security.md). For the distinction between documented
controls and verified deployment evidence, see
[docs/assurance.md](docs/assurance.md).

## Supported versions

Security fixes are made against the current `main` branch. Older commits,
forks, private deployment overlays, and modified installations are not
separately supported.

## Reporting a vulnerability

Do not publish a vulnerability, exploit details, credentials, private
deployment data, or sensitive logs in an issue, discussion, pull request, or
other public channel.

GitHub private vulnerability reporting is enabled for this repository. Use
**Report a vulnerability** in the repository's Security tab to create a private
report.

If that option becomes unavailable, open a minimal public issue asking the
maintainers to provide a private reporting channel. Include no technical details
beyond the affected Pantheon Blueprint document or component name and a
statement that the report is security-sensitive.

### Include privately

- A concise description of the issue and its impact
- The affected file, version, commit, or reference implementation
- Reproduction steps or a minimal proof of concept
- Required preconditions and trust boundary
- Suggested mitigation, if known
- Whether any real deployment or credential may already be affected

Use placeholders or redact material that is not necessary to reproduce the
issue. Never send live credentials when a synthetic example is sufficient.

## What is in scope

Examples include:

- A secret, private identifier, or credential accidentally committed to this
  public repository or included in a template
- Setup instructions that create an unsafe public exposure or materially weaken
  authentication, authorization, isolation, backup, or recovery
- A path that bypasses a security boundary in reference code or configuration
  supplied by Pantheon Blueprint
- Unsafe defaults in a Pantheon Blueprint integration
- Approval, identity, or audit guidance that permits unintended authority
- Documentation that incorrectly presents an unvalidated control as enforced

## What is normally out of scope

- Vulnerabilities solely in Hermes, Executor, AFFiNE, Mem0, n8n, Docker,
  Traefik, Tailscale, Pangolin, Komodo, 1Password, Grafana, or another upstream
  product
- Vulnerabilities introduced only by a private deployment's changes,
  credentials, access policy, or infrastructure
- Social engineering, denial-of-service testing, or testing against systems you
  do not own or have permission to assess
- Reports containing only automated scanner output without a demonstrated
  impact on Pantheon Blueprint guidance or supplied reference material

Report an upstream vulnerability to the upstream project's security process.
It is in scope here when Pantheon Blueprint's integration, configuration, or
documentation creates or materially worsens the vulnerability.

## Response process

The maintainers will aim to:

1. Acknowledge the report when it is seen
2. Reproduce and assess the impact
3. Identify affected guidance, templates, or reference code
4. Coordinate a fix and publication plan where appropriate
5. Credit the reporter if requested and safe to do so

No response or resolution SLA is promised. Please avoid public disclosure until
the maintainers have had a reasonable opportunity to investigate and mitigate
the issue.

## Good-faith research

The project welcomes research performed in good faith:

- Test only systems and accounts you own or are explicitly authorized to test.
- Minimize access to private data and stop if unintended data is encountered.
- Avoid privacy violations, service disruption, persistence, lateral movement,
  and destructive actions.
- Use the least intrusive proof needed to demonstrate the issue.
- Report promptly and protect details while remediation is underway.

The maintainers do not intend to pursue action against good-faith research that
follows this policy. This statement does not grant permission to test third-party
systems or override their terms, policies, or applicable law.

## If a credential or private value is exposed

Treat the value as compromised:

1. Revoke or rotate it through the authoritative provider immediately.
2. Disable affected connectors, routes, or workloads until the new credential
   is deployed.
3. Review provider, gateway, deployment, and repository audit records.
4. Remove the value from the current repository state without repeating it in
   public discussion.
5. Assess whether Git history, build logs, caches, artifacts, mirrors, or forks
   also contain it.
6. Rotate downstream credentials reachable through the exposed identity when
   the blast radius is uncertain.

Deleting a file or editing the latest commit does not make an exposed credential
safe. Rotation is the primary response.
