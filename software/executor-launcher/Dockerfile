# SPDX-License-Identifier: BSD-3-Clause

ARG EXECUTOR_COMMIT=e61beb747b5d3f8ff0128555ba92b90307331661
ARG EXECUTOR_SOURCE_SHA256=df147212df8bc2dd70fc7e14a6cae9331d60fc07040869665c8bb5fdccd86654

FROM oven/bun:1@sha256:5ff609364c049b54eb0ff560ec96319729a972078ef2c755d758f0c6ef89c2d6 AS executor-source
ARG EXECUTOR_COMMIT
ARG EXECUTOR_SOURCE_SHA256
WORKDIR /src
ADD "https://codeload.github.com/UsefulSoftwareCo/executor/tar.gz/${EXECUTOR_COMMIT}" /tmp/executor.tar.gz
COPY apply-onepassword-selfhost.ts /tmp/apply-onepassword-selfhost.ts
RUN echo "${EXECUTOR_SOURCE_SHA256}  /tmp/executor.tar.gz" | sha256sum --check --strict \
    && tar --extract --gzip --file /tmp/executor.tar.gz --strip-components=1 \
    && rm -f /tmp/executor.tar.gz \
    && bun run /tmp/apply-onepassword-selfhost.ts \
    && rm -f /tmp/apply-onepassword-selfhost.ts \
    && grep -Fq 'return { artifactsEnabled, searchToolsEnabled, elicitationMode: { mode } };' \
      packages/hosts/mcp/src/in-memory-session-store.ts

FROM executor-source AS executor-prod-deps
RUN bun install --frozen-lockfile --production --ignore-scripts --filter @executor-js/host-selfhost \
    && bun run apps/host-selfhost/scripts/package-runtime.ts \
    && wasm_path="$(find /src/node_modules -type f -path '*/@1password/sdk-core/nodejs/core_bg.wasm' -print -quit)" \
    && test -n "${wasm_path}" \
    && cp "${wasm_path}" /src/onepassword-core_bg.wasm

FROM executor-source AS executor-build
RUN bun install --frozen-lockfile
RUN cd apps/host-selfhost && bun run build

FROM golang:1.27-alpine@sha256:4c9fe60190a2a3350ddc51de80d0224b8a6698d12bdfc999fee45ea9d6c46dbc AS launcher-build
WORKDIR /src
COPY go.mod main.go ./
RUN CGO_ENABLED=0 go build -trimpath -ldflags='-s -w' -o /executor-launcher .

FROM gcr.io/distroless/cc-debian13@sha256:9b615fff20e1a4fad29c2b30562580b212c7dd5e2225236735cca0070ed11c78
WORKDIR /app
LABEL org.opencontainers.image.source="https://github.com/wan0net/asgard" \
      org.opencontainers.image.revision="e61beb747b5d3f8ff0128555ba92b90307331661" \
      org.opencontainers.image.description="Pinned Executor self-host with native MCP elicitation and a Pantheon secret-file launcher" \
      org.opencontainers.image.licenses="BSD-3-Clause AND MIT"
ENV NODE_ENV=production \
    EXECUTOR_HOST=0.0.0.0 \
    PORT=4788 \
    EXECUTOR_DATA_DIR=/data
COPY --from=executor-prod-deps /usr/local/bin/bun /usr/local/bin/bun
COPY --from=executor-prod-deps /src/onepassword-core_bg.wasm /usr/local/bin/onepassword-core_bg.wasm
COPY --from=executor-prod-deps /src/.selfhost-runtime /app
COPY --from=executor-build /src/apps/host-selfhost/dist /app/apps/host-selfhost/dist
COPY --from=launcher-build /executor-launcher /usr/local/bin/executor-launcher
WORKDIR /app/apps/host-selfhost
VOLUME ["/data"]
EXPOSE 4788
USER 65532:65532
ENTRYPOINT ["/usr/local/bin/executor-launcher"]
