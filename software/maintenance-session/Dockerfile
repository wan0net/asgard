# SPDX-License-Identifier: BSD-3-Clause

FROM python:3.14-alpine3.24@sha256:26730869004e2b9c4b9ad09cab8625e81d256d1ce97e72df5520e806b1709f92
RUN apk upgrade --no-cache libcrypto3 libssl3
WORKDIR /app
LABEL org.opencontainers.image.source="https://github.com/wan0net/asgard" \
      org.opencontainers.image.description="Scoped, durable maintenance-session authority" \
      org.opencontainers.image.licenses="BSD-3-Clause"
COPY --chown=65532:65532 --chmod=0444 maintenance_session_adapter.py /app/maintenance_session_adapter.py
USER 65532:65532
EXPOSE 8090
ENTRYPOINT ["python", "/app/maintenance_session_adapter.py"]
