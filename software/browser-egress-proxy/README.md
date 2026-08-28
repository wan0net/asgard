# Browser egress proxy

This small HTTP CONNECT proxy provides two mutually exclusive, fail-closed
destination modes:

- `public` is the default. It permits public HTTP and HTTPS destinations and
  denies loopback, private, link-local, carrier-grade NAT, metadata,
  documentation, multicast, reserved, and other non-public address space.
- `internal` permits only explicitly configured subnets within RFC1918,
  carrier-grade NAT, or IPv6 ULA space, and only explicitly configured ports.
  It denies the public internet and every unconfigured internal subnet.

Both modes resolve and dial the validated address directly so a later DNS
answer cannot redirect the connection outside the selected boundary.

It is intended as one layer around a disposable browser worker. A deployment
that needs both public research and internal-tool access should run separate
workers and separate proxy instances. Never give one browser session both
policies: hostile public content must not be able to pivot into an internal
tool. This proxy is not an authentication or authorization service and does not
make an otherwise privileged browser safe.

## Configuration

Public mode requires no environment variables and does not accept destination
overrides.

Internal mode requires all three variables:

```text
PANTHEON_PROXY_MODE=internal
PANTHEON_PROXY_ALLOWED_CIDRS=<COMMA_SEPARATED_PRIVATE_OR_TAILNET_PREFIXES>
PANTHEON_PROXY_ALLOWED_PORTS=<COMMA_SEPARATED_PORTS>
```

An internal prefix must be contained by RFC1918, `100.64.0.0/10`, or
`fc00::/7`. Loopback, link-local, metadata, public, multicast, reserved, and
unlisted destinations remain unreachable. Use deployment-specific subnets
rather than the whole eligible range whenever practical.

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
