#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Deterministic, fail-closed maintenance-session capability for Heimdall."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import stat
import threading
import time
import urllib.parse
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

MAX_REQUEST_BYTES = 64 * 1024
MAX_DURATION_SECONDS = 4 * 60 * 60
MIN_DURATION_SECONDS = 60
MAX_USES = 32
GRANT_TTL_SECONDS = 120
HANDOFF_MAX_SKEW_SECONDS = 60
LOW_RISK_ACTIONS = frozenset(
    {"create_branch", "edit_worktree", "run_tests", "open_pull_request"}
)
HIGH_RISK_ACTIONS = frozenset(
    {"merge_pinned_change", "deploy_pinned_change"}
)
ALLOWED_ACTIONS = LOW_RISK_ACTIONS | HIGH_RISK_ACTIONS
PROHIBITED_ACTIONS = frozenset(
    {
        "change_secrets",
        "change_networking",
        "destructive",
        "delete_data",
        "disable_audit",
        "arbitrary_shell",
    }
)
TERMINAL_STATES = frozenset({"revoked", "expired", "completed"})
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/@:-]{0,127}$")
TARGET = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/@:#-]{0,255}$")


class ValidationError(ValueError):
    """A caller supplied a malformed or prohibited value."""


class ConflictError(RuntimeError):
    """The requested transition conflicts with durable state."""


class AuthenticationError(RuntimeError):
    """A trusted internal caller failed handoff authentication."""


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _reference(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _secret_file(path: Path, *, expected_uid: int | None = None) -> bytes:
    metadata = path.lstat()
    expected_uid = os.geteuid() if expected_uid is None else expected_uid
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o400
        or metadata.st_uid != expected_uid
    ):
        raise RuntimeError("handoff_secret_metadata_invalid")
    value = path.read_bytes()
    if not 32 <= len(value) <= 4096 or b"\x00" in value:
        raise RuntimeError("handoff_secret_invalid")
    return value


class HandoffAuthenticator:
    """Verify bounded, request-bound HMAC authentication for internal claims."""

    def __init__(
        self,
        key: bytes,
        *,
        clock: Callable[[], float] = time.time,
        max_skew: int = HANDOFF_MAX_SKEW_SECONDS,
    ) -> None:
        self.key = key
        self.clock = clock
        self.max_skew = max_skew

    @staticmethod
    def message(
        method: str,
        path: str,
        timestamp: str,
        request_id: str,
        body: bytes,
    ) -> bytes:
        body_hash = hashlib.sha256(body).hexdigest()
        return "\n".join(
            (timestamp, request_id, body_hash, method.upper(), path)
        ).encode("ascii")

    def verify(
        self,
        *,
        method: str,
        path: str,
        timestamp: str | None,
        request_id: str | None,
        signature: str | None,
        body: bytes,
    ) -> str:
        if timestamp is None or request_id is None or signature is None:
            raise AuthenticationError("handoff_auth_required")
        request_id = _bounded_text(
            request_id, maximum=128, pattern=IDENTIFIER
        )
        if not timestamp.isdigit():
            raise AuthenticationError("handoff_timestamp_invalid")
        at = int(timestamp)
        if abs(int(self.clock()) - at) > self.max_skew:
            raise AuthenticationError("handoff_timestamp_expired")
        if not re.fullmatch(r"sha256=[a-f0-9]{64}", signature):
            raise AuthenticationError("handoff_signature_invalid")
        expected = hmac.new(
            self.key,
            self.message(method, path, timestamp, request_id, body),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, f"sha256={expected}"):
            raise AuthenticationError("handoff_signature_invalid")
        return request_id


def _exact_object(
    value: Any, required: set[str], optional: set[str] | None = None
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError("invalid_object")
    optional = optional or set()
    keys = set(value)
    if not required <= keys or keys - required - optional:
        raise ValidationError("invalid_fields")
    return value


def _bounded_text(
    value: Any, *, maximum: int, pattern: re.Pattern[str] | None = None
) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ValidationError("invalid_text")
    if pattern is not None and pattern.fullmatch(value) is None:
        raise ValidationError("invalid_text")
    if any(character in value for character in ("*", "?", "\x00")):
        raise ValidationError("wildcard_not_allowed")
    return value


def _strict_list(
    value: Any, *, pattern: re.Pattern[str], maximum_items: int = 16
) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or len(value) > maximum_items
    ):
        raise ValidationError("invalid_scope")
    maximum = 256 if pattern is TARGET else 128
    result = [
        _bounded_text(item, maximum=maximum, pattern=pattern)
        for item in value
    ]
    if len(set(result)) != len(result):
        raise ValidationError("ambiguous_scope")
    return sorted(result)


class MaintenanceStore:
    """SQLite-backed session, grant and redacted journal state."""

    def __init__(
        self,
        path: Path,
        *,
        requester: str,
        approver: str,
        clock: Callable[[], float] = time.time,
        boot_id: str | None = None,
    ) -> None:
        self.path = path
        self.clock = clock
        self.boot_id = boot_id or secrets.token_hex(16)
        self.requester = _bounded_text(
            requester, maximum=128, pattern=IDENTIFIER
        )
        self.approver = _bounded_text(
            approver, maximum=128, pattern=IDENTIFIER
        )
        self._lock = threading.RLock()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._initialise()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path, timeout=5, isolation_level=None
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            connection = self._connect()
            try:
                connection.execute("BEGIN IMMEDIATE")
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

    def _initialise(self) -> None:
        with self._transaction() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    requester_subject TEXT NOT NULL,
                    requester_assertion TEXT NOT NULL,
                    approver_subject TEXT NOT NULL,
                    approver_assertion TEXT NOT NULL,
                    activation_approval_id TEXT,
                    scope_json TEXT NOT NULL,
                    actions_json TEXT NOT NULL,
                    reason_hash TEXT NOT NULL,
                    issued_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    session_digest TEXT NOT NULL UNIQUE,
                    max_uses INTEGER NOT NULL,
                    uses INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS grants (
                    grant_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(session_id),
                    request_id TEXT NOT NULL UNIQUE,
                    token_hash TEXT NOT NULL,
                    action TEXT NOT NULL,
                    repository TEXT NOT NULL,
                    service TEXT NOT NULL,
                    target TEXT NOT NULL,
                    session_digest TEXT NOT NULL,
                    issued_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    boot_id TEXT NOT NULL,
                    approval_id TEXT
                );
                CREATE TABLE IF NOT EXISTS audit_journal (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    occurred_at INTEGER NOT NULL,
                    event TEXT NOT NULL,
                    session_id TEXT,
                    grant_id TEXT,
                    actor_ref TEXT,
                    details_json TEXT NOT NULL
                );
                CREATE TRIGGER IF NOT EXISTS audit_no_update
                BEFORE UPDATE ON audit_journal
                BEGIN SELECT RAISE(ABORT, 'append_only'); END;
                CREATE TRIGGER IF NOT EXISTS audit_no_delete
                BEFORE DELETE ON audit_journal
                BEGIN SELECT RAISE(ABORT, 'append_only'); END;
                """
            )
            rows = db.execute(
                "SELECT grant_id, session_id FROM grants WHERE state='issued'"
            ).fetchall()
            now = int(self.clock())
            for row in rows:
                db.execute(
                    "UPDATE grants SET state='invalidated' WHERE grant_id=?",
                    (row["grant_id"],),
                )
                self._audit(
                    db,
                    now,
                    "grant_invalidated_on_restart",
                    row["session_id"],
                    row["grant_id"],
                    None,
                    {},
                )

    def _audit(
        self,
        db: sqlite3.Connection,
        at: int,
        event: str,
        session_id: str | None,
        grant_id: str | None,
        actor: str | None,
        details: dict[str, Any],
    ) -> None:
        safe = {
            key: value
            for key, value in details.items()
            if key
            in {
                "action",
                "state",
                "uses",
                "max_uses",
                "denial",
                "resource_ref",
            }
        }
        db.execute(
            """
            INSERT INTO audit_journal
              (occurred_at,event,session_id,grant_id,actor_ref,details_json)
            VALUES (?,?,?,?,?,?)
            """,
            (
                at,
                event,
                session_id,
                grant_id,
                _reference(actor) if actor else None,
                _canonical(safe).decode("ascii"),
            ),
        )

    def _expire(self, db: sqlite3.Connection, row: sqlite3.Row, now: int) -> str:
        state = str(row["state"])
        if state in {"pending", "active"} and now >= int(row["expires_at"]):
            db.execute(
                "UPDATE sessions SET state='expired' WHERE session_id=?",
                (row["session_id"],),
            )
            self._audit(
                db,
                now,
                "session_expired",
                row["session_id"],
                None,
                None,
                {"state": "expired"},
            )
            return "expired"
        return state

    def create_session(self, payload: Any) -> dict[str, Any]:
        item = _exact_object(
            payload,
            {
                "request_correlation_id",
                "scope",
                "allowed_actions",
                "reason",
                "duration_seconds",
                "max_uses",
            },
        )
        request_correlation_id = _bounded_text(
            item["request_correlation_id"],
            maximum=128,
            pattern=IDENTIFIER,
        )
        scope_value = _exact_object(
            item["scope"], {"repositories", "services", "targets"}
        )
        scope = {
            "repositories": _strict_list(
                scope_value["repositories"], pattern=IDENTIFIER
            ),
            "services": _strict_list(
                scope_value["services"], pattern=IDENTIFIER
            ),
            "targets": _strict_list(
                scope_value["targets"], pattern=TARGET
            ),
        }
        actions_raw = item["allowed_actions"]
        if not isinstance(actions_raw, list) or not actions_raw:
            raise ValidationError("invalid_actions")
        actions = sorted(set(actions_raw))
        if len(actions) != len(actions_raw):
            raise ValidationError("ambiguous_actions")
        if any(not isinstance(action, str) for action in actions):
            raise ValidationError("invalid_actions")
        if set(actions) & PROHIBITED_ACTIONS or not set(actions) <= ALLOWED_ACTIONS:
            raise ValidationError("prohibited_action")
        reason = _bounded_text(item["reason"], maximum=1024)
        duration = item["duration_seconds"]
        max_uses = item["max_uses"]
        if (
            not isinstance(duration, int)
            or isinstance(duration, bool)
            or not MIN_DURATION_SECONDS <= duration <= MAX_DURATION_SECONDS
        ):
            raise ValidationError("invalid_duration")
        if (
            not isinstance(max_uses, int)
            or isinstance(max_uses, bool)
            or not 1 <= max_uses <= MAX_USES
        ):
            raise ValidationError("invalid_max_uses")
        now = int(self.clock())
        expires_at = now + duration
        session_id = secrets.token_hex(24)
        material = {
            "session_id": session_id,
            "requester": self.requester,
            "approver": self.approver,
            "request_correlation_ref": _digest(request_correlation_id),
            "scope": scope,
            "allowed_actions": actions,
            "reason_hash": _digest(reason),
            "issued_at": now,
            "expires_at": expires_at,
            "max_uses": max_uses,
        }
        session_digest = _digest(material)
        with self._transaction() as db:
            db.execute(
                """
                INSERT INTO sessions VALUES
                  (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    session_id,
                    "pending",
                    self.requester,
                    _digest(request_correlation_id),
                    self.approver,
                    _digest("fixed-adapter-config"),
                    None,
                    _canonical(scope).decode("ascii"),
                    _canonical(actions).decode("ascii"),
                    material["reason_hash"],
                    now,
                    expires_at,
                    session_digest,
                    max_uses,
                    0,
                ),
            )
            self._audit(
                db,
                now,
                "session_created",
                session_id,
                None,
                self.requester,
                {"state": "pending", "max_uses": max_uses},
            )
        return self.get_session(session_id) | {"digest": session_digest}

    def activate_session(self, session_id: str, payload: Any) -> dict[str, Any]:
        item = _exact_object(payload, {"digest", "approval_correlation_id"})
        supplied_digest = _bounded_text(
            item["digest"], maximum=64, pattern=re.compile(r"^[a-f0-9]{64}$")
        )
        approval_correlation_id = _bounded_text(
            item["approval_correlation_id"],
            maximum=128,
            pattern=IDENTIFIER,
        )
        now = int(self.clock())
        with self._transaction() as db:
            row = self._session_row(db, session_id)
            state = self._expire(db, row, now)
            if state != "pending":
                raise ConflictError("invalid_state")
            if not hmac.compare_digest(supplied_digest, row["session_digest"]):
                raise ConflictError("digest_mismatch")
            db.execute(
                """
                UPDATE sessions
                SET state='active', activation_approval_id=?
                WHERE session_id=?
                """,
                (_digest(approval_correlation_id), session_id),
            )
            self._audit(
                db,
                now,
                "session_activated",
                session_id,
                None,
                self.approver,
                {"state": "active"},
            )
        return self.get_session(session_id)

    def transition(
        self, session_id: str, payload: Any, destination: str
    ) -> dict[str, Any]:
        item = _exact_object(payload, {"digest", "request_correlation_id"})
        _bounded_text(
            item["request_correlation_id"],
            maximum=128,
            pattern=IDENTIFIER,
        )
        supplied_digest = _bounded_text(
            item["digest"], maximum=64, pattern=re.compile(r"^[a-f0-9]{64}$")
        )
        now = int(self.clock())
        with self._transaction() as db:
            row = self._session_row(db, session_id)
            state = self._expire(db, row, now)
            if state in TERMINAL_STATES:
                raise ConflictError("invalid_state")
            if not hmac.compare_digest(supplied_digest, row["session_digest"]):
                raise ConflictError("digest_mismatch")
            db.execute(
                "UPDATE sessions SET state=? WHERE session_id=?",
                (destination, session_id),
            )
            db.execute(
                """
                UPDATE grants SET state='invalidated'
                WHERE session_id=? AND state='issued'
                """,
                (session_id,),
            )
            self._audit(
                db,
                now,
                f"session_{destination}",
                session_id,
                None,
                self.requester,
                {"state": destination},
            )
        return self.get_session(session_id)

    def authorize(self, payload: Any, *, high_risk: bool) -> dict[str, Any]:
        required = {
            "session_id",
            "digest",
            "repository",
            "service",
            "action",
            "target",
            "request_id",
        }
        item = _exact_object(payload, required)
        session_id = _bounded_text(
            item["session_id"], maximum=64, pattern=IDENTIFIER
        )
        supplied_digest = _bounded_text(
            item["digest"], maximum=64, pattern=re.compile(r"^[a-f0-9]{64}$")
        )
        repository = _bounded_text(
            item["repository"], maximum=128, pattern=IDENTIFIER
        )
        service = _bounded_text(
            item["service"], maximum=128, pattern=IDENTIFIER
        )
        action = _bounded_text(
            item["action"], maximum=64, pattern=IDENTIFIER
        )
        target = _bounded_text(item["target"], maximum=256, pattern=TARGET)
        request_id = _bounded_text(
            item["request_id"], maximum=128, pattern=IDENTIFIER
        )
        expected = HIGH_RISK_ACTIONS if high_risk else LOW_RISK_ACTIONS
        if action not in expected:
            raise ValidationError("wrong_authorization_class")
        now = int(self.clock())
        grant_id = secrets.token_hex(24)
        with self._transaction() as db:
            row = self._session_row(db, session_id)
            state = self._expire(db, row, now)
            if state != "active":
                raise ConflictError("session_not_active")
            if now >= int(row["expires_at"]):
                raise ConflictError("session_expired")
            if not hmac.compare_digest(supplied_digest, row["session_digest"]):
                raise ConflictError("digest_mismatch")
            scope = json.loads(row["scope_json"])
            actions = json.loads(row["actions_json"])
            if (
                repository not in scope["repositories"]
                or service not in scope["services"]
                or target not in scope["targets"]
                or action not in actions
            ):
                self._audit(
                    db,
                    now,
                    "authorization_denied",
                    session_id,
                    None,
                    None,
                    {
                        "action": action,
                        "denial": "scope_mismatch",
                        "resource_ref": _reference(
                            f"{repository}/{service}/{target}"
                        ),
                    },
                )
                raise ConflictError("scope_mismatch")
            if int(row["uses"]) >= int(row["max_uses"]):
                raise ConflictError("uses_exhausted")
            try:
                db.execute(
                    """
                    INSERT INTO grants VALUES
                      (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        grant_id,
                        session_id,
                        request_id,
                        _digest(secrets.token_bytes(32).hex()),
                        action,
                        repository,
                        service,
                        target,
                        supplied_digest,
                        now,
                        min(now + GRANT_TTL_SECONDS, int(row["expires_at"])),
                        "issued",
                        self.boot_id,
                        row["activation_approval_id"],
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise ConflictError("replay_detected") from error
            uses = int(row["uses"]) + 1
            state_after = (
                "completed" if uses >= int(row["max_uses"]) else "active"
            )
            db.execute(
                "UPDATE sessions SET uses=?, state=? WHERE session_id=?",
                (uses, state_after, session_id),
            )
            self._audit(
                db,
                now,
                "grant_issued",
                session_id,
                grant_id,
                self.approver if high_risk else row["requester_subject"],
                {
                    "action": action,
                    "uses": uses,
                    "max_uses": row["max_uses"],
                    "resource_ref": _reference(
                        f"{repository}/{service}/{target}"
                    ),
                },
            )
        return {
            "grant_id": grant_id,
            "expires_at": min(now + GRANT_TTL_SECONDS, int(row["expires_at"])),
            "one_time": True,
            "redeemable": high_risk,
            "status": "issued" if high_risk else "recorded",
            "action": action,
        }

    def claim(self, payload: Any, *, authenticated_request_id: str) -> dict[str, Any]:
        """Atomically validate and consume one maintenance action."""
        item = _exact_object(
            payload,
            {
                "session_id",
                "digest",
                "repository",
                "service",
                "action",
                "target",
                "request_id",
            },
            {"grant_id"},
        )
        session_id = _bounded_text(
            item["session_id"], maximum=64, pattern=IDENTIFIER
        )
        supplied_digest = _bounded_text(
            item["digest"], maximum=64, pattern=re.compile(r"^[a-f0-9]{64}$")
        )
        repository = _bounded_text(
            item["repository"], maximum=128, pattern=IDENTIFIER
        )
        service = _bounded_text(
            item["service"], maximum=128, pattern=IDENTIFIER
        )
        action = _bounded_text(
            item["action"], maximum=64, pattern=IDENTIFIER
        )
        target = _bounded_text(item["target"], maximum=256, pattern=TARGET)
        request_id = _bounded_text(
            item["request_id"], maximum=128, pattern=IDENTIFIER
        )
        if not hmac.compare_digest(request_id, authenticated_request_id):
            raise AuthenticationError("handoff_request_mismatch")
        high_risk = action in HIGH_RISK_ACTIONS
        if action not in ALLOWED_ACTIONS:
            raise ValidationError("wrong_authorization_class")

        now = int(self.clock())
        supplied_grant_id = item.get("grant_id")
        if high_risk:
            if supplied_grant_id is None:
                raise ValidationError("grant_id_required")
            grant_id = _bounded_text(
                supplied_grant_id, maximum=64, pattern=IDENTIFIER
            )
        elif supplied_grant_id is not None:
            raise ValidationError("grant_id_not_allowed")
        else:
            grant_id = secrets.token_hex(24)
        with self._transaction() as db:
            row = self._session_row(db, session_id)
            state = self._expire(db, row, now)
            if state != "active" and not (high_risk and state == "completed"):
                raise ConflictError("session_not_active")
            if now >= int(row["expires_at"]):
                raise ConflictError("session_expired")
            if not hmac.compare_digest(supplied_digest, row["session_digest"]):
                raise ConflictError("digest_mismatch")
            scope = json.loads(row["scope_json"])
            actions = json.loads(row["actions_json"])
            if (
                repository not in scope["repositories"]
                or service not in scope["services"]
                or target not in scope["targets"]
                or action not in actions
            ):
                self._audit(
                    db,
                    now,
                    "claim_denied",
                    session_id,
                    None,
                    None,
                    {
                        "action": action,
                        "denial": "scope_mismatch",
                        "resource_ref": _reference(
                            f"{repository}/{service}/{target}"
                        ),
                    },
                )
                raise ConflictError("scope_mismatch")
            if high_risk:
                grant = db.execute(
                    "SELECT * FROM grants WHERE grant_id=?", (grant_id,)
                ).fetchone()
                if grant is None:
                    raise ConflictError("grant_not_found")
                expected_values = (
                    ("session_id", session_id),
                    ("session_digest", supplied_digest),
                    ("repository", repository),
                    ("service", service),
                    ("action", action),
                    ("target", target),
                    ("request_id", request_id),
                    ("boot_id", self.boot_id),
                )
                if any(
                    not hmac.compare_digest(str(grant[key]), value)
                    for key, value in expected_values
                ):
                    raise ConflictError("grant_mismatch")
                if grant["approval_id"] is None:
                    raise ConflictError("approval_missing")
                if grant["state"] != "issued":
                    raise ConflictError("grant_not_issued")
                if now >= int(grant["expires_at"]):
                    db.execute(
                        "UPDATE grants SET state='expired' WHERE grant_id=?",
                        (grant_id,),
                    )
                    raise ConflictError("grant_expired")
                updated = db.execute(
                    """
                    UPDATE grants SET state='claimed', expires_at=?
                    WHERE grant_id=? AND state='issued'
                    """,
                    (now, grant_id),
                )
                if updated.rowcount != 1:
                    raise ConflictError("replay_detected")
                uses = int(row["uses"])
                state_after = state
            else:
                if int(row["uses"]) >= int(row["max_uses"]):
                    raise ConflictError("uses_exhausted")
                try:
                    db.execute(
                        """
                        INSERT INTO grants VALUES
                          (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            grant_id,
                            session_id,
                            request_id,
                            _digest(secrets.token_bytes(32).hex()),
                            action,
                            repository,
                            service,
                            target,
                            supplied_digest,
                            now,
                            now,
                            "claimed",
                            self.boot_id,
                            None,
                        ),
                    )
                except sqlite3.IntegrityError as error:
                    raise ConflictError("replay_detected") from error
                uses = int(row["uses"]) + 1
                state_after = (
                    "completed" if uses >= int(row["max_uses"]) else "active"
                )
                db.execute(
                    "UPDATE sessions SET uses=?, state=? WHERE session_id=?",
                    (uses, state_after, session_id),
                )
            self._audit(
                db,
                now,
                "grant_claimed",
                session_id,
                grant_id,
                row["requester_subject"],
                {
                    "action": action,
                    "uses": uses,
                    "max_uses": row["max_uses"],
                    "state": state_after,
                    "resource_ref": _reference(
                        f"{repository}/{service}/{target}"
                    ),
                },
            )
        return {
            "receipt_id": grant_id,
            "status": "claimed",
            "action": action,
            "claimed_at": now,
            "session_state": state_after,
            "request_ref": _reference(request_id),
        }

    def _session_row(
        self, db: sqlite3.Connection, session_id: str
    ) -> sqlite3.Row:
        row = db.execute(
            "SELECT * FROM sessions WHERE session_id=?", (session_id,)
        ).fetchone()
        if row is None:
            raise ConflictError("session_not_found")
        return row

    def get_session(self, session_id: str) -> dict[str, Any]:
        session_id = _bounded_text(
            session_id, maximum=64, pattern=IDENTIFIER
        )
        now = int(self.clock())
        with self._transaction() as db:
            row = self._session_row(db, session_id)
            state = self._expire(db, row, now)
            return {
                "session_id": row["session_id"],
                "state": state,
                "requester_ref": _reference(row["requester_subject"]),
                "approver_ref": _reference(row["approver_subject"]),
                "scope": json.loads(row["scope_json"]),
                "allowed_actions": json.loads(row["actions_json"]),
                "issued_at": row["issued_at"],
                "expires_at": row["expires_at"],
                "digest": row["session_digest"],
                "max_uses": row["max_uses"],
                "uses": row["uses"],
            }

    def audit(self, limit: int) -> dict[str, Any]:
        if not 1 <= limit <= 200:
            raise ValidationError("invalid_limit")
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT sequence,occurred_at,event,session_id,grant_id,
                       actor_ref,details_json
                FROM audit_journal ORDER BY sequence DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return {
            "events": [
                {
                    "sequence": row["sequence"],
                    "occurred_at": row["occurred_at"],
                    "event": row["event"],
                    "session_id": row["session_id"],
                    "grant_id": row["grant_id"],
                    "actor_ref": row["actor_ref"],
                    "details": json.loads(row["details_json"]),
                }
                for row in rows
            ]
        }


class CapabilityServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "asgard-maintenance-session"
    sys_version = ""
    store: MaintenanceStore
    handoff_authenticator: HandoffAuthenticator | None = None

    def log_message(self, format: str, *args: Any) -> None:
        return

    def __getattr__(self, name: str) -> Any:
        if name.startswith("do_"):
            return self._unsupported
        raise AttributeError(name)

    def _respond(self, status: int, payload: Any) -> None:
        body = _canonical(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)
        self.close_connection = True

    def _unsupported(self) -> None:
        self._respond(405, {"error": "method_not_allowed"})

    def _request_body(self) -> bytes:
        if self.headers.get_all("Transfer-Encoding"):
            raise ValidationError("invalid_request")
        types = self.headers.get_all("Content-Type", [])
        if len(types) != 1 or types[0].lower() != "application/json":
            raise ValidationError("unsupported_media_type")
        lengths = self.headers.get_all("Content-Length", [])
        if len(lengths) != 1 or not lengths[0].isdigit():
            raise ValidationError("length_required")
        length = int(lengths[0])
        if not 1 <= length <= MAX_REQUEST_BYTES:
            raise ValidationError("request_too_large")
        return self.rfile.read(length)

    def _json_body(self) -> tuple[Any, bytes]:
        body = self._request_body()
        try:
            return json.loads(body), body
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ValidationError("invalid_json") from error

    def _dispatch(self, callback: Callable[[], Any]) -> None:
        try:
            self._respond(200, callback())
        except ValidationError as error:
            code = str(error)
            status = 415 if code == "unsupported_media_type" else 400
            self._respond(status, {"error": code})
        except ConflictError as error:
            self._respond(409, {"error": str(error)})
        except AuthenticationError as error:
            self._respond(401, {"error": str(error)})
        except sqlite3.DatabaseError:
            self._respond(503, {"error": "state_unavailable"})

    def do_GET(self) -> None:
        target = urllib.parse.urlsplit(self.path)
        if target.path == "/healthz" and not target.query:
            self._respond(200, {"status": "ok"})
            return
        match = re.fullmatch(r"/v1/sessions/([A-Za-z0-9_-]+)", target.path)
        if match and not target.query:
            self._dispatch(lambda: self.store.get_session(match.group(1)))
            return
        if target.path == "/v1/audit":
            try:
                query = urllib.parse.parse_qs(
                    target.query, strict_parsing=True
                )
                if set(query) != {"limit"} or len(query["limit"]) != 1:
                    raise ValidationError("invalid_query")
                limit = int(query["limit"][0])
            except (ValueError, ValidationError):
                self._respond(400, {"error": "invalid_query"})
                return
            self._dispatch(lambda: self.store.audit(limit))
            return
        self._respond(404, {"error": "not_found"})

    def do_POST(self) -> None:
        target = urllib.parse.urlsplit(self.path)
        if target.query:
            self._respond(400, {"error": "invalid_request"})
            return
        try:
            payload, body = self._json_body()
        except ValidationError as error:
            code = str(error)
            status = 415 if code == "unsupported_media_type" else 400
            self._respond(status, {"error": code})
            return
        if target.path == "/v1/sessions":
            self._dispatch(lambda: self.store.create_session(payload))
            return
        if target.path == "/internal/v1/claims":
            if self.handoff_authenticator is None:
                self._respond(503, {"error": "handoff_unavailable"})
                return
            try:
                timestamps = self.headers.get_all("X-Asgard-Timestamp", [])
                request_ids = self.headers.get_all("X-Asgard-Request-Id", [])
                signatures = self.headers.get_all("X-Asgard-Signature", [])
                if not (
                    len(timestamps) == len(request_ids) == len(signatures) == 1
                ):
                    raise AuthenticationError("handoff_auth_required")
                authenticated_request_id = self.handoff_authenticator.verify(
                    method="POST",
                    path=target.path,
                    timestamp=timestamps[0],
                    request_id=request_ids[0],
                    signature=signatures[0],
                    body=body,
                )
            except (AuthenticationError, ValidationError) as error:
                self._respond(401, {"error": str(error)})
                return
            self._dispatch(
                lambda: self.store.claim(
                    payload,
                    authenticated_request_id=authenticated_request_id,
                )
            )
            return
        match = re.fullmatch(
            r"/v1/sessions/([A-Za-z0-9_-]+)/(activate|revoke|complete)",
            target.path,
        )
        if match:
            session_id, operation = match.groups()
            if operation == "activate":
                callback = lambda: self.store.activate_session(
                    session_id, payload
                )
            else:
                callback = lambda: self.store.transition(
                    session_id,
                    payload,
                    "revoked" if operation == "revoke" else "completed",
                )
            self._dispatch(callback)
            return
        if target.path in {
            "/v1/grants/scoped",
            "/v1/grants/high-risk",
        }:
            self._dispatch(
                lambda: self.store.authorize(
                    payload, high_risk=target.path.endswith("high-risk")
                )
            )
            return
        self._respond(404, {"error": "not_found"})


def create_server(
    host: str,
    port: int,
    store: MaintenanceStore,
    handoff_authenticator: HandoffAuthenticator | None = None,
) -> CapabilityServer:
    handler = type(
        "BoundHandler",
        (Handler,),
        {
            "store": store,
            "handoff_authenticator": handoff_authenticator,
        },
    )
    return CapabilityServer((host, port), handler)


def main() -> None:
    state_path = Path(
        os.environ.get(
            "MAINTENANCE_SESSION_DB",
            "/data/maintenance-sessions.sqlite3",
        )
    )
    host = os.environ.get("MAINTENANCE_SESSION_HOST", "0.0.0.0")
    try:
        port = int(os.environ.get("MAINTENANCE_SESSION_PORT", "8090"))
    except ValueError as error:
        raise SystemExit("invalid listen port") from error
    requester = os.environ.get("MAINTENANCE_SESSION_REQUESTER", "")
    approver = os.environ.get("MAINTENANCE_SESSION_APPROVER", "")
    handoff_path = Path(
        os.environ.get(
            "MAINTENANCE_HANDOFF_KEY_FILE",
            "/run/maintenance-session-secrets/MAINTENANCE_HANDOFF_KEY",
        )
    )
    try:
        store = MaintenanceStore(
            state_path, requester=requester, approver=approver
        )
        authenticator = (
            HandoffAuthenticator(_secret_file(handoff_path))
            if handoff_path.exists()
            else None
        )
    except (OSError, RuntimeError, ValidationError) as error:
        raise SystemExit("invalid maintenance configuration") from error
    server = create_server(host, port, store, authenticator)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
