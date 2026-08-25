# SPDX-License-Identifier: BSD-3-Clause

FROM python:3.12-alpine3.24@sha256:6d43704baacd1bfbe7c295d7f13079d5d8104ed33568873133f8fc69980419df
WORKDIR /app
LABEL org.opencontainers.image.source="https://github.com/wan0net/asgard" \
      org.opencontainers.image.description="Fail-closed validation and handoff for untrusted captures" \
      org.opencontainers.image.licenses="BSD-3-Clause"
COPY --chown=1000:1000 huginn_handoff.py /app/huginn_handoff.py
USER 1000:1000
EXPOSE 8651
ENTRYPOINT ["python", "/app/huginn_handoff.py"]
