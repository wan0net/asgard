# SPDX-License-Identifier: BSD-3-Clause

FROM golang:1.27-alpine@sha256:4c9fe60190a2a3350ddc51de80d0224b8a6698d12bdfc999fee45ea9d6c46dbc AS build
WORKDIR /src
COPY go.mod main.go ./
RUN CGO_ENABLED=0 go build -trimpath -ldflags='-s -w' -o /browser-egress-proxy .

FROM gcr.io/distroless/static-debian12:nonroot@sha256:afa5c872c891853ca7fcf1f12c3edb23f7eeef36189728842dd51042ff57f7ab
LABEL org.opencontainers.image.source="https://github.com/wan0net/asgard" \
      org.opencontainers.image.description="Fail-closed CONNECT proxy that denies private and reserved destinations" \
      org.opencontainers.image.licenses="BSD-3-Clause"
COPY --from=build /browser-egress-proxy /browser-egress-proxy
USER 65532:65532
EXPOSE 8080
ENTRYPOINT ["/browser-egress-proxy"]
