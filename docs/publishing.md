# Publishing the documentation

Asgard uses MkDocs with the Material theme to render this repository's complete
documentation set. A small build helper stages the root-level project documents
beside `docs/` in a temporary directory. This keeps source-relative links
working and includes the extensionless `LICENSE` as a rendered page without
committing a duplicate copy.

## Local setup

Use Python 3 and an isolated virtual environment from the repository root:

```bash
python3 -m venv .venv-docs
. .venv-docs/bin/activate
python -m pip install --upgrade pip
python -m pip install --requirement requirements-docs.txt
```

The requirements file pins the documentation tools used in continuous
integration. The virtual environment is local working state and must not be
committed.

## Build and preview

Build the same strict production site used by continuous integration:

```bash
python scripts/build-docs.py build
```

The helper prints the generated site's temporary output directory. To select a
known disposable location instead:

```bash
python scripts/build-docs.py build --site-dir /tmp/asgard-site
```

Preview the staged documentation at `http://127.0.0.1:8000/`:

```bash
python scripts/build-docs.py serve
```

The preview stages a snapshot of the source documents. Restart it after editing
documentation so the temporary source tree is refreshed. See the
[MkDocs documentation](https://www.mkdocs.org/getting-started/) for the
underlying build and preview behavior.

## GitHub Pages workflow

The Pages workflow runs for pushes to `main` and can also be started manually.
Its build job installs the pinned documentation dependencies, stages the public
sources, runs MkDocs in strict mode, and uploads the generated site as a Pages
artifact. The dependent deployment job publishes only that artifact to the
`github-pages` environment.

Maintainers must enable one repository setting before the workflow can publish:

> **Settings > Pages > Build and deployment > Source: GitHub Actions**

Enabling that setting and merging the workflow causes the generated
documentation to be published publicly. This repository configuration does not
claim that Pages has already been enabled or that a deployment has occurred.
GitHub documents the mechanism in
[Using custom workflows with GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).
