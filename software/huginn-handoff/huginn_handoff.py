#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Bounded, authenticated Huginn capture handoff for Muninn.

Raw n8n captures are untrusted and read-only. This service validates and
imports eligible captures into a content-addressed immutable outbox, then
exposes only fixed read, lease, and checkpoint operations.
"""

from __future__ import annotations

import base64
import binascii
import contextlib
import datetime as dt
import hashlib
import hmac
import json
import os
import re
import secrets
import stat
import tempfile
import threading
import time
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

SCHEMA_CAPTURE = "asgard.huginn-capture.v1"
SCHEMA_ENVELOPE = "asgard.huginn-envelope.v1"
SCHEMA_MANIFEST = "asgard.huginn-manifest.v1"
SCHEMA_CHECKPOINT = "asgard.huginn-checkpoint.v1"
SCHEMA_QUARANTINE = "asgard.huginn-quarantine.v1"
HEX64 = re.compile(r"^[a-f0-9]{64}$")
SEMVER_TAG = re.compile(r"^v?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
SAFE_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
SAFE_CAPTURE_NAME = re.compile(
    r"^(?:[1-9][0-9]{0,19}|[a-f0-9]{64})-[0-9A-Za-z]+\.json$"
)
RFC3339 = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
ALLOWED_SOURCE_PREFIX = (
    "https://api.github.com/repos/UsefulSoftwareCo/executor/releases/"
)
EMAIL_SOURCE_PREFIX = "email://inbound/"
OPERATOR_EMAIL_ADDRESSES: frozenset[str] = frozenset()
EMAIL_ADDRESS = re.compile(r"^[^<>,@\s]+@[^<>,@\s]+$")
GMAIL_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
MAX_CAPTURE_BYTES = 2 * 1024 * 1024
MAX_ENVELOPE_BYTES = MAX_CAPTURE_BYTES + 64 * 1024
MAX_REQUEST_BYTES = 64 * 1024


class HandoffError(RuntimeError):
    """A safe operational error that does not contain capture content."""


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def utc_timestamp(value: float | None = None) -> str:
    moment = dt.datetime.fromtimestamp(
        time.time() if value is None else value, tz=dt.timezone.utc
    )
    return moment.isoformat(timespec="microseconds").replace("+00:00", "Z")


def private_dir(path: Path, *, create: bool = True) -> None:
    if create:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(path, 0o700)
    try:
        mode = path.stat().st_mode & 0o777
    except FileNotFoundError as exc:
        raise HandoffError("required private directory does not exist") from exc
    if mode & 0o077:
        raise HandoffError("private directory has group or world permissions")


def read_only_input_dir(path: Path) -> None:
    """Validate a producer-owned directory mounted read-only into this service."""
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise HandoffError("required input directory does not exist") from exc
    mode = stat.S_IMODE(metadata.st_mode)
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISDIR(metadata.st_mode)
        or mode & 0o027
    ):
        raise HandoffError("input directory permissions are not eligible")


def fsync_dir(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_write_new(path: Path, data: bytes, *, mode: int = 0o400) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=".publish-", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_path, mode)
        try:
            os.link(temporary_path, path)
            created = True
        except FileExistsError:
            if not hmac.compare_digest(
                hashlib.sha256(path.read_bytes()).digest(),
                hashlib.sha256(data).digest(),
            ):
                raise HandoffError("immutable object conflict")
            created = False
        fsync_dir(path.parent)
        return created
    finally:
        with contextlib.suppress(FileNotFoundError):
            temporary_path.unlink()


def atomic_replace_private(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=".state-", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(canonical_json(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        os.chmod(path, 0o600)
        fsync_dir(path.parent)
    finally:
        with contextlib.suppress(FileNotFoundError):
            temporary_path.unlink()


def read_json(path: Path, maximum: int = MAX_CAPTURE_BYTES) -> Any:
    data = path.read_bytes()
    if len(data) > maximum:
        raise HandoffError("JSON object exceeds configured maximum")
    try:
        return json.loads(data)
    except json.JSONDecodeError as exc:
        raise HandoffError("stored JSON is malformed") from exc


def strict_json(data: bytes) -> Any:
    def object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise HandoffError("JSON object contains a duplicate key")
            result[key] = value
        return result

    try:
        return json.loads(data, object_pairs_hook=object_without_duplicates)
    except json.JSONDecodeError as exc:
        raise HandoffError("staged capture JSON is malformed") from exc
    except RecursionError as exc:
        raise HandoffError("staged capture JSON nesting is excessive") from exc


def require_timestamp(value: Any, field: str) -> str:
    if not isinstance(value, str) or not RFC3339.fullmatch(value):
        raise HandoffError(f"capture {field} is invalid")
    return value


def email_address(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    candidate = value.strip()
    bracketed = re.fullmatch(
        r"[^<>]*<\s*([^<>,@\s]+@[^<>,@\s]+)\s*>\s*", candidate
    )
    if bracketed:
        candidate = bracketed.group(1)
    if not EMAIL_ADDRESS.fullmatch(candidate):
        return ""
    return candidate.lower()


def operator_email_addresses(value: str) -> frozenset[str]:
    addresses = frozenset(
        item.strip().lower() for item in value.split(",") if item.strip()
    )
    if any(email_address(item) != item for item in addresses):
        raise HandoffError("HUGINN_OPERATOR_EMAIL_ADDRESSES is invalid")
    return addresses


def authentication_result_passes(value: str, sender: str) -> bool:
    domain = sender.rsplit("@", 1)[-1] if "@" in sender else ""
    if not domain or len(value.encode("utf-8")) > 8192:
        return False
    quoted = re.escape(domain)
    required = (
        r"(?:^|[;\s])spf=pass(?:\s|;|$)",
        r"(?:^|[;\s])dkim=pass(?:\s|;|$)",
        r"(?:^|[;\s])dmarc=pass(?:\s|;|$)",
        rf"smtp\.mailfrom=[^;\s@]+@{quoted}(?:[;\s]|$)",
        rf"header\.i=(?:[^;\s@]*@)?{quoted}(?:[;\s]|$)",
        rf"header\.from={quoted}(?:[;\s]|$)",
    )
    return value.lstrip().lower().startswith("mx.google.com;") and all(
        re.search(pattern, value, re.IGNORECASE) for pattern in required
    )


def validate_operator_auth(value: Any, from_value: str) -> None:
    fields = {
        "authentication_source",
        "status",
        "claimed_sender",
        "allowlist_match",
        "identity_headers_safe",
        "authentication_results",
        "sender",
        "reply_to",
        "return_path",
        "auto_submitted",
        "precedence",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise HandoffError("email operator authentication fields are invalid")
    if value["authentication_source"] != "gmail_api_metadata_ordered":
        raise HandoffError("email authentication source is invalid")
    for field, maximum in {
        "claimed_sender": 320,
        "sender": 4096,
        "reply_to": 4096,
        "return_path": 4096,
        "auto_submitted": 128,
        "precedence": 128,
    }.items():
        item = value[field]
        if not isinstance(item, str) or len(item.encode("utf-8")) > maximum:
            raise HandoffError("email operator authentication value is invalid")
    results = value["authentication_results"]
    if (
        not isinstance(results, list)
        or len(results) > 8
        or any(
            not isinstance(item, str) or len(item.encode("utf-8")) > 8192
            for item in results
        )
    ):
        raise HandoffError("email authentication results are invalid")
    claimed = email_address(from_value)
    sender = email_address(value["sender"])
    reply_to = email_address(value["reply_to"])
    return_path = email_address(value["return_path"])
    allowlisted = claimed in OPERATOR_EMAIL_ADDRESSES
    identity_headers_safe = (
        (not sender or sender == claimed)
        and (not reply_to or reply_to == claimed)
        and (not return_path or return_path == claimed)
        and value["auto_submitted"].lower() in {"", "no"}
        and value["precedence"].lower() not in {"bulk", "junk", "list"}
    )
    authenticated = (
        allowlisted
        and identity_headers_safe
        and bool(results)
        and authentication_result_passes(results[0], claimed)
    )
    expected_status = (
        "operator_authenticated" if authenticated else "external_untrusted"
    )
    if (
        value["status"] != expected_status
        or value["claimed_sender"] != claimed
        or value["allowlist_match"] is not allowlisted
        or value["identity_headers_safe"] is not identity_headers_safe
    ):
        raise HandoffError("email operator authentication is inconsistent")


def validate_email_content(value: Any, message_hash: str) -> None:
    required = {
        "gmail_message_id",
        "gmail_thread_id",
        "message_id",
        "message_id_hash",
        "sent_at",
        "from",
        "to",
        "cc",
        "subject",
        "text",
        "html",
        "operator_auth",
        "attachments",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise HandoffError("email content fields are invalid")
    if value["message_id_hash"] != message_hash:
        raise HandoffError("email message identity is inconsistent")
    if (
        not isinstance(value["gmail_message_id"], str)
        or not GMAIL_ID.fullmatch(value["gmail_message_id"])
        or not isinstance(value["gmail_thread_id"], str)
        or not GMAIL_ID.fullmatch(value["gmail_thread_id"])
    ):
        raise HandoffError("email Gmail identity is invalid")
    require_timestamp(value["sent_at"], "email sent_at")
    limits = {
        "message_id": 1024,
        "from": 4096,
        "to": 8192,
        "cc": 8192,
        "subject": 4096,
        "text": 768 * 1024,
        "html": 768 * 1024,
    }
    for field, maximum in limits.items():
        item = value[field]
        if not isinstance(item, str) or len(item.encode("utf-8")) > maximum:
            raise HandoffError(f"email {field} is invalid")
    if len(value["text"].encode()) + len(value["html"].encode()) > 1024 * 1024:
        raise HandoffError("email body exceeds the combined size limit")
    validate_operator_auth(value["operator_auth"], value["from"])
    attachments = value["attachments"]
    if not isinstance(attachments, list) or len(attachments) > 10:
        raise HandoffError("email attachments are invalid")
    total_bytes = 0
    for attachment in attachments:
        if not isinstance(attachment, dict) or set(attachment) != {
            "filename",
            "mime_type",
            "size",
            "sha256",
            "data_base64",
        }:
            raise HandoffError("email attachment fields are invalid")
        if (
            not isinstance(attachment["filename"], str)
            or not 1 <= len(attachment["filename"].encode()) <= 255
            or not isinstance(attachment["mime_type"], str)
            or not 1 <= len(attachment["mime_type"].encode()) <= 255
            or not isinstance(attachment["size"], int)
            or not 0 <= attachment["size"] <= 256 * 1024
            or not HEX64.fullmatch(str(attachment["sha256"]))
            or not isinstance(attachment["data_base64"], str)
        ):
            raise HandoffError("email attachment value is invalid")
        try:
            decoded = base64.b64decode(attachment["data_base64"], validate=True)
        except (binascii.Error, ValueError) as exc:
            raise HandoffError("email attachment encoding is invalid") from exc
        if (
            len(decoded) != attachment["size"]
            or sha256_bytes(decoded) != attachment["sha256"]
        ):
            raise HandoffError("email attachment integrity is invalid")
        total_bytes += len(decoded)
    if total_bytes > 512 * 1024:
        raise HandoffError("email attachments exceed the combined size limit")


def validate_capture(value: Any, filename: str | None = None) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "schema",
        "capture_version",
        "capture_path",
        "source_url",
        "source_updated_at",
        "collected_at",
        "mime_type",
        "workflow",
        "content",
    }:
        raise HandoffError("capture envelope fields are invalid")
    if value["schema"] != SCHEMA_CAPTURE:
        raise HandoffError("capture schema is invalid")
    if value["mime_type"] != "application/json":
        raise HandoffError("capture MIME type is not allowed")
    workflow = value["workflow"]
    if workflow not in {"executor-release-collector", "inbound-email-collector"}:
        raise HandoffError("capture workflow is not allowed")
    source_url = value["source_url"]
    if not isinstance(source_url, str):
        raise HandoffError("capture source is not allowed")
    require_timestamp(value["source_updated_at"], "source_updated_at")
    require_timestamp(value["collected_at"], "collected_at")
    if (
        not isinstance(value["capture_version"], str)
        or len(value["capture_version"].encode()) > 256
        or not isinstance(value["capture_path"], str)
        or len(value["capture_path"].encode()) > 1024
        or not isinstance(value["content"], dict)
    ):
        raise HandoffError("capture value types are invalid")
    if workflow == "executor-release-collector":
        if not source_url.startswith(ALLOWED_SOURCE_PREFIX) or not source_url[
            len(ALLOWED_SOURCE_PREFIX) :
        ].isdigit():
            raise HandoffError("capture source is not allowed")
        source_id = source_url.removeprefix(ALLOWED_SOURCE_PREFIX)
        content = value["content"]
        if (
            content.get("id") != int(source_id)
            or content.get("draft") is not False
            or content.get("prerelease") is not False
            or not isinstance(content.get("tag_name"), str)
            or not SEMVER_TAG.fullmatch(content["tag_name"])
            or content.get("updated_at") != value["source_updated_at"]
            or content.get("asgard_candidate_schema")
            != "asgard.update-candidate.v1"
            or content.get("asgard_decision") != "review_required"
        ):
            raise HandoffError("release candidate metadata is invalid")
        require_timestamp(content.get("published_at"), "published_at")
        directory = "executor-releases"
    else:
        source_id = source_url.removeprefix(EMAIL_SOURCE_PREFIX)
        if source_url != EMAIL_SOURCE_PREFIX + source_id or not HEX64.fullmatch(
            source_id
        ):
            raise HandoffError("capture source is not allowed")
        validate_email_content(value["content"], source_id)
        directory = "inbound-email"
    expected_version = f"{source_id}:{value['source_updated_at']}"
    safe_updated_at = re.sub(r"[^0-9A-Za-z]", "", value["source_updated_at"])
    expected_filename = f"{source_id}-{safe_updated_at}.json"
    expected_path = f"/home/node/.n8n-files/huginn/{directory}/{expected_filename}"
    if (
        value["capture_version"] != expected_version
        or value["capture_path"] != expected_path
        or (filename is not None and filename != expected_filename)
    ):
        raise HandoffError("capture identity fields are inconsistent")
    return value


class HandoffStore:
    def __init__(self, staging: Path, outbox: Path, state: Path):
        self.staging = staging
        self.outbox = outbox
        self.state = state
        self.lock = threading.RLock()
        read_only_input_dir(staging)
        for path in (
            outbox,
            outbox / "objects",
            outbox / "manifests",
            outbox / "quarantine",
            state,
            state / "leases",
            state / "checkpoints",
        ):
            private_dir(path)

    def _manifest_files(self) -> list[Path]:
        return sorted((self.outbox / "manifests").glob("*.json"))

    def _staged_capture_files(self) -> list[Path]:
        files = list(self.staging.glob("*.json"))
        for directory in ("executor-releases", "inbound-email"):
            candidate = self.staging / directory
            if candidate.exists() or candidate.is_symlink():
                if candidate.is_symlink() or not candidate.is_dir():
                    raise HandoffError("staged capture directory is not eligible")
                files.extend(candidate.glob("*.json"))
        return sorted(files)

    def _validate_manifest_chain(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        prior_hash: str | None = None
        for sequence, path in enumerate(self._manifest_files(), start=1):
            value = read_json(path)
            if (
                not isinstance(value, dict)
                or value.get("schema") != SCHEMA_MANIFEST
                or value.get("sequence") != sequence
                or value.get("prior_manifest_hash") != prior_hash
                or not HEX64.fullmatch(str(value.get("envelope_sha256", "")))
                or not HEX64.fullmatch(str(value.get("content_sha256", "")))
                or path.name != f"{sequence:020d}-{value.get('capture_id', '')}.json"
            ):
                raise HandoffError("immutable manifest chain is invalid")
            object_path = (
                self.outbox
                / "objects"
                / value["envelope_sha256"][:2]
                / f"{value['envelope_sha256']}.json"
            )
            data = object_path.read_bytes()
            if (
                len(data) != value.get("envelope_bytes")
                or sha256_bytes(data) != value["envelope_sha256"]
            ):
                raise HandoffError("immutable envelope integrity check failed")
            try:
                envelope = json.loads(data)
            except json.JSONDecodeError as exc:
                raise HandoffError("immutable envelope is malformed") from exc
            content_bytes = canonical_json(envelope.get("content"))
            if (
                not isinstance(envelope, dict)
                or envelope.get("schema") != SCHEMA_ENVELOPE
                or envelope.get("capture_id") != value.get("capture_id")
                or envelope.get("content_sha256") != value.get("content_sha256")
                or envelope.get("content_bytes") != len(content_bytes)
                or sha256_bytes(content_bytes) != value.get("content_sha256")
                or envelope.get("source_url") != value.get("source_url")
                or envelope.get("source_updated_at") != value.get("source_updated_at")
                or envelope.get("collected_at") != value.get("collected_at")
                or envelope.get("mime_type") != value.get("mime_type")
                or envelope.get("workflow") != value.get("workflow")
                or envelope.get("classification") != "untrusted-external"
            ):
                raise HandoffError("immutable envelope contract is invalid")
            prior_hash = sha256_bytes(path.read_bytes())
            rows.append(value)
        return rows

    def _quarantine_record(self, path: Path, raw: bytes) -> dict[str, Any] | None:
        digest = sha256_bytes(raw)
        record_path = self.outbox / "quarantine" / f"{digest}.meta.json"
        if not record_path.exists():
            return None
        record = read_json(record_path)
        object_path = self.outbox / "quarantine" / f"{digest}.json"
        if (
            not isinstance(record, dict)
            or record.get("schema") != SCHEMA_QUARANTINE
            or record.get("sha256") != digest
            or record.get("bytes") != len(raw)
            or record.get("staged_name") != path.name
            or not object_path.is_file()
            or sha256_bytes(object_path.read_bytes()) != digest
        ):
            raise HandoffError("quarantine record integrity is invalid")
        return record

    def _quarantine_staged(self, path: Path, raw: bytes, reason: str) -> None:
        digest = sha256_bytes(raw)
        quarantine = self.outbox / "quarantine"
        object_path = quarantine / f"{digest}.json"
        record_path = quarantine / f"{digest}.meta.json"
        atomic_write_new(object_path, raw)
        atomic_write_new(
            record_path,
            canonical_json(
                {
                    "schema": SCHEMA_QUARANTINE,
                    "sha256": digest,
                    "bytes": len(raw),
                    "staged_name": path.name,
                    "reason": reason,
                    "quarantined_at": utc_timestamp(),
                }
            ),
        )
        print(
            json.dumps(
                {
                    "event": "huginn_capture_quarantined",
                    "sha256": digest,
                    "reason": reason,
                },
                sort_keys=True,
            ),
            flush=True,
        )

    def import_staged(self) -> int:
        imported = 0
        with self.lock:
            manifests = self._validate_manifest_chain()
            known = {row["capture_id"] for row in manifests}
            for path in self._staged_capture_files():
                path_stat = path.lstat()
                if (
                    not stat.S_ISREG(path_stat.st_mode)
                    or path.is_symlink()
                    or path_stat.st_size > MAX_CAPTURE_BYTES
                    or not SAFE_CAPTURE_NAME.fullmatch(path.name)
                ):
                    raise HandoffError("staged capture file is not eligible")
                raw = path.read_bytes()
                if self._quarantine_record(path, raw) is not None:
                    continue
                try:
                    decoded = strict_json(raw)
                    capture = validate_capture(decoded, path.name)
                except HandoffError as exc:
                    self._quarantine_staged(path, raw, str(exc))
                    continue
                try:
                    content_bytes = canonical_json(capture["content"])
                except RecursionError as exc:
                    raise HandoffError("capture content nesting is excessive") from exc
                content_sha256 = sha256_bytes(content_bytes)
                capture_id = sha256_bytes(
                    canonical_json(
                        {
                            "schema": SCHEMA_CAPTURE,
                            "workflow": capture["workflow"],
                            "source_url": capture["source_url"],
                            "capture_version": capture["capture_version"],
                            "content_sha256": content_sha256,
                        }
                    )
                )
                if capture_id in known:
                    continue
                envelope = {
                    "schema": SCHEMA_ENVELOPE,
                    "capture_id": capture_id,
                    "source_url": capture["source_url"],
                    "source_updated_at": capture["source_updated_at"],
                    "collected_at": capture["collected_at"],
                    "mime_type": capture["mime_type"],
                    "workflow": capture["workflow"],
                    "capture_version": capture["capture_version"],
                    "content_sha256": content_sha256,
                    "content_bytes": len(content_bytes),
                    "classification": "untrusted-external",
                    "content": capture["content"],
                }
                envelope_bytes = canonical_json(envelope)
                envelope_sha256 = sha256_bytes(envelope_bytes)
                object_path = (
                    self.outbox
                    / "objects"
                    / envelope_sha256[:2]
                    / f"{envelope_sha256}.json"
                )
                atomic_write_new(object_path, envelope_bytes)
                sequence = len(manifests) + 1
                prior_path = self._manifest_files()[-1] if manifests else None
                manifest = {
                    "schema": SCHEMA_MANIFEST,
                    "sequence": sequence,
                    "capture_id": capture_id,
                    "envelope_sha256": envelope_sha256,
                    "envelope_bytes": len(envelope_bytes),
                    "content_sha256": content_sha256,
                    "source_url": capture["source_url"],
                    "source_updated_at": capture["source_updated_at"],
                    "collected_at": capture["collected_at"],
                    "mime_type": capture["mime_type"],
                    "workflow": capture["workflow"],
                    "prior_manifest_hash": (
                        sha256_bytes(prior_path.read_bytes()) if prior_path else None
                    ),
                    "imported_at": utc_timestamp(),
                    "classification": "untrusted-external",
                }
                manifest_path = (
                    self.outbox / "manifests" / f"{sequence:020d}-{capture_id}.json"
                )
                atomic_write_new(manifest_path, canonical_json(manifest))
                manifests.append(manifest)
                known.add(capture_id)
                imported += 1
                print(
                    json.dumps(
                        {
                            "event": "huginn_capture_imported",
                            "sequence": sequence,
                            "capture_id": capture_id,
                            "content_sha256": content_sha256,
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
        return imported

    def manifests_after(self, cursor: int, limit: int) -> list[dict[str, Any]]:
        self.import_staged()
        manifests = self._validate_manifest_chain()
        paths = self._manifest_files()
        return [
            {
                "manifest": manifest,
                "manifest_hash": sha256_bytes(paths[index].read_bytes()),
            }
            for index, manifest in enumerate(manifests)
            if manifest["sequence"] > cursor
        ][:limit]

    def envelope(self, capture_id: str) -> dict[str, Any]:
        if not HEX64.fullmatch(capture_id):
            raise HandoffError("invalid capture identifier")
        self.import_staged()
        matches = [
            row
            for row in self._validate_manifest_chain()
            if row["capture_id"] == capture_id
        ]
        if len(matches) != 1:
            raise FileNotFoundError
        row = matches[0]
        return read_json(
            self.outbox
            / "objects"
            / row["envelope_sha256"][:2]
            / f"{row['envelope_sha256']}.json",
            MAX_ENVELOPE_BYTES,
        )

    def _lease_path(self, name: str) -> Path:
        if not SAFE_NAME.fullmatch(name):
            raise HandoffError("invalid lease name")
        return self.state / "leases" / f"{name}.json"

    def _checkpoint_path(self, name: str) -> Path:
        if not SAFE_NAME.fullmatch(name):
            raise HandoffError("invalid checkpoint name")
        return self.state / "checkpoints" / f"{name}.json"

    def acquire(self, name: str, worker: str, ttl: int) -> dict[str, Any]:
        now = time.time()
        path = self._lease_path(name)
        with self.lock:
            current = read_json(path) if path.exists() else None
            if current and float(current.get("expires_at_epoch", 0)) > now:
                raise PermissionError
            token = secrets.token_urlsafe(32)
            lease = {
                "name": name,
                "worker_id": worker,
                "token_hash": sha256_bytes(token.encode()),
                "expires_at_epoch": now + ttl,
                "expires_at": utc_timestamp(now + ttl),
            }
            atomic_replace_private(path, lease)
            return {
                "name": name,
                "worker_id": worker,
                "lease_token": token,
                "expires_at": lease["expires_at"],
            }

    def _lease(self, name: str, token: str) -> dict[str, Any]:
        path = self._lease_path(name)
        if not path.exists():
            raise PermissionError
        lease = read_json(path)
        if float(
            lease.get("expires_at_epoch", 0)
        ) <= time.time() or not hmac.compare_digest(
            str(lease.get("token_hash", "")), sha256_bytes(token.encode())
        ):
            raise PermissionError
        return lease

    def release(self, name: str, token: str) -> dict[str, Any]:
        with self.lock:
            self._lease(name, token)
            self._lease_path(name).unlink()
            fsync_dir(self.state / "leases")
        return {"name": name, "released": True}

    def checkpoint(self, name: str) -> dict[str, Any]:
        path = self._checkpoint_path(name)
        if path.exists():
            return read_json(path)
        return {
            "schema": SCHEMA_CHECKPOINT,
            "name": name,
            "version": 0,
            "manifest_sequence": 0,
            "manifest_hash": None,
            "updated_at": None,
        }

    def commit(
        self,
        name: str,
        token: str,
        expected_version: int,
        sequence: int,
        manifest_hash: str,
    ) -> dict[str, Any]:
        with self.lock:
            self._lease(name, token)
            manifests = self._validate_manifest_chain()
            paths = self._manifest_files()
            if sequence < 1 or sequence > len(manifests):
                raise HandoffError("checkpoint manifest does not exist")
            actual = sha256_bytes(paths[sequence - 1].read_bytes())
            if not hmac.compare_digest(actual, manifest_hash):
                raise HandoffError("checkpoint manifest hash mismatch")
            current = self.checkpoint(name)
            if (
                current["version"] == expected_version + 1
                and current["manifest_sequence"] == sequence
                and current["manifest_hash"] == manifest_hash
            ):
                return current
            if current["version"] != expected_version:
                raise FileExistsError
            if sequence != current["manifest_sequence"] + 1:
                raise FileExistsError
            value = {
                "schema": SCHEMA_CHECKPOINT,
                "name": name,
                "version": expected_version + 1,
                "manifest_sequence": sequence,
                "manifest_hash": manifest_hash,
                "updated_at": utc_timestamp(),
            }
            atomic_replace_private(self._checkpoint_path(name), value)
            print(
                json.dumps(
                    {
                        "event": "huginn_checkpoint_committed",
                        "job": name,
                        "sequence": sequence,
                        "manifest_hash": manifest_hash,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            return value


class Handler(BaseHTTPRequestHandler):
    server_version = "AsgardHuginnHandoff/1"
    sys_version = ""

    @property
    def app(self) -> Server:
        return self.server  # type: ignore[return-value]

    def log_message(self, _format: str, *args: Any) -> None:
        return

    def authorized(self) -> bool:
        header = self.headers.get("Authorization", "")
        supplied = header[7:].strip() if header.startswith("Bearer ") else ""
        return hmac.compare_digest(supplied.encode(), self.app.bearer.encode())

    def respond(self, status: int, value: Any) -> None:
        data = canonical_json(value)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise HandoffError("invalid request length") from exc
        if length < 2 or length > MAX_REQUEST_BYTES:
            raise HandoffError("invalid request body size")
        try:
            value = json.loads(self.rfile.read(length))
        except json.JSONDecodeError as exc:
            raise HandoffError("invalid request JSON") from exc
        if not isinstance(value, dict):
            raise HandoffError("request body must be an object")
        return value

    def dispatch(self) -> None:
        if not self.authorized():
            self.respond(HTTPStatus.UNAUTHORIZED, {"error": "authentication_failed"})
            return
        parsed = urllib.parse.urlparse(self.path)
        parts = [part for part in parsed.path.split("/") if part]
        store = self.app.store
        try:
            if self.command == "GET" and parts == ["health"] and not parsed.query:
                imported = store.import_staged()
                count = len(store._validate_manifest_chain())
                self.respond(
                    HTTPStatus.OK,
                    {"status": "ok", "manifest_count": count, "imported": imported},
                )
                return
            if self.command == "GET" and parts == ["v1", "manifests"]:
                query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
                if set(query) != {"after", "limit"}:
                    raise HandoffError("manifest query is invalid")
                after, limit = int(query["after"][0]), int(query["limit"][0])
                if after < 0 or not 1 <= limit <= 100:
                    raise HandoffError("manifest query is out of bounds")
                self.respond(
                    HTTPStatus.OK,
                    {"data": store.manifests_after(after, limit), "after": after},
                )
                return
            if (
                self.command == "GET"
                and len(parts) == 3
                and parts[:2] == ["v1", "captures"]
                and not parsed.query
            ):
                self.respond(HTTPStatus.OK, store.envelope(parts[2]))
                return
            if (
                self.command == "GET"
                and parts == ["v1", "checkpoints", "hourly"]
                and not parsed.query
            ):
                self.respond(HTTPStatus.OK, store.checkpoint("hourly"))
                return
            if self.command == "POST" and parts == [
                "v1",
                "leases",
                "acquire",
                "hourly",
            ]:
                body = self.body()
                if set(body) != {"worker_id", "ttl_seconds"}:
                    raise HandoffError("invalid lease request fields")
                if body["worker_id"] != "muninn" or not isinstance(
                    body["ttl_seconds"], int
                ):
                    raise HandoffError("invalid lease request")
                ttl = body["ttl_seconds"]
                if not 30 <= ttl <= 3600:
                    raise HandoffError("invalid lease TTL")
                self.respond(HTTPStatus.OK, store.acquire("hourly", "muninn", ttl))
                return
            if self.command == "POST" and parts == [
                "v1",
                "leases",
                "release",
                "hourly",
            ]:
                body = self.body()
                if set(body) != {"lease_token"} or not isinstance(
                    body["lease_token"], str
                ):
                    raise HandoffError("invalid lease release")
                self.respond(
                    HTTPStatus.OK, store.release("hourly", body["lease_token"])
                )
                return
            if self.command == "POST" and parts == [
                "v1",
                "checkpoints",
                "hourly",
                "commit",
            ]:
                body = self.body()
                required = {
                    "lease_token",
                    "expected_version",
                    "manifest_sequence",
                    "manifest_hash",
                }
                if set(body) != required:
                    raise HandoffError("invalid checkpoint fields")
                self.respond(
                    HTTPStatus.OK,
                    store.commit(
                        "hourly",
                        str(body["lease_token"]),
                        int(body["expected_version"]),
                        int(body["manifest_sequence"]),
                        str(body["manifest_hash"]),
                    ),
                )
                return
            self.respond(HTTPStatus.NOT_FOUND, {"error": "not_found"})
        except FileNotFoundError:
            self.respond(HTTPStatus.NOT_FOUND, {"error": "not_found"})
        except PermissionError:
            self.respond(HTTPStatus.CONFLICT, {"error": "lease_conflict"})
        except FileExistsError:
            self.respond(HTTPStatus.CONFLICT, {"error": "checkpoint_conflict"})
        except (HandoffError, ValueError, TypeError, IndexError) as exc:
            print(
                json.dumps(
                    {
                        "event": "huginn_handoff_validation_failed",
                        "reason": str(exc),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            self.respond(HTTPStatus.BAD_REQUEST, {"error": "validation_failed"})
        except OSError:
            print(
                json.dumps({"event": "huginn_handoff_storage_failed"}, sort_keys=True),
                flush=True,
            )
            self.respond(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "storage_failed"})

    do_GET = dispatch
    do_POST = dispatch

    def reject(self) -> None:
        if not self.authorized():
            self.respond(HTTPStatus.UNAUTHORIZED, {"error": "authentication_failed"})
        else:
            self.respond(HTTPStatus.METHOD_NOT_ALLOWED, {"error": "method_not_allowed"})

    do_DELETE = reject
    do_PUT = reject
    do_PATCH = reject
    do_HEAD = reject


class Server(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False
    request_queue_size = 32

    def __init__(self, address: tuple[str, int], store: HandoffStore, bearer: str):
        self.store = store
        self.bearer = bearer
        super().__init__(address, Handler)


def main() -> None:
    global OPERATOR_EMAIL_ADDRESSES

    bearer = os.environ.get("HUGINN_HANDOFF_BEARER", "")
    if len(bearer.encode()) < 32:
        raise HandoffError("HUGINN_HANDOFF_BEARER is missing or too short")
    staging = Path(os.environ.get("HUGINN_STAGING_DIR", "/captures"))
    outbox = Path(os.environ.get("HUGINN_OUTBOX_DIR", "/outbox"))
    state = Path(os.environ.get("HUGINN_HANDOFF_STATE_DIR", "/state"))
    OPERATOR_EMAIL_ADDRESSES = operator_email_addresses(
        os.environ.get("HUGINN_OPERATOR_EMAIL_ADDRESSES", "")
    )
    port = int(os.environ.get("HUGINN_HANDOFF_PORT", "8651"))
    if not 1 <= port <= 65535:
        raise HandoffError("invalid handoff port")
    store = HandoffStore(staging, outbox, state)
    store.import_staged()
    Server(("0.0.0.0", port), store, bearer).serve_forever(poll_interval=0.5)


if __name__ == "__main__":
    main()
