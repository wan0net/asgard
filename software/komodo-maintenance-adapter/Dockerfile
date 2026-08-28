# SPDX-License-Identifier: BSD-3-Clause
FROM python:3.14-alpine3.24@sha256:05b2b8b732ecd268fee8727a369f936f022d1321b59befd13c30ede22769dcdc
RUN python -m pip uninstall --yes pip setuptools \
    && apk upgrade --no-cache libcrypto3 libssl3
WORKDIR /opt/komodo-maintenance-adapter
LABEL org.opencontainers.image.source="https://github.com/wan0net/asgard" \
      org.opencontainers.image.description="Maintenance-gated fixed Komodo procedure adapter"
COPY --chown=65532:65532 --chmod=0444 komodo_maintenance_adapter.py /opt/komodo-maintenance-adapter/
USER 65532:65532
ENTRYPOINT ["python", "/opt/komodo-maintenance-adapter/komodo_maintenance_adapter.py"]
