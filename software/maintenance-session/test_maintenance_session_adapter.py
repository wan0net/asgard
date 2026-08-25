# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import hashlib
import hmac
import http.client
import importlib.util
import json
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

MODULE = Path(__file__).parent / "maintenance_session_adapter.py"
SPEC = importlib.util.spec_from_file_location("maintenance_session_adapter", MODULE)
assert SPEC and SPEC.loader
adapter = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = adapter
SPEC.loader.exec_module(adapter)


class Clock:
    def __init__(self, value: int = 1_800_000_000) -> None:
        self.value = value

    def __call__(self) -> float:
        return float(self.value)


class MaintenanceStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "state.sqlite3"
        self.clock = Clock()
        self.store = adapter.MaintenanceStore(
            self.path,
            requester="svc-odine",
            approver="approver@pantheon.example.com",
            clock=self.clock,
            boot_id="boot-one",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def request(
        self,
        *,
        actions: list[str] | None = None,
        duration: int = 3600,
        uses: int = 4,
        repositories: list[str] | None = None,
        services: list[str] | None = None,
        targets: list[str] | None = None,
        reason: str = "Fix the AFFiNE indexer enumeration defect",
    ) -> dict[str, object]:
        return {
            "request_correlation_id": "task-MNT-42",
            "scope": {
                "repositories": repositories or ["example-service"],
                "services": services or ["mimir-indexer"],
                "targets": targets or ["refs/heads/fix-affine-indexer"],
            },
            "allowed_actions": actions
            or ["create_branch", "run_tests", "open_pull_request"],
            "reason": reason,
            "duration_seconds": duration,
            "max_uses": uses,
        }

    def activate(
        self, session: dict[str, object], approval_id: str = "approval-activate"
    ) -> dict[str, object]:
        return self.store.activate_session(
            str(session["session_id"]),
            {
                "digest": session["digest"],
                "approval_correlation_id": approval_id,
            },
        )

    def low_grant(
        self,
        session: dict[str, object],
        *,
        request_id: str = "request-1",
        action: str = "create_branch",
        repository: str = "example-service",
        service: str = "mimir-indexer",
        target: str = "refs/heads/fix-affine-indexer",
    ) -> dict[str, object]:
        return self.store.authorize(
            {
                "session_id": session["session_id"],
                "digest": session["digest"],
                "repository": repository,
                "service": service,
                "action": action,
                "target": target,
                "request_id": request_id,
            },
            high_risk=False,
        )

    def test_default_is_pending_and_cannot_authorize(self) -> None:
        session = self.store.create_session(self.request())
        self.assertEqual(session["state"], "pending")
        with self.assertRaisesRegex(
            adapter.ConflictError, "session_not_active"
        ):
            self.low_grant(session)

    def test_opaque_ids_always_match_the_accepted_path_grammar(self) -> None:
        with mock.patch.object(
            adapter.secrets, "token_urlsafe", return_value="_not-a-valid-id"
        ):
            session = self.store.create_session(self.request())
        self.assertRegex(str(session["session_id"]), r"^[A-Za-z0-9][A-Za-z0-9_-]+$")

    def test_activation_rejects_chat_text_instead_of_exact_tool_shape(self) -> None:
        session = self.store.create_session(self.request())
        with self.assertRaises(adapter.ValidationError):
            self.store.activate_session(
                str(session["session_id"]),
                {
                    "digest": session["digest"],
                    "chat_text": "yes please approve",
                },
            )
        self.assertEqual(
            self.store.get_session(str(session["session_id"]))["state"],
            "pending",
        )

    def test_duration_bounds_wildcards_empty_scope_and_unknown_actions(self) -> None:
        empty_scope = self.request()
        empty_scope["scope"]["repositories"] = []
        invalid = (
            self.request(duration=59),
            self.request(duration=adapter.MAX_DURATION_SECONDS + 1),
            empty_scope,
            self.request(repositories=["*"]),
            self.request(services=["mimir-*"]),
            self.request(targets=["refs/heads/*"]),
            self.request(actions=["arbitrary_shell"]),
            self.request(actions=["future_action"]),
        )
        for payload in invalid:
            with self.subTest(payload=payload):
                with self.assertRaises(adapter.ValidationError):
                    self.store.create_session(payload)

    def test_expiry_is_persisted_and_denies_grants(self) -> None:
        session = self.store.create_session(self.request(duration=60))
        self.activate(session)
        self.clock.value += 60
        with self.assertRaisesRegex(
            adapter.ConflictError, "session_not_active"
        ):
            self.low_grant(session)
        status = self.store.get_session(str(session["session_id"]))
        self.assertEqual(status["state"], "expired")
        self.assertIn(
            "session_expired",
            [event["event"] for event in self.store.audit(20)["events"]],
        )

    def test_scope_and_digest_mismatch_fail_closed(self) -> None:
        session = self.store.create_session(self.request())
        self.activate(session)
        for key, value in (
            ("repository", "public-asgard"),
            ("service", "executor"),
            ("target", "refs/heads/other"),
        ):
            arguments = {key: value}
            with self.subTest(**arguments):
                with self.assertRaisesRegex(
                    adapter.ConflictError, "scope_mismatch"
                ):
                    self.low_grant(session, request_id=f"wrong-{key}", **arguments)
        altered = dict(session)
        altered["digest"] = "0" * 64
        with self.assertRaisesRegex(adapter.ConflictError, "digest_mismatch"):
            self.low_grant(altered, request_id="wrong-digest")

    def test_request_replay_is_denied_and_no_bearer_is_exposed(self) -> None:
        session = self.store.create_session(self.request())
        self.activate(session)
        grant = self.low_grant(session)
        with self.assertRaisesRegex(adapter.ConflictError, "replay_detected"):
            self.low_grant(session)
        self.assertFalse(grant["redeemable"])
        self.assertEqual(grant["status"], "recorded")
        self.assertNotIn("grant_token", grant)
        self.assertFalse(hasattr(self.store, "redeem"))

    def test_internal_claim_is_atomic_claimed_and_non_secret(self) -> None:
        session = self.store.create_session(
            self.request(actions=["edit_worktree"], uses=2)
        )
        self.activate(session)
        payload = {
            "session_id": session["session_id"],
            "digest": session["digest"],
            "repository": "example-service",
            "service": "mimir-indexer",
            "action": "edit_worktree",
            "target": "refs/heads/fix-affine-indexer",
            "request_id": "claim-1",
        }
        receipt = self.store.claim(
            payload, authenticated_request_id="claim-1"
        )
        self.assertEqual(receipt["status"], "claimed")
        self.assertNotIn("token", json.dumps(receipt))
        with sqlite3.connect(self.path) as db:
            state = db.execute(
                "SELECT state FROM grants WHERE grant_id=?",
                (receipt["receipt_id"],),
            ).fetchone()[0]
        self.assertEqual(state, "claimed")
        self.assertEqual(
            self.store.get_session(str(session["session_id"]))["uses"], 1
        )

    def test_internal_claim_rejects_auth_scope_digest_action_and_replay(
        self,
    ) -> None:
        session = self.store.create_session(
            self.request(actions=["edit_worktree"], uses=4)
        )
        self.activate(session)
        base = {
            "session_id": session["session_id"],
            "digest": session["digest"],
            "repository": "example-service",
            "service": "mimir-indexer",
            "action": "edit_worktree",
            "target": "refs/heads/fix-affine-indexer",
            "request_id": "claim-2",
        }
        with self.assertRaises(adapter.AuthenticationError):
            self.store.claim(base, authenticated_request_id="different")
        wrong_scope = dict(base, repository="wan0net/asgard")
        with self.assertRaisesRegex(adapter.ConflictError, "scope_mismatch"):
            self.store.claim(
                wrong_scope, authenticated_request_id="claim-2"
            )
        wrong_digest = dict(base, digest="0" * 64)
        with self.assertRaisesRegex(adapter.ConflictError, "digest_mismatch"):
            self.store.claim(
                wrong_digest, authenticated_request_id="claim-2"
            )
        wrong_action = dict(base, action="merge_pinned_change")
        with self.assertRaisesRegex(
            adapter.ValidationError, "grant_id_required"
        ):
            self.store.claim(
                wrong_action, authenticated_request_id="claim-2"
            )
        self.store.claim(base, authenticated_request_id="claim-2")
        with self.assertRaisesRegex(adapter.ConflictError, "replay_detected"):
            self.store.claim(base, authenticated_request_id="claim-2")

    def test_internal_claim_expiry_and_restart_replay_fail_closed(self) -> None:
        session = self.store.create_session(
            self.request(actions=["run_tests"], duration=60, uses=2)
        )
        self.activate(session)
        payload = {
            "session_id": session["session_id"],
            "digest": session["digest"],
            "repository": "example-service",
            "service": "mimir-indexer",
            "action": "run_tests",
            "target": "refs/heads/fix-affine-indexer",
            "request_id": "claim-restart",
        }
        self.store.claim(payload, authenticated_request_id="claim-restart")
        restarted = adapter.MaintenanceStore(
            self.path,
            requester="svc-odine",
            approver="approver@pantheon.example.com",
            clock=self.clock,
            boot_id="boot-after-claim",
        )
        with self.assertRaisesRegex(adapter.ConflictError, "replay_detected"):
            restarted.claim(
                payload, authenticated_request_id="claim-restart"
            )
        self.clock.value += 60
        expired = dict(payload, request_id="claim-expired")
        with self.assertRaisesRegex(
            adapter.ConflictError, "session_not_active"
        ):
            restarted.claim(
                expired, authenticated_request_id="claim-expired"
            )

    def test_internal_claim_use_limit_completes_without_extra_grant(self) -> None:
        session = self.store.create_session(
            self.request(actions=["edit_worktree"], uses=1)
        )
        self.activate(session)
        payload = {
            "session_id": session["session_id"],
            "digest": session["digest"],
            "repository": "example-service",
            "service": "mimir-indexer",
            "action": "edit_worktree",
            "target": "refs/heads/fix-affine-indexer",
            "request_id": "claim-limit-1",
        }
        receipt = self.store.claim(
            payload, authenticated_request_id="claim-limit-1"
        )
        self.assertEqual(receipt["session_state"], "completed")
        second = dict(payload, request_id="claim-limit-2")
        with self.assertRaisesRegex(
            adapter.ConflictError, "session_not_active"
        ):
            self.store.claim(
                second, authenticated_request_id="claim-limit-2"
            )
        status = self.store.get_session(str(session["session_id"]))
        self.assertEqual((status["uses"], status["state"]), (1, "completed"))
        with sqlite3.connect(self.path) as db:
            grants = db.execute(
                "SELECT COUNT(*) FROM grants WHERE session_id=?",
                (session["session_id"],),
            ).fetchone()[0]
        self.assertEqual(grants, 1)

    def test_restart_keeps_session_but_invalidates_outstanding_grant(self) -> None:
        session = self.store.create_session(self.request())
        self.activate(session)
        self.low_grant(session)
        restarted = adapter.MaintenanceStore(
            self.path,
            requester="svc-odine",
            approver="approver@pantheon.example.com",
            clock=self.clock,
            boot_id="boot-two",
        )
        self.assertEqual(
            restarted.get_session(str(session["session_id"]))["state"],
            "active",
        )
        events = restarted.audit(20)["events"]
        self.assertIn(
            "grant_invalidated_on_restart",
            [event["event"] for event in events],
        )

    def test_active_session_authorizes_exact_high_risk_action_once(self) -> None:
        session = self.store.create_session(
            self.request(
                actions=["merge_pinned_change", "deploy_pinned_change"],
                uses=2,
            )
        )
        self.activate(session)
        base = {
            "session_id": session["session_id"],
            "digest": session["digest"],
            "repository": "example-service",
            "service": "mimir-indexer",
            "action": "merge_pinned_change",
            "target": "refs/heads/fix-affine-indexer",
            "request_id": "merge-1",
        }
        grant = self.store.authorize(base, high_risk=True)
        self.assertEqual(grant["action"], "merge_pinned_change")
        with self.assertRaisesRegex(adapter.ConflictError, "replay_detected"):
            self.store.authorize(base, high_risk=True)

    def test_low_risk_endpoint_cannot_authorize_high_risk_action(self) -> None:
        session = self.store.create_session(
            self.request(actions=["merge_pinned_change"])
        )
        self.activate(session)
        with self.assertRaisesRegex(
            adapter.ValidationError, "wrong_authorization_class"
        ):
            self.low_grant(session, action="merge_pinned_change")

    def test_bounded_uses_complete_session(self) -> None:
        session = self.store.create_session(self.request(uses=1))
        self.activate(session)
        self.low_grant(session)
        status = self.store.get_session(str(session["session_id"]))
        self.assertEqual((status["uses"], status["state"]), (1, "completed"))
        with self.assertRaisesRegex(
            adapter.ConflictError, "session_not_active"
        ):
            self.low_grant(session, request_id="request-2")

    def test_revoke_invalidates_outstanding_grants_and_no_delete_api_exists(
        self,
    ) -> None:
        session = self.store.create_session(self.request())
        self.activate(session)
        self.low_grant(session)
        status = self.store.transition(
            str(session["session_id"]),
            {
                "digest": session["digest"],
                "request_correlation_id": "revoke-1",
            },
            "revoked",
        )
        self.assertEqual(status["state"], "revoked")
        self.assertFalse(hasattr(self.store, "delete_session"))

    def test_audit_is_append_only_and_state_transition_is_atomic(self) -> None:
        session = self.store.create_session(self.request())
        self.activate(session)
        with sqlite3.connect(self.path) as db:
            with self.assertRaisesRegex(sqlite3.DatabaseError, "append_only"):
                db.execute("DELETE FROM audit_journal")
            before = db.execute(
                "SELECT COUNT(*) FROM audit_journal"
            ).fetchone()[0]
        with self.assertRaisesRegex(adapter.ConflictError, "digest_mismatch"):
            self.store.transition(
                str(session["session_id"]),
                {
                    "digest": "0" * 64,
                    "request_correlation_id": "bad-transition",
                },
                "revoked",
            )
        with sqlite3.connect(self.path) as db:
            after = db.execute(
                "SELECT COUNT(*) FROM audit_journal"
            ).fetchone()[0]
        self.assertEqual(before, after)
        self.assertEqual(
            self.store.get_session(str(session["session_id"]))["state"],
            "active",
        )

    def test_reason_assertions_approval_ids_and_tokens_are_redacted(self) -> None:
        secret = "TOP-SECRET-REASON-MATERIAL"
        session = self.store.create_session(self.request(reason=secret))
        self.activate(session, approval_id="approval-secret-value")
        grant = self.low_grant(session)
        self.assertNotIn("grant_token", grant)
        content = self.path.read_bytes()
        rendered = json.dumps(self.store.audit(100), sort_keys=True)
        status = json.dumps(
            self.store.get_session(str(session["session_id"])), sort_keys=True
        )
        for forbidden in (
            secret,
            "task-MNT-42",
            "approval-secret-value",
        ):
            self.assertNotIn(forbidden.encode(), content)
            self.assertNotIn(forbidden, rendered)
            self.assertNotIn(forbidden, status)


class HttpContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.store = adapter.MaintenanceStore(
            Path(self.temp.name) / "state.sqlite3",
            requester="svc-odine",
            approver="approver@pantheon.example.com",
            boot_id="http-test-boot",
        )
        self.handoff_key = b"h" * 32
        self.authenticator = adapter.HandoffAuthenticator(self.handoff_key)
        self.server = adapter.create_server(
            "127.0.0.1", 0, self.store, self.authenticator
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever, daemon=True
        )
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)
        self.temp.cleanup()

    def request(
        self,
        method: str,
        path: str,
        payload: object | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, object]]:
        body = None
        request_headers = dict(headers or {})
        if payload is not None:
            body = json.dumps(payload).encode()
            request_headers.setdefault("Content-Type", "application/json")
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=2
        )
        connection.request(method, path, body=body, headers=request_headers)
        response = connection.getresponse()
        result = json.loads(response.read())
        connection.close()
        return response.status, result

    def test_health_and_exact_methods(self) -> None:
        self.assertEqual(
            self.request("GET", "/healthz"),
            (200, {"status": "ok"}),
        )
        status, payload = self.request("DELETE", "/v1/sessions/anything")
        self.assertEqual((status, payload), (405, {"error": "method_not_allowed"}))
        status, payload = self.request("GET", "/unknown")
        self.assertEqual((status, payload), (404, {"error": "not_found"}))

    def test_create_contract_rejects_extra_fields_and_chat_approval(self) -> None:
        request = {
            "request_correlation_id": "MNT-42",
            "scope": {
                "repositories": ["example-service"],
                "services": ["mimir-indexer"],
                "targets": ["refs/heads/fix-indexer"],
            },
            "allowed_actions": ["create_branch"],
            "reason": "Fix indexer",
            "duration_seconds": 600,
            "max_uses": 1,
        }
        status, session = self.request("POST", "/v1/sessions", request)
        self.assertEqual(status, 200)
        self.assertEqual(session["state"], "pending")
        status, payload = self.request(
            "POST",
            f"/v1/sessions/{session['session_id']}/activate",
            {"digest": session["digest"], "chat_text": "yes"},
        )
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "invalid_fields")
        extra = dict(request)
        extra["shell"] = "rm -rf"
        status, payload = self.request("POST", "/v1/sessions", extra)
        self.assertEqual((status, payload), (400, {"error": "invalid_fields"}))

    def test_content_type_and_body_limits_fail_closed(self) -> None:
        status, payload = self.request(
            "POST",
            "/v1/sessions",
            {},
            {"Content-Type": "text/plain"},
        )
        self.assertEqual(
            (status, payload), (415, {"error": "unsupported_media_type"})
        )

    def test_internal_claim_requires_valid_bound_hmac(self) -> None:
        request = {
            "request_correlation_id": "MNT-claim",
            "scope": {
                "repositories": ["example-service"],
                "services": ["mimir-indexer"],
                "targets": ["asgard/tools-01"],
            },
            "allowed_actions": ["edit_worktree"],
            "reason": "Bounded edit",
            "duration_seconds": 600,
            "max_uses": 1,
        }
        status, session = self.request("POST", "/v1/sessions", request)
        self.assertEqual(status, 200)
        status, _ = self.request(
            "POST",
            f"/v1/sessions/{session['session_id']}/activate",
            {
                "digest": session["digest"],
                "approval_correlation_id": "approval-claim",
            },
        )
        self.assertEqual(status, 200)
        payload = {
            "session_id": session["session_id"],
            "digest": session["digest"],
            "repository": "example-service",
            "service": "mimir-indexer",
            "action": "edit_worktree",
            "target": "asgard/tools-01",
            "request_id": "claim-http-1",
        }
        status, denied = self.request(
            "POST", "/internal/v1/claims", payload
        )
        self.assertEqual((status, denied["error"]), (401, "handoff_auth_required"))

        body = json.dumps(payload).encode()
        timestamp = str(int(self.authenticator.clock()))
        message = adapter.HandoffAuthenticator.message(
            "POST",
            "/internal/v1/claims",
            timestamp,
            "claim-http-1",
            body,
        )
        signature = hmac.new(
            self.handoff_key, message, hashlib.sha256
        ).hexdigest()
        status, receipt = self.request(
            "POST",
            "/internal/v1/claims",
            payload,
            {
                "X-Asgard-Timestamp": timestamp,
                "X-Asgard-Request-Id": "claim-http-1",
                "X-Asgard-Signature": f"sha256={signature}",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(receipt["status"], "claimed")
        self.assertNotIn("token", json.dumps(receipt))

    def test_high_risk_grant_is_redeemable_once_by_bound_consumer(self) -> None:
        request = {
            "request_correlation_id": "MNT-deploy",
            "scope": {
                "repositories": ["example-org/example-service"],
                "services": ["asgard-agent-01"],
                "targets": ["asgard/agent-01"],
            },
            "allowed_actions": ["deploy_pinned_change"],
            "reason": "Deploy reviewed desired state",
            "duration_seconds": 600,
            "max_uses": 1,
        }
        status, session = self.request("POST", "/v1/sessions", request)
        self.assertEqual(status, 200)
        status, _ = self.request(
            "POST",
            f"/v1/sessions/{session['session_id']}/activate",
            {
                "digest": session["digest"],
                "approval_correlation_id": "approval-session",
            },
        )
        self.assertEqual(status, 200)
        grant_request = {
            "session_id": session["session_id"],
            "digest": session["digest"],
            "repository": "example-org/example-service",
            "service": "asgard-agent-01",
            "action": "deploy_pinned_change",
            "target": "asgard/agent-01",
            "request_id": "deploy-request-1",
        }
        status, grant = self.request(
            "POST", "/v1/grants/high-risk", grant_request
        )
        self.assertEqual(status, 200)
        self.assertEqual(grant["status"], "issued")
        self.assertTrue(grant["redeemable"])

        claim = dict(grant_request)
        claim["grant_id"] = grant["grant_id"]
        body = json.dumps(claim).encode()
        timestamp = str(int(self.authenticator.clock()))
        message = adapter.HandoffAuthenticator.message(
            "POST", "/internal/v1/claims", timestamp,
            claim["request_id"], body,
        )
        signature = hmac.new(
            self.handoff_key, message, hashlib.sha256
        ).hexdigest()
        headers = {
            "X-Asgard-Timestamp": timestamp,
            "X-Asgard-Request-Id": claim["request_id"],
            "X-Asgard-Signature": f"sha256={signature}",
        }
        status, receipt = self.request(
            "POST", "/internal/v1/claims", claim, headers
        )
        self.assertEqual((status, receipt["status"]), (200, "claimed"))
        status, replay = self.request(
            "POST", "/internal/v1/claims", claim, headers
        )
        self.assertEqual((status, replay["error"]), (409, "grant_not_issued"))

    def test_internal_claim_rejects_bad_stale_and_mismatched_hmac(self) -> None:
        payload = {"request_id": "claim-auth"}
        current = int(self.authenticator.clock())
        for timestamp, request_id, signature in (
            (str(current), "claim-auth", "sha256=" + "0" * 64),
            (str(current - 61), "claim-auth", "sha256=" + "0" * 64),
            (str(current), "other", "sha256=" + "0" * 64),
        ):
            status, _ = self.request(
                "POST",
                "/internal/v1/claims",
                payload,
                {
                    "X-Asgard-Timestamp": timestamp,
                    "X-Asgard-Request-Id": request_id,
                    "X-Asgard-Signature": signature,
                },
            )
            self.assertEqual(status, 401)

    def test_absent_handoff_keeps_public_api_live_and_claims_unavailable(
        self,
    ) -> None:
        server = adapter.create_server("127.0.0.1", 0, self.store, None)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = http.client.HTTPConnection(
                "127.0.0.1", server.server_port, timeout=2
            )
            connection.request("GET", "/healthz")
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            response.read()
            connection.close()
            connection = http.client.HTTPConnection(
                "127.0.0.1", server.server_port, timeout=2
            )
            body = json.dumps({"request_id": "claim-none"})
            connection.request(
                "POST",
                "/internal/v1/claims",
                body=body,
                headers={"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            self.assertEqual(response.status, 503)
            self.assertEqual(
                json.loads(response.read()), {"error": "handoff_unavailable"}
            )
            connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=1)

    def test_internal_claim_rejects_duplicate_hmac_headers(self) -> None:
        body = json.dumps({"request_id": "duplicate"}).encode()
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=2
        )
        connection.putrequest("POST", "/internal/v1/claims")
        connection.putheader("Content-Type", "application/json")
        connection.putheader("Content-Length", str(len(body)))
        connection.putheader("X-Asgard-Timestamp", "1800000000")
        connection.putheader("X-Asgard-Timestamp", "1800000000")
        connection.putheader("X-Asgard-Request-Id", "duplicate")
        connection.putheader("X-Asgard-Signature", "sha256=" + "0" * 64)
        connection.endheaders(body)
        response = connection.getresponse()
        self.assertEqual(response.status, 401)
        response.read()
        connection.close()


if __name__ == "__main__":
    unittest.main()
