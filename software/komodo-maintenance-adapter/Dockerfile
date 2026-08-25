# SPDX-License-Identifier: BSD-3-Clause
FROM python:3.14-alpine3.24@sha256:26730869004e2b9c4b9ad09cab8625e81d256d1ce97e72df5520e806b1709f92
WORKDIR /opt/komodo-maintenance-adapter
LABEL org.opencontainers.image.source="https://github.com/wan0net/asgard" \
      org.opencontainers.image.description="Maintenance-gated fixed Komodo procedure adapter"
COPY --chown=65532:65532 --chmod=0444 komodo_maintenance_adapter.py /opt/komodo-maintenance-adapter/
USER 65532:65532
ENTRYPOINT ["python", "/opt/komodo-maintenance-adapter/komodo_maintenance_adapter.py"]
