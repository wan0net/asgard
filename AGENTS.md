# Instructions for agents

## Repository purpose

This is the public Pantheon Blueprint reference architecture. It documents a
self-hosted personal AI system with one user-facing assistant and separated
knowledge, curation, collection, and tool-execution capabilities.

Work here must remain reusable, public-safe, and independent of any one private
deployment.

## Before making a change

1. Read [README.md](README.md).
2. Read the documents relevant to the requested change:
   - [Architecture](docs/architecture.md)
   - [Getting started](docs/getting-started.md)
   - [Data flows](docs/data-flows.md)
   - [Security model](docs/security.md)
   - [Operations](docs/operations.md)
3. Read [CONTRIBUTING.md](CONTRIBUTING.md) and
   [SECURITY.md](SECURITY.md).
4. Inspect the current working tree and preserve unrelated user changes.
5. Define one bounded concern, its affected files, and its validation.

Do not broaden a task merely because adjacent improvements are possible.

## Public-safety rules

Never add or reproduce:

- real domains, hostnames, IP addresses, email addresses, phone numbers, user
  IDs, account IDs, or organization identifiers;
- passwords, tokens, API keys, cookies, OAuth secrets or codes, private keys,
  recovery material, or secret-bearing environment values;
- real 1Password vault names, item names, secret references, service-account
  details, or internal access structure;
- private repository URLs, dashboard URLs, storage bucket names, monitoring
  tenant details, or internal ticket references;
- private network diagrams, firewall exports, workload mappings, logs,
  conversations, knowledge content, database samples, or deployment evidence;
  or
- copied configuration whose surrounding context may identify a private
  deployment.

Use obvious placeholders:

```text
pantheon.example.com
192.0.2.10
<WORKLOAD_IDENTITY>
<SECRET_REFERENCE>
<VERSION>
<IMAGE_DIGEST>
<PRIVATE_CONFIG_REPO>
```

A private Git repository is not a secret manager. Never commit decrypted
secrets anywhere.

## Relationship to `pantheon-private`

Do not read, search, clone, or copy from `pantheon-private` unless the user
explicitly authorizes that access for the current task.

When authorized:

1. Treat all private content as sensitive by default.
2. Identify the general architectural lesson, not the private implementation
   text.
3. Synthesize a new public-safe explanation from first principles and official
   upstream sources.
4. Replace every identifier and value with a generic placeholder.
5. Do not transfer private deployment evidence, exact inventory, account
   structure, exception records, logs, screenshots, commands containing real
   targets, or repository history.
6. Run privacy and secret checks before presenting or committing the result.

Authorization to consult the private repository is not authorization to
publish from it.

## Source and claim discipline

When changing statements about current product behavior:

- use official upstream documentation, repositories, release notes, or
  specifications;
- verify that the source applies to the version or release family being
  discussed;
- link the official source near the relevant guidance;
- avoid copying long upstream procedures that will become stale; and
- do not rely on model memory, search-result summaries, community posts, or a
  private deployment as the sole source.

Label claims clearly:

- **Upstream fact:** documented behavior of an upstream product.
- **Pantheon Blueprint policy:** a requirement or recommendation of this
  architecture.
- **Validation required:** behavior a deployment must demonstrate before
  relying on it.
- **Optional:** a nonessential component or integration.

Use [Readiness and assurance](docs/assurance.md) for maturity labels, validation
gates, and evidence-record definitions.

Do not describe a feature as implemented, enforced, self-healing, secure, or
verified without a reproducible acceptance test and version-specific evidence.

Never invent:

- configuration keys;
- callback or redirect paths;
- image names or tags;
- command-line options;
- API routes;
- environment variables;
- license terms; or
- compatibility claims.

Use a placeholder and link upstream documentation when stable syntax cannot be
verified.

## Where changes belong

This public repository may contain:

- architecture and operations documentation;
- generic diagrams and workflows;
- validation procedures;
- secret-free examples;
- reusable templates with placeholders; and
- implementation-neutral policies.

Deployment mutations belong in a private overlay unless the task explicitly
adds or improves a generic public template.

Do not place live desired state, rendered configuration, secrets, deployment
records, private identities, or operational evidence here.

## Writing and diagrams

- Use plain language and explicit trust boundaries.
- Keep product names separate from architectural capability names.
- Make authority clear: for example, AFFiNE is canonical and Mem0 is
  rebuildable.
- State failure behavior and negative requirements, not only the happy path.
- Keep cross-links relative within the repository.
- Use Mermaid for architecture, sequence, state, and data-flow diagrams.
- Quote Mermaid labels containing punctuation or parentheses.
- Label arrows with the data, identity, or authority crossing the boundary.
- Use subgraphs for trust zones.
- Do not rely on color alone.
- Keep prose consistent with every changed diagram.

## Change discipline

- Make one bounded change per task or pull request.
- Do not reformat unrelated files.
- Preserve existing user changes.
- Prefer small, reviewable diffs.
- Update related links or diagrams only when required for consistency.
- Do not perform deployment, OAuth, account, DNS, secret, or infrastructure
  mutations while editing public documentation.

Stop and request human direction before:

- OAuth login or consent;
- creating, rotating, revealing, or moving a secret;
- publishing a service, DNS record, route, repository, or artifact;
- deleting, overwriting, migrating, or otherwise performing a destructive
  action;
- enabling a tool or write permission;
- modifying a live or private deployment; or
- choosing a missing material option such as license, identity model, retention
  policy, public exposure, or authoritative data source.

## Validation

Before handoff:

1. Review the complete diff.
2. Confirm only intended files changed.
3. Run the repository's configured Markdown checks.
4. Run `git diff --check`.
5. Check fenced blocks and render changed Mermaid diagrams.
6. Validate internal links.
7. Confirm external links resolve to official sources.
8. Run a repository secret scanner when available.
9. Search for private identifiers, domains, addresses, emails, phone numbers,
   vault/item names, tokens, and private repository links.
10. Confirm all examples use placeholders.
11. Verify claims are labelled and acceptance tests are stated.

Generic check shape:

```text
secret-scan <REPOSITORY>
privacy-pattern-scan <REPOSITORY>
markdown-lint <CHANGED_MARKDOWN>
link-check <CHANGED_MARKDOWN>
render-mermaid <CHANGED_DIAGRAMS>
git diff --check
```

These names are illustrative. Use the tools configured by the repository; do
not invent or commit a new checking framework unless requested.

If a check cannot run, state that clearly and perform the strongest available
manual verification.

## Expected handoff

Report:

1. the outcome;
2. files changed;
3. the architectural or operational decision captured;
4. official sources used for changed product behavior;
5. validation performed and its result;
6. assumptions, unvalidated integrations, or disabled capabilities;
7. privacy or security considerations; and
8. the next safe step, if work remains.

Do not include secrets, private values, or sensitive evidence in the handoff.
