# Maintenance-session authority

This service provides a narrow, durable authority for explicitly approved
maintenance windows. It records a pending proposal, binds activation to an
immutable digest, issues bounded grants only for the exact approved scope, and
keeps a redacted append-only SQLite journal.

Low-risk grants cover branch creation, worktree edits, tests, and draft pull
requests. High-risk grants cover only pinned merge and deployment actions. The
service does not edit repositories, invoke deployment systems, expose a shell,
or handle arbitrary secrets itself.

An optional internal claim path uses a request-bound HMAC with timestamp and
request ID validation. Issued grants expire after two minutes and are
invalidated on restart. Missing handoff configuration leaves the public API
available while the internal claim path fails closed.

## Configuration

| Variable | Purpose |
| --- | --- |
| `MAINTENANCE_SESSION_DB` | Durable SQLite state path |
| `MAINTENANCE_SESSION_REQUESTER` | Fixed requester identity |
| `MAINTENANCE_SESSION_APPROVER` | Fixed approver identity |
| `MAINTENANCE_SESSION_HOST` | Listen address; defaults to `0.0.0.0` |
| `MAINTENANCE_SESSION_PORT` | Listen port; defaults to `8090` |
| `MAINTENANCE_HANDOFF_KEY_FILE` | Optional mode-0400 internal HMAC key file |

Identities and the handoff key belong in private runtime configuration. They
must not be accepted from the maintenance request body.

The repository publishes a non-root image as
`ghcr.io/wan0net/asgard-maintenance-session-adapter`. Pin deployments to a
published digest rather than a mutable tag.

## Test

```sh
python -m unittest discover -s . -p 'test_*.py' -v
```

## License

BSD-3-Clause. See the repository [software licence](../../LICENSES/BSD-3-Clause.txt).
