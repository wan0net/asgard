# SPDX-License-Identifier: BSD-3-Clause

FROM python:3.14-alpine3.24@sha256:05b2b8b732ecd268fee8727a369f936f022d1321b59befd13c30ede22769dcdc
RUN apk upgrade --no-cache libcrypto3 libssl3
WORKDIR /app
LABEL org.opencontainers.image.source="https://github.com/wan0net/asgard" \
      org.opencontainers.image.description="Scoped, durable maintenance-session authority" \
      org.opencontainers.image.licenses="BSD-3-Clause"
COPY --chown=65532:65532 --chmod=0444 maintenance_session_adapter.py /app/maintenance_session_adapter.py
USER 65532:65532
EXPOSE 8090
ENTRYPOINT ["python", "/app/maintenance_session_adapter.py"]
