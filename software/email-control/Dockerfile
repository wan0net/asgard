# SPDX-License-Identifier: BSD-3-Clause

FROM python:3.12-alpine3.24@sha256:6d43704baacd1bfbe7c295d7f13079d5d8104ed33568873133f8fc69980419df
WORKDIR /app
LABEL org.opencontainers.image.source="https://github.com/wan0net/asgard" \
      org.opencontainers.image.description="Authenticated, thread-bound email control adapter" \
      org.opencontainers.image.licenses="BSD-3-Clause"
COPY --chown=65532:65532 email-control/email_control.py /app/email_control.py
COPY --chown=65532:65532 huginn-handoff/huginn_handoff.py /app/huginn_handoff.py
ENV EMAIL_HANDOFF_CONTRACT=/app/huginn_handoff.py
USER 65532:65532
EXPOSE 8094
ENTRYPOINT ["python", "/app/email_control.py"]
