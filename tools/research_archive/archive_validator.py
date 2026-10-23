#!/usr/bin/env python3
"""Validate a built archive without printing sensitive content."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import PurePosixPath
from urllib.parse import urlsplit

from archive_builder import (ALLOWED_SUFFIXES, MARKDOWN_BANNER, MAX_BYTES, MANIFEST_NAME,
                             PRIVATE_PATH_RE, PRIVATE_URL_RE, TOKEN_PATTERNS, EMAIL_RE)

LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^\s)]+)(?:[^)]*)\)")
URI_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
PROVENANCE_RE = re.compile(r"^`provenance:(?:external|nonincluded)/[0-9a-f]{16}`$")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ValidationError(Exception):
    pass


def _safe_rel(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValidationError("invalid manifest destination")
    p = PurePosixPath(value)
    if p.is_absolute() or any(part in ("", ".", "..") for part in p.parts) or ":" in value:
        raise ValidationError("invalid manifest destination")
    return p.as_posix()


def _scan_text(path: str, rel: str, data: bytes, errors: list[str]) -> str | None:
    if len(data) > MAX_BYTES:
        errors.append(f"{rel}: exceeds 1 MiB")
        return None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        errors.append(f"{rel}: non-text or invalid UTF-8")
        return None
    for line_no, line in enumerate(text.splitlines(), 1):
        category = "email" if EMAIL_RE.search(line) else "private_path" if PRIVATE_PATH_RE.search(line) else "private_url" if PRIVATE_URL_RE.search(line) else "possible_token" if any(p.search(line) for p in TOKEN_PATTERNS) else None
        if category:
            errors.append(f"{rel}:{line_no}: {category}")
    return text


def validate(archive_dir: str) -> list[str]:
    errors: list[str] = []
    manifest_path = os.path.join(archive_dir, MANIFEST_NAME)
    try:
        with open(manifest_path, "rb") as f:
            manifest_raw = f.read(MAX_BYTES + 1)
        if len(manifest_raw) > MAX_BYTES:
            return [f"{MANIFEST_NAME}: exceeds 1 MiB"]
        manifest = json.loads(manifest_raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return [f"{MANIFEST_NAME}: missing or invalid JSON"]
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1 or not isinstance(manifest.get("files"), list):
        return [f"{MANIFEST_NAME}: unsupported schema"]
    hosts = manifest.get("public_url_hosts", [])
    if not isinstance(hosts, list) or any(not isinstance(host, str) for host in hosts):
        errors.append(f"{MANIFEST_NAME}: invalid public URL host allowlist")
        hosts = []
    allowed_hosts = {host.casefold().rstrip(".") for host in hosts}
    _scan_text(manifest_path, MANIFEST_NAME, manifest_raw, errors)
    if not isinstance(manifest.get("redaction_banner"), str) or not manifest["redaction_banner"].strip():
        errors.append(f"{MANIFEST_NAME}: redaction banner missing")

    declared: dict[str, dict] = {}
    destinations: set[str] = set()
    for record in manifest["files"]:
        if not isinstance(record, dict) or not isinstance(record.get("source_ref"), str) or not isinstance(record.get("include"), bool):
            errors.append(f"{MANIFEST_NAME}: malformed file record")
            continue
        if not isinstance(record.get("reason"), str) or not record["reason"].strip():
            errors.append(f"{MANIFEST_NAME}: file record reason missing")
        if not record["include"]:
            continue
        try:
            dest = _safe_rel(record.get("destination"))
        except ValidationError as e:
            errors.append(f"{MANIFEST_NAME}: {e}")
            continue
        if dest in destinations or dest == MANIFEST_NAME:
            errors.append(f"{MANIFEST_NAME}: duplicate or reserved destination")
            continue
        destinations.add(dest)
        declared[dest] = record
        if os.path.splitext(dest)[1].casefold() not in ALLOWED_SUFFIXES:
            errors.append(f"{dest}: disallowed file type")
        for field in ("original_sha256", "export_sha256"):
            value = record.get(field)
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                errors.append(f"{dest}: invalid {field}")

    actual: set[str] = set()
    text_by_path: dict[str, str] = {}
    try:
        root_info = os.lstat(archive_dir)
        if stat.S_ISLNK(root_info.st_mode) or not stat.S_ISDIR(root_info.st_mode):
            return ["archive root is not a plain directory"]
        for base, dirs, names in os.walk(archive_dir, topdown=True, followlinks=False):
            for name in list(dirs):
                full = os.path.join(base, name)
                info = os.lstat(full)
                if stat.S_ISLNK(info.st_mode):
                    errors.append(f"{os.path.relpath(full, archive_dir).replace(os.sep, '/')}: symlink")
                    dirs.remove(name)
            for name in names:
                full = os.path.join(base, name)
                rel = os.path.relpath(full, archive_dir).replace(os.sep, "/")
                info = os.lstat(full)
                if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                    errors.append(f"{rel}: not a plain file")
                    continue
                if rel == MANIFEST_NAME:
                    continue
                if rel != "README.md" and rel not in declared:
                    errors.append(f"{rel}: not declared in manifest")
                actual.add(rel)
                if os.path.splitext(rel)[1].casefold() not in ALLOWED_SUFFIXES:
                    errors.append(f"{rel}: disallowed file type")
                try:
                    with open(full, "rb") as f:
                        data = f.read(MAX_BYTES + 1)
                except OSError:
                    errors.append(f"{rel}: could not be read")
                    continue
                text = _scan_text(full, rel, data, errors)
                if text is not None:
                    text_by_path[rel] = text
                    if rel.casefold().endswith(".json"):
                        try:
                            json.loads(text)
                        except json.JSONDecodeError:
                            errors.append(f"{rel}: invalid JSON")
                record = declared.get(rel)
                if record:
                    if record.get("bytes") != len(data):
                        errors.append(f"{rel}: byte count mismatch")
                    if record.get("export_sha256") != sha256(data):
                        errors.append(f"{rel}: exported hash mismatch")
    except OSError:
        return errors + ["archive tree could not be inspected"]

    for dest in sorted(set(declared) - actual):
        errors.append(f"{dest}: declared file missing")

    # All Markdown destinations must point to an included archive file or an
    # in-document anchor. Provenance refs emitted as inline code are not links.
    all_targets = set(declared) | {MANIFEST_NAME} | ({"README.md"} if "README.md" in text_by_path else set())
    for rel, text in text_by_path.items():
        if not rel.casefold().endswith(".md"):
            continue
        if not text.startswith(MARKDOWN_BANNER):
            errors.append(f"{rel}: sanitized historical evidence banner missing")
        for match in LINK_RE.finditer(text):
            target = match.group(1)
            if target.startswith("#"):
                continue
            if URI_RE.match(target):
                parsed = urlsplit(target)
                host = (parsed.hostname or "").casefold().rstrip(".")
                if parsed.scheme.casefold() not in ("http", "https") or not host or host not in allowed_hosts or parsed.username or parsed.password:
                    errors.append(f"{rel}: external Markdown link is not allowlisted")
                continue
            target_path = target.split("#", 1)[0].split("?", 1)[0]
            if not target_path:
                continue
            joined = os.path.normpath(os.path.join(os.path.dirname(rel), target_path)).replace("\\", "/")
            if joined == ".." or joined.startswith("../") or joined not in all_targets:
                errors.append(f"{rel}: broken relative Markdown link")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", help="archive directory to validate")
    args = parser.parse_args(argv)
    errors = validate(args.archive)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("archive validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
