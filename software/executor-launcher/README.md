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

## Licence and upstream material

Pantheon launcher and patch code is BSD-3-Clause. The downloaded Executor source
retains its upstream MIT licence. Built images therefore contain material under
both licences.
