# Contributing to Asgard

Thank you for helping improve Asgard.

Asgard is a documentation-first reference architecture for a self-hosted
personal AI system. Contributions should make the design easier to understand,
deploy, validate, or operate without presenting one private deployment as a
universal solution.

## Public-safety rules

Never submit:

- real domains, hostnames, IP addresses, email addresses, phone numbers, or
  account identifiers;
- API keys, tokens, passwords, cookies, private keys, OAuth secrets, recovery
  material, or secret-bearing logs;
- real 1Password vault names, item names, secret references, service-account
  tokens, or organization details;
- links to private repositories, dashboards, object-storage buckets, incidents,
  deployment systems, or monitoring tenants;
- conversation content, knowledge-base content, tool arguments, database
  samples, or unredacted deployment evidence; or
- private network diagrams, firewall exports, access-control lists, or identity
  mappings.

Use obvious placeholders such as:

```text
asgard.example.com
192.0.2.10
<WORKLOAD_IDENTITY>
<SECRET_REFERENCE>
<VERSION>
<IMAGE_DIGEST>
<PRIVATE_CONFIG_REPO>
```

Before opening a pull request, inspect both the working tree and Git history.
Deleting a secret from the latest commit does not remove it from earlier
commits. If sensitive material is committed, stop and follow
[SECURITY.md](SECURITY.md).

## Label claims precisely

Documentation must distinguish:

- **Upstream fact:** behavior supported by current official project
  documentation.
- **Asgard policy:** a requirement or recommendation of this reference
  architecture.
- **Validation required:** behavior that a real deployment must demonstrate
  before relying on it.
- **Optional:** a component or integration that is not necessary for the
  minimal architecture.

Do not describe a control as implemented or verified merely because a Compose
file, prompt, policy, or product feature exists. State the versions, assumptions,
and acceptance test required to support the claim.

## Scope

Good contributions include:

- correcting or clarifying architecture and data flows;
- adding safe deployment, recovery, migration, or validation procedures;
- documenting a replaceable implementation for an existing capability;
- improving threat assumptions and negative tests;
- updating an upstream link or compatibility constraint;
- adding generic, secret-free configuration examples; and
- reporting a reproducible documentation or integration gap.

Deployment-specific overlays, live credentials, private operating records, and
product promotion without technical evidence are out of scope.

## License for contributions

Asgard is licensed under
[Creative Commons Attribution-NonCommercial 4.0 International](LICENSE).
Unless a software subtree contains an explicit, separate license notice,
submitting a contribution means you agree to license that contribution under
CC BY-NC 4.0.

A contribution made entirely within a separately licensed software subtree is
submitted under the license stated in that subtree. Clearly identify any
third-party material and its license; do not submit material whose terms are
incompatible with this repository or the applicable subtree.

## Pull requests

Keep one concern per pull request. A focused change is easier to validate,
review, revert, and publish safely.

Include:

1. the problem being solved;
2. whether the change is an upstream fact, Asgard policy, optional design, or
   validation requirement;
3. the affected trust boundary and data flow;
4. official upstream references;
5. security and privacy implications;
6. acceptance tests or review checks; and
7. migration or rollback implications, when applicable.

Update related diagrams and cross-links in the same pull request when necessary
to keep the documentation internally consistent.

A Developer Certificate of Origin sign-off is not required.

## Proposing a component or version change

Names in the architecture represent capabilities; products are replaceable
implementations. A proposal to add or replace a component should document:

| Question | Required information |
| --- | --- |
| Capability | Which architectural responsibility it implements |
| Trust boundary | Where it runs and what it can reach |
| Identity | How callers and downstream accounts remain distinguishable |
| Credentials | How secrets are provisioned without entering agent context |
| Authority | Which data is canonical and which data is rebuildable |
| Failure behavior | Whether it fails open, fails closed, retries, or duplicates work |
| Operations | Version pinning, health checks, backup, restore, update, and rollback |
| Licensing | Applicable upstream license and redistribution constraints |
| Maturity | Stable, experimental, optional, or unvalidated |
| Evidence | Official documentation and reproducible acceptance tests |

For a version update, also include:

- old and proposed versions;
- immutable image digest where available;
- release notes and migration guidance;
- compatibility with coupled components;
- configuration or schema changes;
- pre-change backup requirements;
- rollback boundary; and
- smoke and negative test results using public-safe fixtures.

Do not submit raw moving-branch or `latest` updates as deployment guidance.

## Acceptance tests

Tests should cover the smallest relevant set of:

- rendered configuration contains only expected routes, mounts, networks, and
  privileges;
- unauthorized services cannot bypass Heimdall;
- caller identity cannot select another caller's downstream connector;
- denied or expired approvals have no side effect;
- canonical AFFiNE content remains authoritative over Mem0;
- indexes can be rebuilt from canonical content;
- backup objects use unique keys and the writer cannot delete old objects;
- reboot, dependency failure, rollback, and restore behavior match the claim;
- logs and telemetry exclude secrets and private content; and
- public documentation contains no deployment-specific values.

Use synthetic users, fixtures, domains, identities, and data in all published
test evidence.

## Documentation style

- Prefer plain language and explicit trust boundaries.
- Define acronyms and product-specific terms.
- Link to official upstream documentation for current behavior.
- Avoid copying long upstream procedures that will become stale.
- Do not invent configuration keys, callback paths, image tags, or command-line
  options.
- Use relative links for files in this repository.
- Keep headings descriptive and tables readable without special rendering.
- Wrap commands and examples in fenced code blocks with an appropriate language
  tag.

### Mermaid diagrams

- Use Mermaid for architecture, sequence, state, and data-flow diagrams.
- Quote labels containing punctuation or parentheses.
- Show trust zones with subgraphs.
- Label arrows with the data or authority crossing the boundary.
- Distinguish supporting flows from ordinary tool calls when relevant.
- Keep diagrams useful in monochrome; do not rely on color alone.
- Update accompanying prose when a diagram changes.

## Local checks

Before opening a pull request:

1. Run a repository-wide secret scanner.
2. Search for private domains, addresses, emails, phone numbers, vault/item
   names, account IDs, tokens, and private repository URLs.
3. Review the diff and staged files manually.
4. Run the repository's Markdown formatter or linter when configured.
5. Check for trailing whitespace and malformed fenced blocks.
6. Render Mermaid diagrams.
7. Validate internal links and confirm external links resolve to official
   sources.
8. Confirm examples contain placeholders only.

Generic check shape:

```text
secret-scan <REPOSITORY>
privacy-pattern-scan <REPOSITORY>
markdown-lint <MARKDOWN_FILES>
link-check <MARKDOWN_FILES>
git diff --check
```

Use the actual tools selected by the repository; these names are illustrative,
not commands supplied by Asgard.

## Security reports

Do not open a public issue or pull request for a suspected vulnerability,
credential exposure, private-data leak, or bypass of an intended security
boundary. Follow the responsible-disclosure process in
[SECURITY.md](SECURITY.md).
