# SPDX-License-Identifier: BSD-3-Clause

FROM golang:1.26-alpine@sha256:0178a641fbb4858c5f1b48e34bdaabe0350a330a1b1149aabd498d0699ff5fb2 AS build
WORKDIR /src
COPY go.mod main.go ./
RUN CGO_ENABLED=0 go build -trimpath -ldflags='-s -w' -o /browser-egress-proxy .

FROM gcr.io/distroless/static-debian12:nonroot@sha256:1b7b9f0f0e0a1d2155f531db587cc48ec26aaf97ab64364225f5bf18a054e66a
LABEL org.opencontainers.image.source="https://github.com/wan0net/asgard" \
      org.opencontainers.image.description="Fail-closed CONNECT proxy that denies private and reserved destinations" \
      org.opencontainers.image.licenses="BSD-3-Clause"
COPY --from=build /browser-egress-proxy /browser-egress-proxy
USER 65532:65532
EXPOSE 8080
ENTRYPOINT ["/browser-egress-proxy"]
