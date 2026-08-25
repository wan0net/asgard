# Huginn capture handoff

The handoff treats collected captures as untrusted, bounded input. It validates
their schema, hashes, timestamps, source contract, MIME type, attachment
metadata, and email authentication record before placing accepted content in a
content-addressed immutable outbox.

Consumers use fixed read, lease, acknowledgement, and checkpoint operations.
The service does not delete the read-only staging source and does not promote
captured content into canonical knowledge.

## Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `HUGINN_HANDOFF_BEARER` | Required bearer with at least 32 encoded bytes | none |
| `HUGINN_STAGING_DIR` | Read-only capture staging directory | `/captures` |
| `HUGINN_OUTBOX_DIR` | Immutable accepted-capture outbox | `/outbox` |
| `HUGINN_HANDOFF_STATE_DIR` | Lease and checkpoint state | `/state` |
| `HUGINN_HANDOFF_PORT` | HTTP port | `8651` |
| `HUGINN_OPERATOR_EMAIL_ADDRESSES` | Comma-separated authenticated operator addresses | empty |

An empty operator-address list fails closed: no sender can receive operator
status. Addresses belong in private runtime configuration, never public source.

The repository publishes a non-root container as
`ghcr.io/wan0net/asgard-huginn-handoff`. Pin deployments to a digest emitted by
the image workflow; do not deploy a mutable tag.

## Test

```sh
python -m unittest discover -s . -p 'test_*.py' -v
```

## License

BSD-3-Clause. See the repository [software licence](../../LICENSES/BSD-3-Clause.txt).
