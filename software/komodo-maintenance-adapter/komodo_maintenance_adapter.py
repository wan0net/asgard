#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Fail-closed maintenance gate for one configured Komodo procedure."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import stat
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

MAX_BODY = 32 * 1024
MAX_UPSTREAM_BODY = 64 * 1024
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/@:-]{0,127}$")
DIGEST = re.compile(r"^[a-f0-9]{64}$")
OPAQUE_ID = re.compile(r"^[A-Za-z0-9_-]{16,64}$")


class ValidationError(ValueError):
    pass


class AuthenticationError(RuntimeError):
    pass


class UpstreamError(RuntimeError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def secret(path: Path) -> bytes:
    metadata = path.lstat()
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o400
        or metadata.st_uid != os.geteuid()
    ):
        raise RuntimeError("secret_metadata_invalid")
    value = path.read_bytes()
    if not 16 <= len(value) <= 4096 or b"\x00" in value:
        raise RuntimeError("secret_invalid")
    return value


def exact(value: Any, fields: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValidationError("invalid_fields")
    return value


def bounded(value: Any, pattern: re.Pattern[str]) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ValidationError("invalid_text")
    return value


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"missing_configuration:{name}")
    return value


def endpoint(
    value: str, *, schemes: set[str], require_path: bool = False
) -> tuple[str, str]:
    parsed = urllib.parse.urlsplit(value)
    if (
        parsed.scheme not in schemes
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or (parsed.path and not parsed.path.startswith("/"))
        or (require_path and parsed.path in {"", "/"})
    ):
        raise RuntimeError("endpoint_invalid")
    return value.rstrip("/"), parsed.path.rstrip("/") or "/"


class Gate:
    def __init__(
        self,
        *,
        adapter_key: bytes,
        handoff_key: bytes,
        komodo_key: bytes,
        komodo_secret: bytes,
        komodo_url: str,
        claim_url: str,
        procedure: str,
        fixed_scope: dict[str, str],
        opener: Any | None = None,
        clock: Any = time.time,
    ) -> None:
        self.adapter_key = adapter_key
        self.handoff_key = handoff_key
        self.komodo_key = komodo_key
        self.komodo_secret = komodo_secret
        self.komodo_url, _ = endpoint(komodo_url, schemes={"https"})
        self.claim_url, self.claim_path = endpoint(
            claim_url, schemes={"http", "https"}, require_path=True
        )
        self.procedure = bounded(procedure, IDENTIFIER)
        if set(fixed_scope) != {"repository", "service", "action", "target"}:
            raise RuntimeError("scope_configuration_invalid")
        self.fixed_scope = {
            key: bounded(value, IDENTIFIER) for key, value in fixed_scope.items()
        }
        self.opener = opener or urllib.request.build_opener(NoRedirect())
        self.clock = clock

    def authenticate(self, supplied: str | None) -> None:
        if supplied is None or not hmac.compare_digest(
            supplied.encode(), self.adapter_key
        ):
            raise AuthenticationError("authentication_required")

    def deploy(self, payload: Any) -> dict[str, Any]:
        item = exact(
            payload,
            {
                "session_id", "digest", "grant_id", "request_id",
                "repository", "service", "action", "target",
            },
        )
        claim = {
            "session_id": bounded(item["session_id"], OPAQUE_ID),
            "digest": bounded(item["digest"], DIGEST),
            "grant_id": bounded(item["grant_id"], OPAQUE_ID),
            "request_id": bounded(item["request_id"], IDENTIFIER),
            "repository": bounded(item["repository"], IDENTIFIER),
            "service": bounded(item["service"], IDENTIFIER),
            "action": bounded(item["action"], IDENTIFIER),
            "target": bounded(item["target"], IDENTIFIER),
        }
        if any(claim[key] != value for key, value in self.fixed_scope.items()):
            raise ValidationError("scope_mismatch")
        receipt = self._claim(claim)
        result_digest = self._run_procedure()
        return {
            "status": "accepted",
            "procedure": self.procedure,
            "receipt_id": receipt["receipt_id"],
            "request_ref": receipt["request_ref"],
            "result_digest": result_digest,
        }

    def _request(self, request: urllib.request.Request) -> bytes:
        try:
            with self.opener.open(request, timeout=15) as response:
                body = response.read(MAX_UPSTREAM_BODY + 1)
                if len(body) > MAX_UPSTREAM_BODY:
                    raise UpstreamError("upstream_response_too_large")
                if not 200 <= response.status < 300:
                    raise UpstreamError("upstream_rejected")
                return body
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise UpstreamError("upstream_unavailable") from error

    def _claim(self, payload: dict[str, str]) -> dict[str, Any]:
        body = json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ).encode()
        timestamp = str(int(self.clock()))
        body_hash = hashlib.sha256(body).hexdigest()
        message = "\n".join(
            (timestamp, payload["request_id"], body_hash,
             "POST", self.claim_path)
        ).encode("ascii")
        signature = hmac.new(
            self.handoff_key, message, hashlib.sha256
        ).hexdigest()
        request = urllib.request.Request(
            self.claim_url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Asgard-Timestamp": timestamp,
                "X-Asgard-Request-Id": payload["request_id"],
                "X-Asgard-Signature": f"sha256={signature}",
            },
        )
        raw = self._request(request)
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as error:
            raise UpstreamError("authority_response_invalid") from error
        if (
            not isinstance(result, dict)
            or result.get("status") != "claimed"
            or not isinstance(result.get("receipt_id"), str)
            or not isinstance(result.get("request_ref"), str)
        ):
            raise UpstreamError("authority_response_invalid")
        return result

    def _run_procedure(self) -> str:
        body = json.dumps(
            {"procedure": self.procedure}, separators=(",", ":")
        ).encode()
        request = urllib.request.Request(
            f"{self.komodo_url}/execute/RunProcedure",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Api-Key": self.komodo_key.decode(),
                "X-Api-Secret": self.komodo_secret.decode(),
            },
        )
        return hashlib.sha256(self._request(request)).hexdigest()


class Handler(BaseHTTPRequestHandler):
    gate: Gate

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path != "/healthz":
            self._json(404, {"error": "not_found"})
            return
        self._json(200, {"status": "ready"})

    def do_POST(self) -> None:
        if self.path != "/v1/deploy":
            self._json(404, {"error": "not_found"})
            return
        try:
            keys = self.headers.get_all("X-Maintenance-Key", [])
            if len(keys) != 1:
                raise AuthenticationError("authentication_required")
            self.gate.authenticate(keys[0])
            if self.headers.get("Content-Type") != "application/json":
                raise ValidationError("unsupported_media_type")
            length = int(self.headers.get("Content-Length", "0"))
            if not 1 <= length <= MAX_BODY:
                raise ValidationError("invalid_body")
            payload = json.loads(self.rfile.read(length))
            self._json(200, self.gate.deploy(payload))
        except AuthenticationError as error:
            self._json(401, {"error": str(error)})
        except (ValidationError, json.JSONDecodeError, UnicodeDecodeError) as error:
            self._json(400, {"error": str(error) or "invalid_json"})
        except UpstreamError as error:
            self._json(502, {"error": str(error)})

    def log_message(self, format: str, *args: Any) -> None:
        return


def create_server(host: str, port: int, gate: Gate) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"gate": gate})
    return ThreadingHTTPServer((host, port), handler)


def main() -> None:
    root = Path(os.environ.get(
        "KOMODO_MAINTENANCE_SECRET_DIR", "/run/komodo-maintenance-secrets"
    ))
    gate = Gate(
        adapter_key=secret(root / "ADAPTER_API_KEY"),
        handoff_key=secret(root / "MAINTENANCE_HANDOFF_KEY"),
        komodo_key=secret(root / "KOMODO_API_KEY"),
        komodo_secret=secret(root / "KOMODO_API_SECRET"),
        komodo_url=required_env("KOMODO_URL"),
        claim_url=required_env("MAINTENANCE_AUTHORITY_URL"),
        procedure=required_env("KOMODO_PROCEDURE"),
        fixed_scope={
            "repository": required_env("MAINTENANCE_SCOPE_REPOSITORY"),
            "service": required_env("MAINTENANCE_SCOPE_SERVICE"),
            "action": required_env("MAINTENANCE_SCOPE_ACTION"),
            "target": required_env("MAINTENANCE_SCOPE_TARGET"),
        },
    )
    server = create_server(
        os.environ.get("KOMODO_MAINTENANCE_HOST", "0.0.0.0"),
        int(os.environ.get("KOMODO_MAINTENANCE_PORT", "8091")),
        gate,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
