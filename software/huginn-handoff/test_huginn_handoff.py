# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("huginn_handoff.py")
SPEC = importlib.util.spec_from_file_location("huginn_handoff", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

TEST_OPERATOR_EMAIL_ADDRESSES = frozenset(
    {
        "operator-alias@pantheon.example.com",
        "operator-primary@pantheon.example.com",
        "operator-recovery@pantheon.example.com",
    }
)
MODULE.OPERATOR_EMAIL_ADDRESSES = TEST_OPERATOR_EMAIL_ADDRESSES


def capture() -> dict:
    return {
        "schema": "asgard.huginn-capture.v1",
        "capture_version": "362619959:2026-07-30T18:17:26Z",
        "capture_path": (
            "/home/node/.n8n-files/huginn/executor-releases/"
            "362619959-20260730T181726Z.json"
        ),
        "source_url": (
            "https://api.github.com/repos/UsefulSoftwareCo/executor/releases/362619959"
        ),
        "source_updated_at": "2026-07-30T18:17:26Z",
        "collected_at": "2026-07-31T08:04:50.378Z",
        "mime_type": "application/json",
        "workflow": "executor-release-collector",
        "content": {
            "id": 362619959,
            "tag_name": "v1.2.3",
            "draft": False,
            "prerelease": False,
            "published_at": "2026-07-30T18:00:00Z",
            "updated_at": "2026-07-30T18:17:26Z",
            "asgard_candidate_schema": "asgard.update-candidate.v1",
            "asgard_decision": "review_required",
            "body": "untrusted release text",
        },
    }


def operator_authentication_results(address: str) -> str:
    domain = address.rsplit("@", 1)[1]
    return (
        "mx.google.com; spf=pass smtp.mailfrom="
        f"{address}; dkim=pass header.i=@{domain}; "
        f"dmarc=pass header.from={domain}"
    )


def email_capture(sender: str = "sender@example.test") -> dict:
    message_id = "<mail-123@example.test>"
    message_hash = hashlib.sha256(message_id.encode()).hexdigest()
    attachment = b"bounded attachment"
    return {
        "schema": "asgard.huginn-capture.v1",
        "capture_version": f"{message_hash}:2026-08-02T00:01:02Z",
        "capture_path": (
            "/home/node/.n8n-files/huginn/inbound-email/"
            f"{message_hash}-20260802T000102Z.json"
        ),
        "source_url": f"email://inbound/{message_hash}",
        "source_updated_at": "2026-08-02T00:01:02Z",
        "collected_at": "2026-08-02T00:01:03Z",
        "mime_type": "application/json",
        "workflow": "inbound-email-collector",
        "content": {
            "gmail_message_id": "18fedcba01234567",
            "gmail_thread_id": "18fedcba01234567",
            "message_id": message_id,
            "message_id_hash": message_hash,
            "sent_at": "2026-08-02T00:01:02Z",
            "from": f"Sender <{sender}>",
            "to": "odine@example.test",
            "cc": "",
            "subject": "Untrusted subject",
            "text": "Untrusted message body",
            "html": "",
            "operator_auth": {
                "authentication_source": "gmail_api_metadata_ordered",
                "status": (
                    "operator_authenticated"
                    if sender in MODULE.OPERATOR_EMAIL_ADDRESSES
                    else "external_untrusted"
                ),
                "claimed_sender": sender,
                "allowlist_match": sender in MODULE.OPERATOR_EMAIL_ADDRESSES,
                "identity_headers_safe": True,
                "authentication_results": [
                    operator_authentication_results(sender)
                ],
                "sender": "",
                "reply_to": "",
                "return_path": f"<{sender}>",
                "auto_submitted": "",
                "precedence": "",
            },
            "attachments": [
                {
                    "filename": "evidence.txt",
                    "mime_type": "text/plain",
                    "size": len(attachment),
                    "sha256": hashlib.sha256(attachment).hexdigest(),
                    "data_base64": base64.b64encode(attachment).decode(),
                }
            ],
        },
    }


class HandoffStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.staging = root / "staging"
        self.outbox = root / "outbox"
        self.state = root / "state"
        for path in (self.staging, self.outbox, self.state):
            path.mkdir(mode=0o700)
            os.chmod(path, 0o700)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_capture(self, value: dict | None = None) -> Path:
        path = self.staging / "362619959-20260730T181726Z.json"
        path.write_text(json.dumps(value or capture()), encoding="utf-8")
        return path

    def test_import_is_content_addressed_and_idempotent(self) -> None:
        self.write_capture()
        store = MODULE.HandoffStore(self.staging, self.outbox, self.state)
        self.assertEqual(store.import_staged(), 1)
        self.assertEqual(store.import_staged(), 0)
        records = store.manifests_after(0, 10)
        self.assertEqual(len(records), 1)
        manifest = records[0]["manifest"]
        envelope = store.envelope(manifest["capture_id"])
        expected = MODULE.sha256_bytes(MODULE.canonical_json(capture()["content"]))
        self.assertEqual(envelope["content_sha256"], expected)
        self.assertEqual(envelope["classification"], "untrusted-external")
        self.assertEqual(manifest["content_sha256"], expected)

    def test_inbound_email_is_validated_imported_and_idempotent(self) -> None:
        candidate = email_capture()
        email_dir = self.staging / "inbound-email"
        email_dir.mkdir(mode=0o700)
        os.chmod(email_dir, 0o700)
        filename = Path(candidate["capture_path"]).name
        (email_dir / filename).write_text(json.dumps(candidate), encoding="utf-8")
        store = MODULE.HandoffStore(self.staging, self.outbox, self.state)
        self.assertEqual(store.import_staged(), 1)
        self.assertEqual(store.import_staged(), 0)
        envelope = store.envelope(store.manifests_after(0, 1)[0]["manifest"]["capture_id"])
        self.assertEqual(envelope["workflow"], "inbound-email-collector")
        self.assertEqual(envelope["classification"], "untrusted-external")

    def test_inbound_email_rejects_tampered_attachment(self) -> None:
        candidate = email_capture()
        candidate["content"]["attachments"][0]["sha256"] = "0" * 64
        with self.assertRaises(MODULE.HandoffError):
            MODULE.validate_capture(candidate, Path(candidate["capture_path"]).name)

    def test_all_operator_aliases_require_aligned_google_authentication(self) -> None:
        for address in sorted(MODULE.OPERATOR_EMAIL_ADDRESSES):
            with self.subTest(address=address):
                candidate = email_capture(address)
                MODULE.validate_capture(candidate, Path(candidate["capture_path"]).name)

    def test_operator_email_configuration_is_explicit_and_validated(self) -> None:
        self.assertEqual(MODULE.operator_email_addresses(""), frozenset())
        self.assertEqual(
            MODULE.operator_email_addresses(
                "operator-primary@pantheon.example.com, operator-alias@example.test"
            ),
            frozenset(
                {
                    "operator-primary@pantheon.example.com",
                    "operator-alias@example.test",
                }
            ),
        )
        with self.assertRaises(MODULE.HandoffError):
            MODULE.operator_email_addresses("not-an-email")

    def test_spoofed_operator_and_reply_redirection_fail_closed(self) -> None:
        candidate = email_capture("operator-primary@pantheon.example.com")
        candidate["content"]["operator_auth"]["authentication_results"] = [
            operator_authentication_results("attacker.example@attacker.example")
        ]
        with self.assertRaises(MODULE.HandoffError):
            MODULE.validate_capture(candidate, Path(candidate["capture_path"]).name)

        candidate = email_capture("operator-alias@pantheon.example.com")
        candidate["content"]["operator_auth"]["reply_to"] = "attacker@example.test"
        with self.assertRaises(MODULE.HandoffError):
            MODULE.validate_capture(candidate, Path(candidate["capture_path"]).name)

    def test_external_email_cannot_claim_operator_status(self) -> None:
        candidate = email_capture()
        candidate["content"]["operator_auth"]["status"] = "operator_authenticated"
        with self.assertRaises(MODULE.HandoffError):
            MODULE.validate_capture(candidate, Path(candidate["capture_path"]).name)

    def test_forged_lower_authentication_result_cannot_override_first_header(self) -> None:
        candidate = email_capture("operator-primary@pantheon.example.com")
        candidate["content"]["operator_auth"].update(
            {
                "status": "external_untrusted",
                "authentication_results": [
                    operator_authentication_results("attacker@attacker.example"),
                    operator_authentication_results("operator-primary@pantheon.example.com"),
                ],
            }
        )
        MODULE.validate_capture(candidate, Path(candidate["capture_path"]).name)
        candidate["content"]["operator_auth"]["status"] = "operator_authenticated"
        with self.assertRaises(MODULE.HandoffError):
            MODULE.validate_capture(candidate, Path(candidate["capture_path"]).name)

    def test_rejects_wrong_source_mime_schema_and_oversize(self) -> None:
        for field, value in (
            ("source_url", "https://attacker.example/release/1"),
            ("mime_type", "text/html"),
            ("schema", "attacker.instructions.v1"),
        ):
            with self.subTest(field=field):
                candidate = capture()
                candidate[field] = value
                with self.assertRaises(MODULE.HandoffError):
                    MODULE.validate_capture(candidate)
        oversized = self.staging / "1-A.json"
        with oversized.open("wb") as stream:
            stream.truncate(MODULE.MAX_CAPTURE_BYTES + 1)
        store = MODULE.HandoffStore(self.staging, self.outbox, self.state)
        with self.assertRaises(MODULE.HandoffError):
            store.import_staged()

    def test_rejects_mutable_or_mismatched_update_candidate(self) -> None:
        for field, value in (
            ("draft", True),
            ("prerelease", True),
            ("tag_name", "latest"),
            ("id", 1),
            ("asgard_decision", "deploy"),
        ):
            with self.subTest(field=field):
                candidate = capture()
                candidate["content"][field] = value
                with self.assertRaises(MODULE.HandoffError):
                    MODULE.validate_capture(candidate)

    def test_symlink_is_rejected(self) -> None:
        target = self.write_capture()
        link = self.staging / "1-A.json"
        link.symlink_to(target)
        store = MODULE.HandoffStore(self.staging, self.outbox, self.state)
        with self.assertRaises(MODULE.HandoffError):
            store.import_staged()

    def test_symlinked_staging_directory_is_rejected(self) -> None:
        target = self.staging / "real-email"
        target.mkdir(mode=0o700)
        (self.staging / "inbound-email").symlink_to(target, target_is_directory=True)
        store = MODULE.HandoffStore(self.staging, self.outbox, self.state)
        with self.assertRaises(MODULE.HandoffError):
            store.import_staged()

    def test_group_readable_staging_root_is_allowed(self) -> None:
        os.chmod(self.staging, 0o750)
        store = MODULE.HandoffStore(self.staging, self.outbox, self.state)
        self.assertEqual(store.import_staged(), 0)

    def test_group_writable_staging_root_is_rejected(self) -> None:
        os.chmod(self.staging, 0o770)
        with self.assertRaises(MODULE.HandoffError):
            MODULE.HandoffStore(self.staging, self.outbox, self.state)

    def test_symlinked_staging_root_is_rejected(self) -> None:
        linked = Path(self.temp.name) / "linked-staging"
        linked.symlink_to(self.staging, target_is_directory=True)
        with self.assertRaises(MODULE.HandoffError):
            MODULE.HandoffStore(linked, self.outbox, self.state)

    def test_invalid_capture_is_quarantined_without_blocking_valid_work(self) -> None:
        path = self.staging / "1-20260730T181726Z.json"
        path.write_bytes(b'{"schema":"asgard.huginn-capture.v1","schema":"other"}')
        valid = self.write_capture()
        store = MODULE.HandoffStore(self.staging, self.outbox, self.state)
        self.assertEqual(store.import_staged(), 1)
        self.assertEqual(store.import_staged(), 0)
        records = list((self.outbox / "quarantine").glob("*.meta.json"))
        objects = [
            candidate
            for candidate in (self.outbox / "quarantine").glob("*.json")
            if not candidate.name.endswith(".meta.json")
        ]
        self.assertEqual(len(records), 1)
        self.assertEqual(len(objects), 1)
        record = json.loads(records[0].read_text())
        self.assertEqual(record["schema"], "asgard.huginn-quarantine.v1")
        self.assertEqual(record["staged_name"], path.name)
        self.assertEqual(
            hashlib.sha256(objects[0].read_bytes()).hexdigest(), record["sha256"]
        )
        self.assertEqual(len(store.manifests_after(0, 10)), 1)
        self.assertTrue(valid.exists())

    def test_quarantine_record_tamper_fails_closed(self) -> None:
        path = self.staging / "1-20260730T181726Z.json"
        path.write_bytes(b'{"schema":"asgard.huginn-capture.v1","schema":"other"}')
        store = MODULE.HandoffStore(self.staging, self.outbox, self.state)
        self.assertEqual(store.import_staged(), 0)
        record = next((self.outbox / "quarantine").glob("*.meta.json"))
        record.chmod(0o600)
        record.write_text("{}")
        with self.assertRaises(MODULE.HandoffError):
            store.import_staged()

    def test_checkpoint_advances_last_and_exact_retry_is_idempotent(self) -> None:
        self.write_capture()
        store = MODULE.HandoffStore(self.staging, self.outbox, self.state)
        record = store.manifests_after(0, 1)[0]
        lease = store.acquire("hourly", "muninn", 60)
        result = store.commit(
            "hourly", lease["lease_token"], 0, 1, record["manifest_hash"]
        )
        retried = store.commit(
            "hourly", lease["lease_token"], 0, 1, record["manifest_hash"]
        )
        self.assertEqual(result, retried)
        self.assertEqual(result["version"], 1)

    def test_failed_processing_leaves_checkpoint_unchanged(self) -> None:
        self.write_capture()
        store = MODULE.HandoffStore(self.staging, self.outbox, self.state)
        store.manifests_after(0, 1)
        lease = store.acquire("hourly", "muninn", 60)
        with self.assertRaises(MODULE.HandoffError):
            store.commit("hourly", lease["lease_token"], 0, 1, "0" * 64)
        self.assertEqual(store.checkpoint("hourly")["manifest_sequence"], 0)

    def test_http_api_requires_the_fixed_bearer(self) -> None:
        self.write_capture()
        store = MODULE.HandoffStore(self.staging, self.outbox, self.state)
        server = MODULE.Server(("127.0.0.1", 0), store, "b" * 32)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            with self.assertRaises(urllib.error.HTTPError) as failure:
                urllib.request.urlopen(base + "/health", timeout=2)
            self.assertEqual(failure.exception.code, 401)
            failure.exception.close()
            request = urllib.request.Request(
                base + "/health", headers={"Authorization": "Bearer " + "b" * 32}
            )
            with urllib.request.urlopen(request, timeout=2) as response:
                payload = json.load(response)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["manifest_count"], 1)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
