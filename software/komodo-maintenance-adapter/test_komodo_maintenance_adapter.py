# SPDX-License-Identifier: BSD-3-Clause
import importlib.util
import json
import unittest
from pathlib import Path


MODULE = Path(__file__).parent / "komodo_maintenance_adapter.py"
SPEC = importlib.util.spec_from_file_location("komodo_gate", MODULE)
gate_module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(gate_module)


class Response:
    def __init__(self, status, body):
        self.status = status
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, maximum):
        return self.body[:maximum]


class Opener:
    def __init__(self):
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request)
        if len(self.requests) == 1:
            return Response(
                200,
                json.dumps({
                    "status": "claimed",
                    "receipt_id": "a" * 48,
                    "request_ref": "b" * 16,
                }).encode(),
            )
        return Response(200, b'{"execution":"accepted"}')


def request_payload():
    return {
        "session_id": "a" * 48,
        "digest": "b" * 64,
        "grant_id": "c" * 48,
        "request_id": "deploy-20260809-1",
        "repository": "example-org/example-service",
        "service": "example-service",
        "action": "deploy_pinned_change",
        "target": "deploy/example-service",
    }


class GateTests(unittest.TestCase):
    def setUp(self):
        self.opener = Opener()
        self.gate = gate_module.Gate(
            adapter_key=b"a" * 32,
            handoff_key=b"h" * 32,
            komodo_key=b"k" * 32,
            komodo_secret=b"s" * 32,
            komodo_url="https://komodo.example",
            claim_url="http://authority.example/internal/v1/claims",
            procedure="update-example-service",
            fixed_scope={
                "repository": "example-org/example-service",
                "service": "example-service",
                "action": "deploy_pinned_change",
                "target": "deploy/example-service",
            },
            opener=self.opener,
            clock=lambda: 1_800_000_000,
        )

    def test_deploy_claims_before_fixed_procedure(self):
        result = self.gate.deploy(request_payload())
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["procedure"], "update-example-service")
        self.assertEqual(len(self.opener.requests), 2)
        claim = self.opener.requests[0]
        self.assertEqual(
            claim.full_url, "http://authority.example/internal/v1/claims"
        )
        self.assertIn("X-asgard-signature", claim.headers)
        komodo = self.opener.requests[1]
        self.assertEqual(
            komodo.full_url,
            "https://komodo.example/execute/RunProcedure",
        )
        self.assertEqual(
            json.loads(komodo.data), {"procedure": "update-example-service"}
        )

    def test_wrong_scope_fails_before_any_upstream_call(self):
        payload = request_payload()
        payload["target"] = "deploy/another-service"
        with self.assertRaisesRegex(gate_module.ValidationError, "scope_mismatch"):
            self.gate.deploy(payload)
        self.assertEqual(self.opener.requests, [])

    def test_missing_or_wrong_key_is_denied(self):
        for value in (None, "wrong"):
            with self.assertRaises(gate_module.AuthenticationError):
                self.gate.authenticate(value)

    def test_exact_key_is_accepted(self):
        self.gate.authenticate("a" * 32)

    def test_endpoints_and_scope_configuration_fail_closed(self):
        common = {
            "adapter_key": b"a" * 32,
            "handoff_key": b"h" * 32,
            "komodo_key": b"k" * 32,
            "komodo_secret": b"s" * 32,
            "procedure": "update-example-service",
            "fixed_scope": {
                "repository": "example-org/example-service",
                "service": "example-service",
                "action": "deploy_pinned_change",
                "target": "deploy/example-service",
            },
        }
        with self.assertRaisesRegex(RuntimeError, "endpoint_invalid"):
            gate_module.Gate(
                **common,
                komodo_url="http://komodo.example",
                claim_url="http://authority.example/internal/v1/claims",
            )
        with self.assertRaisesRegex(RuntimeError, "endpoint_invalid"):
            gate_module.Gate(
                **common,
                komodo_url="https://komodo.example",
                claim_url="http://user@authority.example/internal/v1/claims",
            )
        with self.assertRaisesRegex(RuntimeError, "scope_configuration_invalid"):
            gate_module.Gate(
                **{**common, "fixed_scope": {"repository": "example"}},
                komodo_url="https://komodo.example",
                claim_url="http://authority.example/internal/v1/claims",
            )


if __name__ == "__main__":
    unittest.main()
