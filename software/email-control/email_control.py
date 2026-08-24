#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Fail-closed email trust and thread-bound reply adapter for Odine."""

from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import os
import re
import sqlite3
import stat
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

HEX64 = re.compile(r"^[a-f0-9]{64}$")
REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
MAX_REQUEST = 32 * 1024
MAX_REPLY = 16 * 1024


class PolicyError(RuntimeError):
    pass


class ConflictError(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def private_secret(path: Path) -> str:
    metadata = path.lstat()
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o400
        or metadata.st_uid != os.geteuid()
    ):
        raise RuntimeError("secret_metadata_invalid")
    value = path.read_text().strip()
    if not 32 <= len(value) <= 4096 or "\x00" in value:
        raise RuntimeError("secret_invalid")
    return value


def load_handoff(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("email_handoff_contract", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("handoff_contract_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CaptureStore:
    def __init__(self, root: Path, contract: Any):
        self.root = root
        self.contract = contract

    def read(self, message_hash: str) -> dict[str, Any]:
        if not isinstance(message_hash, str) or not HEX64.fullmatch(message_hash):
            raise PolicyError("invalid_message_hash")
        candidates = list(self.root.glob(f"{message_hash}-*.json"))
        if len(candidates) != 1 or candidates[0].is_symlink():
            raise PolicyError("message_capture_ambiguous")
        path = candidates[0]
        data = path.read_bytes()
        if len(data) > self.contract.MAX_CAPTURE_BYTES:
            raise PolicyError("message_capture_oversized")
        try:
            value = self.contract.strict_json(data)
            self.contract.validate_capture(value, path.name)
        except self.contract.HandoffError as exc:
            raise PolicyError("message_capture_invalid") from exc
        if value["source_url"] != f"email://inbound/{message_hash}":
            raise PolicyError("message_capture_identity_mismatch")
        return value["content"]


class ReplyLedger:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(path.parent, 0o700)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                """CREATE TABLE IF NOT EXISTS replies (
                request_id TEXT PRIMARY KEY,
                message_hash TEXT NOT NULL,
                mode TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                state TEXT NOT NULL,
                response_json TEXT
                )"""
            )
        os.chmod(path, 0o600)

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        return db

    def begin(self, request_id: str, message_hash: str, mode: str, body: str) -> str | None:
        if not isinstance(request_id, str) or not REQUEST_ID.fullmatch(request_id):
            raise PolicyError("invalid_request_id")
        digest = hashlib.sha256(canonical({"body": body})).hexdigest()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM replies WHERE request_id=?", (request_id,)
            ).fetchone()
            if row:
                if (
                    row["message_hash"] != message_hash
                    or row["mode"] != mode
                    or row["payload_hash"] != digest
                ):
                    raise ConflictError("request_replay_mismatch")
                if row["state"] == "sent":
                    return row["response_json"]
                raise ConflictError("reply_delivery_uncertain")
            db.execute(
                "INSERT INTO replies VALUES (?,?,?,?,?,NULL)",
                (request_id, message_hash, mode, digest, "sending"),
            )
            db.commit()
        return None

    def finish(self, request_id: str, response: dict[str, Any]) -> None:
        encoded = canonical(response).decode()
        with self.connect() as db:
            changed = db.execute(
                "UPDATE replies SET state='sent',response_json=? "
                "WHERE request_id=? AND state='sending'",
                (encoded, request_id),
            ).rowcount
            if changed != 1:
                raise ConflictError("reply_state_conflict")
            db.commit()


class EmailControl:
    def __init__(
        self,
        captures: CaptureStore,
        ledger: ReplyLedger,
        n8n_url: str,
        n8n_bearer: str,
    ):
        self.captures = captures
        self.ledger = ledger
        self.n8n_url = n8n_url
        self.n8n_bearer = n8n_bearer

    def reply_target(self, content: dict[str, Any]) -> str:
        auth = content["operator_auth"]
        reply_to = auth["reply_to"]
        target = self.captures.contract.email_address(reply_to or content["from"])
        if not target or (reply_to and not self.captures.contract.email_address(reply_to)):
            raise PolicyError("reply_target_invalid")
        return target

    def message(self, message_hash: str) -> dict[str, Any]:
        content = self.captures.read(message_hash)
        auth = content["operator_auth"]
        try:
            reply_target: str | None = self.reply_target(content)
        except PolicyError:
            reply_target = None
        return {
            "message_id_hash": content["message_id_hash"],
            "sent_at": content["sent_at"],
            "from": content["from"],
            "subject": content["subject"],
            "reply_target": reply_target,
            "text": content["text"],
            "html": content["html"],
            "operator_auth": {
                "status": auth["status"],
                "claimed_sender": auth["claimed_sender"],
            },
        }

    def reply(self, mode: str, value: Any) -> dict[str, Any]:
        if mode not in {"operator", "external"}:
            raise PolicyError("invalid_reply_mode")
        fields = {"request_id", "message_id_hash", "body"}
        if mode == "external":
            fields.add("expected_reply_address")
        if not isinstance(value, dict) or set(value) != fields:
            raise PolicyError("invalid_fields")
        body = value["body"]
        if (
            not isinstance(body, str)
            or not body.strip()
            or "\x00" in body
            or len(body.encode()) > MAX_REPLY
        ):
            raise PolicyError("invalid_reply_body")
        content = self.captures.read(value["message_id_hash"])
        status = content["operator_auth"]["status"]
        reply_target = self.reply_target(content)
        if mode == "operator" and status != "operator_authenticated":
            raise PolicyError("operator_reply_requires_authenticated_operator")
        if mode == "external" and status != "external_untrusted":
            raise PolicyError("external_reply_requires_external_message")
        if mode == "external":
            auth = content["operator_auth"]
            if (
                value["expected_reply_address"] != reply_target
                or auth["auto_submitted"] not in {"", "no"}
                or auth["precedence"] in {"bulk", "junk", "list"}
            ):
                raise PolicyError("external_reply_target_not_approved")
        replay = self.ledger.begin(
            value["request_id"], value["message_id_hash"], mode, body
        )
        if replay is not None:
            return json.loads(replay)
        payload = {
            "schema": "asgard.email-thread-reply.v1",
            "request_id": value["request_id"],
            "gmail_message_id": content["gmail_message_id"],
            "gmail_thread_id": content["gmail_thread_id"],
            "body": body,
        }
        request = urllib.request.Request(
            self.n8n_url,
            data=canonical(payload),
            headers={
                "Authorization": f"Bearer {self.n8n_bearer}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError("reply_delivery_rejected")
            response.read(1)
        result = {
            "status": "sent",
            "request_id": value["request_id"],
            "message_id_hash": value["message_id_hash"],
            "mode": mode,
            "reply_target": reply_target,
        }
        self.ledger.finish(value["request_id"], result)
        return result


class Handler(BaseHTTPRequestHandler):
    server: Any

    def send_json(self, status: int, value: Any) -> None:
        body = canonical(value)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def authenticate(self) -> bool:
        expected = f"Bearer {self.server.bearer}"
        supplied = self.headers.get("Authorization", "")
        return hmac.compare_digest(supplied, expected)

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self.send_json(HTTPStatus.OK, {"status": "ok"})
            return
        if not self.authenticate():
            self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return
        match = re.fullmatch(r"/v1/messages/([a-f0-9]{64})", self.path)
        if not match:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        try:
            self.send_json(HTTPStatus.OK, self.server.control.message(match.group(1)))
        except PolicyError as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

    def do_POST(self) -> None:
        if not self.authenticate():
            self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return
        match = re.fullmatch(r"/v1/replies/(operator|external)", self.path)
        if not match:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 1 <= length <= MAX_REQUEST:
                raise PolicyError("invalid_request_size")
            value = json.loads(self.rfile.read(length))
            result = self.server.control.reply(match.group(1), value)
            self.send_json(HTTPStatus.OK, result)
        except json.JSONDecodeError:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_json"})
        except PolicyError as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except ConflictError as exc:
            self.send_json(HTTPStatus.CONFLICT, {"error": str(exc)})
        except Exception:
            self.send_json(HTTPStatus.BAD_GATEWAY, {"error": "delivery_failed_uncertain"})

    def log_message(self, _format: str, *_args: Any) -> None:
        return


def main() -> None:
    contract = load_handoff(Path(os.environ["EMAIL_HANDOFF_CONTRACT"]))
    captures = CaptureStore(Path(os.environ["EMAIL_CAPTURE_DIR"]), contract)
    ledger = ReplyLedger(Path(os.environ["EMAIL_CONTROL_DB"]))
    bearer = private_secret(Path(os.environ["EMAIL_CONTROL_BEARER_FILE"]))
    n8n_bearer = private_secret(Path(os.environ["EMAIL_N8N_BEARER_FILE"]))
    control = EmailControl(captures, ledger, os.environ["EMAIL_N8N_URL"], n8n_bearer)
    server = ThreadingHTTPServer(
        (os.environ.get("EMAIL_CONTROL_HOST", "0.0.0.0"), int(os.environ.get("EMAIL_CONTROL_PORT", "8094"))),
        Handler,
    )
    server.control = control
    server.bearer = bearer
    server.serve_forever()


if __name__ == "__main__":
    main()
