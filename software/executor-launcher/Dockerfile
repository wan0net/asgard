# SPDX-License-Identifier: BSD-3-Clause

ARG EXECUTOR_COMMIT=22a0383758aef57106fda7aa05825c0607352feb
ARG EXECUTOR_SOURCE_SHA256=a59a3a3bd4f7c12016df2fbdc6371ba2475a0ac2734f70b30cc9bee9f3afda68

FROM oven/bun:1@sha256:e10577f0db68676a7024391c6e5cb4b879ebd17188ab750cf10024a6d700e5c4 AS executor-source
ARG EXECUTOR_COMMIT
ARG EXECUTOR_SOURCE_SHA256
WORKDIR /src
ADD "https://github.com/UsefulSoftwareCo/executor/archive/${EXECUTOR_COMMIT}.tar.gz" /tmp/executor.tar.gz
COPY apply-onepassword-selfhost.ts /tmp/apply-onepassword-selfhost.ts
RUN echo "${EXECUTOR_SOURCE_SHA256}  /tmp/executor.tar.gz" | sha256sum --check --strict \
    && tar --extract --gzip --file /tmp/executor.tar.gz --strip-components=1 \
    && rm -f /tmp/executor.tar.gz \
    && bun run /tmp/apply-onepassword-selfhost.ts \
    && rm -f /tmp/apply-onepassword-selfhost.ts \
    && grep -Fq 'if (mode !== "browser") return { artifactsEnabled, elicitationMode: { mode } };' \
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

FROM golang:1.26-alpine@sha256:0178a641fbb4858c5f1b48e34bdaabe0350a330a1b1149aabd498d0699ff5fb2 AS launcher-build
WORKDIR /src
COPY go.mod main.go ./
RUN CGO_ENABLED=0 go build -trimpath -ldflags='-s -w' -o /executor-launcher .

FROM gcr.io/distroless/cc-debian12@sha256:6e1871c34683dc9ee996d13084497783fd98ac0200213d0826625f4e9d4be1d0
WORKDIR /app
LABEL org.opencontainers.image.source="https://github.com/wan0net/asgard" \
      org.opencontainers.image.revision="22a0383758aef57106fda7aa05825c0607352feb" \
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
