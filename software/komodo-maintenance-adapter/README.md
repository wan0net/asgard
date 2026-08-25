# Komodo maintenance adapter

This service exposes one narrowly configured Komodo procedure behind an active
maintenance-session claim. It authenticates its caller, verifies that every
scope field exactly matches runtime configuration, claims the corresponding
grant, and only then calls Komodo. It has no generic Komodo proxy or arbitrary
procedure endpoint.

The adapter fails closed when its procedure, authority URL, Komodo URL, or any
fixed-scope field is absent. Deployment identities, repository names, service
names, targets, topology, and credentials therefore remain private runtime
configuration rather than public source defaults.

## Configuration

| Variable | Purpose |
| --- | --- |
| `KOMODO_URL` | Required HTTPS base URL for Komodo |
| `MAINTENANCE_AUTHORITY_URL` | Required HTTP(S) URL of the exact claim endpoint |
| `KOMODO_PROCEDURE` | Required fixed procedure identifier |
| `MAINTENANCE_SCOPE_REPOSITORY` | Required fixed repository scope |
| `MAINTENANCE_SCOPE_SERVICE` | Required fixed service scope |
| `MAINTENANCE_SCOPE_ACTION` | Required fixed action scope |
| `MAINTENANCE_SCOPE_TARGET` | Required fixed deployment target scope |
| `KOMODO_MAINTENANCE_SECRET_DIR` | Secret-file directory; defaults to `/run/komodo-maintenance-secrets` |
| `KOMODO_MAINTENANCE_HOST` | Listen address; defaults to `0.0.0.0` |
| `KOMODO_MAINTENANCE_PORT` | Listen port; defaults to `8091` |

The secret directory must contain mode-0400, service-owned files named
`ADAPTER_API_KEY`, `MAINTENANCE_HANDOFF_KEY`, `KOMODO_API_KEY`, and
`KOMODO_API_SECRET`. The deploy endpoint is `POST /v1/deploy` and requires one
`X-Maintenance-Key` header.

The repository publishes a non-root image as
`ghcr.io/wan0net/asgard-komodo-maintenance-adapter`. Pin deployments to a
published digest rather than a mutable tag.

## Test

```sh
python -m unittest discover -s . -p 'test_*.py' -v
```

## License

BSD-3-Clause. See the repository [software licence](../../LICENSES/BSD-3-Clause.txt).
