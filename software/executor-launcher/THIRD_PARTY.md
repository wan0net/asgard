# Third-party material

The container build downloads the upstream
[`UsefulSoftwareCo/executor`](https://github.com/UsefulSoftwareCo/executor)
source at commit `e61beb747b5d3f8ff0128555ba92b90307331661` (release
`v1.6.2`) and verifies its archive with the checksum recorded in the Dockerfile.

Executor is distributed under the MIT License. The build retains upstream
licence material in the resulting image. Pantheon-specific launcher and patch
code in this directory is distributed under BSD-3-Clause.

Base images and transitive application dependencies retain their own licences.
Published images include a software bill of materials and build provenance so
the exact set can be inspected for each digest.
