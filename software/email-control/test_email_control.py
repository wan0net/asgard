# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONTROL = load("email_control", Path(__file__).with_name("email_control.py"))
HANDOFF = load("email_handoff", ROOT / "huginn-handoff" / "huginn_handoff.py")
HANDOFF.OPERATOR_EMAIL_ADDRESSES = frozenset(
    {
        "operator-alias@pantheon.example.com",
        "operator-primary@pantheon.example.com",
        "operator-recovery@pantheon.example.com",
    }
)


def auth_results(address: str) -> str:
    domain = address.rsplit("@", 1)[1]
    return (
        f"mx.google.com; spf=pass smtp.mailfrom={address}; "
        f"dkim=pass header.i=@{domain}; dmarc=pass header.from={domain}"
    )


def capture(address: str) -> dict:
    message_id = f"<control-{address}@example.test>"
    digest = hashlib.sha256(message_id.encode()).hexdigest()
    trusted = address in HANDOFF.OPERATOR_EMAIL_ADDRESSES
    sent = "2026-08-09T00:01:02Z"
    return {
        "schema": "asgard.huginn-capture.v1",
        "capture_version": f"{digest}:{sent}",
        "capture_path": f"/home/node/.n8n-files/huginn/inbound-email/{digest}-20260809T000102Z.json",
        "source_url": f"email://inbound/{digest}",
        "source_updated_at": sent,
        "collected_at": "2026-08-09T00:01:03Z",
        "mime_type": "application/json",
        "workflow": "inbound-email-collector",
        "content": {
            "gmail_message_id": "18fedcba01234567",
            "gmail_thread_id": "18fedcba01234567",
            "message_id": message_id,
            "message_id_hash": digest,
            "sent_at": sent,
            "from": f"Sender <{address}>",
            "to": "operator-primary@pantheon.example.com",
            "cc": "",
            "subject": "Status please",
            "text": "Please send a status reply",
            "html": "",
            "operator_auth": {
                "authentication_source": "gmail_api_metadata_ordered",
                "status": "operator_authenticated" if trusted else "external_untrusted",
                "claimed_sender": address,
                "allowlist_match": trusted,
                "identity_headers_safe": True,
                "authentication_results": [auth_results(address)],
                "sender": "",
                "reply_to": "",
                "return_path": f"<{address}>",
                "auto_submitted": "",
                "precedence": "",
            },
            "attachments": [],
        },
    }


class Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, _size=-1):
        return b"{}"


class EmailControlTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.captures = root / "captures"
        self.captures.mkdir(mode=0o700)
        self.control = CONTROL.EmailControl(
            CONTROL.CaptureStore(self.captures, HANDOFF),
            CONTROL.ReplyLedger(root / "state" / "email.sqlite3"),
            "http://n8n:5678/webhook/asgard-email-thread-reply",
            "n" * 32,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write(self, address: str) -> str:
        value = capture(address)
        digest = value["content"]["message_id_hash"]
        name = Path(value["capture_path"]).name
        (self.captures / name).write_text(json.dumps(value), encoding="utf-8")
        return digest

    def test_all_operator_aliases_are_trusted(self) -> None:
        for address in sorted(HANDOFF.OPERATOR_EMAIL_ADDRESSES):
            with self.subTest(address=address):
                digest = self.write(address)
                self.assertEqual(
                    self.control.message(digest)["operator_auth"]["status"],
                    "operator_authenticated",
                )

    @mock.patch.object(CONTROL.urllib.request, "urlopen", return_value=Response())
    def test_operator_reply_derives_thread_and_never_accepts_recipient(self, send) -> None:
        digest = self.write("operator-primary@pantheon.example.com")
        result = self.control.reply(
            "operator",
            {"request_id": "reply-1", "message_id_hash": digest, "body": "Done."},
        )
        self.assertEqual(result["status"], "sent")
        request = send.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(payload["gmail_message_id"], "18fedcba01234567")
        self.assertEqual(payload["gmail_thread_id"], "18fedcba01234567")
        self.assertNotIn("to", payload)
        self.assertNotIn("cc", payload)
        self.assertNotIn("bcc", payload)

    def test_wrong_trust_lane_is_denied(self) -> None:
        external = self.write("someone@example.test")
        with self.assertRaises(CONTROL.PolicyError):
            self.control.reply(
                "operator",
                {"request_id": "reply-2", "message_id_hash": external, "body": "No"},
            )
        operator = self.write("operator-alias@pantheon.example.com")
        with self.assertRaises(CONTROL.PolicyError):
            self.control.reply(
                "external",
                {
                    "request_id": "reply-3",
                    "message_id_hash": operator,
                    "body": "No",
                    "expected_reply_address": "operator-alias@pantheon.example.com",
                },
            )

    @mock.patch.object(CONTROL.urllib.request, "urlopen", return_value=Response())
    def test_external_reply_requires_exact_visible_derived_destination(self, send) -> None:
        digest = self.write("someone@example.test")
        base = {
            "request_id": "reply-external",
            "message_id_hash": digest,
            "body": "Thanks.",
        }
        with self.assertRaises(CONTROL.PolicyError):
            self.control.reply(
                "external", {**base, "expected_reply_address": "attacker@example.test"}
            )
        result = self.control.reply(
            "external", {**base, "expected_reply_address": "someone@example.test"}
        )
        self.assertEqual(result["reply_target"], "someone@example.test")
        payload = json.loads(send.call_args.args[0].data)
        self.assertNotIn("expected_reply_address", payload)
        self.assertNotIn("to", payload)

    @mock.patch.object(CONTROL.urllib.request, "urlopen", return_value=Response())
    def test_exact_replay_returns_receipt_without_second_send(self, send) -> None:
        digest = self.write("operator-recovery@pantheon.example.com")
        request = {"request_id": "reply-4", "message_id_hash": digest, "body": "Done."}
        self.assertEqual(self.control.reply("operator", request)["status"], "sent")
        self.assertEqual(self.control.reply("operator", request)["status"], "sent")
        self.assertEqual(send.call_count, 1)

    @mock.patch.object(CONTROL.urllib.request, "urlopen", side_effect=OSError("timeout"))
    def test_ambiguous_send_is_never_retried(self, send) -> None:
        digest = self.write("operator-primary@pantheon.example.com")
        request = {"request_id": "reply-5", "message_id_hash": digest, "body": "Done."}
        with self.assertRaises(OSError):
            self.control.reply("operator", request)
        with self.assertRaises(CONTROL.ConflictError):
            self.control.reply("operator", request)
        self.assertEqual(send.call_count, 1)

    def test_spoofed_operator_capture_is_rejected(self) -> None:
        value = capture("operator-primary@pantheon.example.com")
        value["content"]["operator_auth"]["authentication_results"] = [
            auth_results("attacker@example.test")
        ]
        digest = value["content"]["message_id_hash"]
        (self.captures / Path(value["capture_path"]).name).write_text(json.dumps(value))
        with self.assertRaises(CONTROL.PolicyError):
            self.control.message(digest)

if __name__ == "__main__":
    unittest.main()
