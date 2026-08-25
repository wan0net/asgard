# Browser egress proxy

This small HTTP CONNECT proxy fails closed when a requested destination resolves
to loopback, private, link-local, carrier-grade NAT, metadata, documentation,
multicast, reserved, or other non-public address space. It resolves and dials
the validated address directly so a later DNS answer cannot redirect the
connection to a blocked network.

It is intended as one layer around a disposable browser worker. It is not an
authentication proxy and does not make an otherwise privileged browser safe.

## Test

```sh
go test ./...
```

## Build

```sh
docker build -t pantheon-browser-egress-proxy .
```

The container listens on port `8080` as a non-root user.

## License

BSD-3-Clause. See the repository [software licence](../../LICENSES/BSD-3-Clause.txt).
