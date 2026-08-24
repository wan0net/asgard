# Email control adapter

This adapter reads only captures that have passed the Huginn handoff contract.
It separates authenticated-operator replies from approval-gated external
replies, derives the Gmail thread from the validated capture, and never accepts
an arbitrary destination from a caller.

The SQLite ledger makes exact retries idempotent. An ambiguous downstream send
is recorded and is not retried blindly.

## Configuration

| Variable | Purpose |
| --- | --- |
| `EMAIL_HANDOFF_CONTRACT` | Path to the public handoff module contract |
| `EMAIL_CAPTURE_DIR` | Validated capture directory |
| `EMAIL_CONTROL_DB` | Idempotency and reply ledger database |
| `EMAIL_CONTROL_BEARER_FILE` | File containing the inbound bearer |
| `EMAIL_N8N_BEARER_FILE` | File containing the downstream automation bearer |
| `EMAIL_N8N_URL` | Fixed downstream reply workflow URL |
| `EMAIL_CONTROL_HOST` | Listen address; defaults to `0.0.0.0` |
| `EMAIL_CONTROL_PORT` | Listen port; defaults to `8094` |

Bearer values must be provisioned at runtime and must not appear in source,
images, command arguments, or logs.

## Test

Run from the `software` directory so the sibling handoff contract is available:

```sh
python -m unittest discover -s email-control -p 'test_*.py' -v
```

## License

BSD-3-Clause. See the repository [software licence](../../LICENSES/BSD-3-Clause.txt).
