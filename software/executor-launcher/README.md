# Executor self-host launcher

This component builds an exact, checksum-verified upstream
[Executor](https://github.com/UsefulSoftwareCo/executor) revision, applies the
reviewed self-host integration patch, and starts it only after three required
runtime secret files are present and non-empty.

The launcher reads the files under `/run/executor-secrets`, adds their values to
the child process environment, and replaces itself with the Executor process.
Secret values are never compiled into the image.

## Test

```sh
go test ./...
```

The container build also verifies that every expected upstream patch location
occurs exactly once. An upstream source change therefore fails the build rather
than producing a partially patched image.

## Vulnerability exception

The image scan has one package- and expiry-scoped suppression for
`CVE-2026-14456`. Debian currently defers a fix for the OpenSSL QUIC-server
denial of service. The self-host runtime is an HTTP application behind a
separate TLS edge, and review of the exact pinned Executor source found no QUIC
server implementation. The exception expires on 2026-09-25; every other high
or critical finding continues to fail publication.

## Licence and upstream material

Pantheon launcher and patch code is BSD-3-Clause. The downloaded Executor source
retains its upstream MIT licence. Built images therefore contain material under
both licences.
