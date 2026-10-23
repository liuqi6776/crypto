#!/usr/bin/env python3
"""Build a deterministic, sanitized research archive from an explicit JSON spec.

This tool intentionally does not discover files. Every source file must be named
in the spec. Excluded entries are recorded without opening their source paths.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
from urllib.parse import quote, urlsplit
from pathlib import PurePosixPath
from typing import Any

MAX_BYTES = 1024 * 1024
ALLOWED_SUFFIXES = {".md", ".csv", ".json", ".txt"}
MANIFEST_NAME = "archive_manifest.json"
MARKDOWN_BANNER = "> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.\n\n"


class ArchiveError(Exception):
    """Expected input or safety error with non-sensitive diagnostics."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_rel(value: str, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ArchiveError(f"invalid {label} path")
    p = PurePosixPath(value)
    if p.is_absolute() or any(part in ("", ".", "..") for part in p.parts):
        raise ArchiveError(f"invalid {label} path")
    if ":" in value or "\x00" in value:
        raise ArchiveError(f"invalid {label} path")
    return p.as_posix()


def _read_explicit(root: str, rel: str) -> bytes:
    """Read one exact file, refusing symlinks at every component."""
    parts = rel.split("/")
    current = root
    try:
        root_stat = os.lstat(current)
        if not stat.S_ISDIR(root_stat.st_mode) or stat.S_ISLNK(root_stat.st_mode):
            raise ArchiveError("source root is not a plain directory")
        for part in parts:
            current = os.path.join(current, part)
            info = os.lstat(current)
            if stat.S_ISLNK(info.st_mode):
                raise ArchiveError("source path contains a symlink")
        if not stat.S_ISREG(info.st_mode):
            raise ArchiveError("source entry is not a regular file")
        if info.st_size > MAX_BYTES:
            raise ArchiveError("source entry exceeds 1 MiB")
        with open(current, "rb") as f:
            data = f.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ArchiveError("source entry exceeds 1 MiB")
        return data
    except ArchiveError:
        raise
    except (OSError, PermissionError):
        # Never include a source path or OS error text in diagnostics.
        raise ArchiveError("source entry could not be read") from None


def _path_redactor(roots: dict[str, str]):
    # Known source roots are matched first and rendered with stable logical names.
    ordered = sorted(roots.items(), key=lambda item: len(item[1]), reverse=True)
    def normalize_path(value: str) -> str:
        value = value.replace("\\", "/")
        unc = value.startswith("//")
        value = re.sub(r"/+", "/", value)
        if unc:
            value = "/" + value
        return value.rstrip("/")

    normalized = [(name, normalize_path(path)) for name, path in ordered]

    def replace(match: re.Match[str]) -> str:
        raw = match.group(0)
        norm = normalize_path(raw).rstrip(".,;:)")
        low = norm.casefold()
        for name, root in normalized:
            rlow = root.casefold()
            if low == rlow or low.startswith(rlow + "/"):
                tail = norm[len(root):].lstrip("/")
                return f"<SOURCE_ROOT:{name}>" + (f"/{tail}" if tail else "")
        return "<REDACTED_PRIVATE_PATH>"

    # Windows drive paths and common user home paths on Unix. A known root can
    # begin anywhere in one of these matches; the replacement preserves its tail.
    sep = r"(?:\\\\|[\\/])"  # one slash/backslash or a JSON-escaped backslash pair
    pattern = re.compile(
        rf"(?i)(?:(?<![A-Za-z0-9])[A-Z]:{sep}[^\s\"'<>|]+|"
        rf"(?<![A-Za-z0-9:])(?:\\\\\\\\|\\\\|//)[^\\/\s\"'<>|]+{sep}[^\\/\s\"'<>|]+(?:{sep}[^\s\"'<>|]+)*|"
        r"(?<![A-Za-z0-9:])/(?:home|Users)/[^\s\"'<>|]+)"
    )
    return lambda text: pattern.sub(replace, text)


EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
TOKEN_PATTERNS = [
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?token|secret[_-]?key)\s*[:=]\s*[\"']?[A-Za-z0-9_./+=-]{12,}"),
]
PATH_SEP = r"(?:\\\\|[\\/])"
PRIVATE_PATH_RE = re.compile(
    rf"(?i)(?:(?<![A-Za-z0-9])[A-Z]:{PATH_SEP}[^\s\"'<>|]+|"
    rf"(?<![A-Za-z0-9:])(?:\\\\\\\\|\\\\|//)[^\\/\s\"'<>|]+{PATH_SEP}[^\\/\s\"'<>|]+(?:{PATH_SEP}[^\s\"'<>|]+)*|"
    r"(?<![A-Za-z0-9:])/(?:home|Users)/[^\s\"'<>|]+)"
)
PRIVATE_URL_RE = re.compile(
    r"(?i)https?://(?:docs\.google\.com/(?:document|spreadsheets|presentation)/d/[^\s\"'<>)]*|"
    r"drive\.google\.com/file/d/[^\s\"'<>)]*|"
    r"(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?(?:/[^\s\"'<>)]*)?)"
)


def sensitive_category(text: str) -> str | None:
    if EMAIL_RE.search(text):
        return "email"
    if PRIVATE_PATH_RE.search(text):
        return "private_path"
    if any(pattern.search(text) for pattern in TOKEN_PATTERNS):
        return "possible_token"
    return None


def redact_exact_rules(content: str, rules: object, source_ref: str, redactor) -> tuple[str, list[dict[str, Any]]]:
    if rules is None:
        rules = []
    if not isinstance(rules, list):
        raise ArchiveError(f"redactions must be a list for {source_ref}")
    applied: list[dict[str, Any]] = []
    for rule in rules:
        if not isinstance(rule, dict) or not isinstance(rule.get("old"), str) or not rule["old"] or not isinstance(rule.get("new"), str) or not isinstance(rule.get("reason"), str) or not rule["reason"].strip():
            raise ArchiveError(f"invalid redaction rule for {source_ref}")
        old, new = rule["old"], rule["new"]
        count = content.count(old)
        if not count:
            raise ArchiveError(f"redaction rule not found for {source_ref}")
        content = content.replace(old, new)
        applied.append({"reason": redactor(rule["reason"]), "count": count})
    return content, applied


LINK_RE = re.compile(r"(!?\[([^\]]*)\]\()([^\s)]+)([^)]*\))")
URI_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def _source_key(root_name: str, rel: str) -> str:
    return f"{root_name}/{rel}"


def _link_target(source_rel: str, target: str) -> str | None:
    """Lexically resolve an ordinary relative link without touching the FS."""
    target = target.split("#", 1)[0].split("?", 1)[0]
    if not target or target.startswith("/") or URI_RE.match(target):
        return None
    pieces = list(PurePosixPath(source_rel).parent.parts)
    for part in target.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if not pieces:
                return None
            pieces.pop()
        else:
            pieces.append(part)
    return "/".join(pieces)


def _rewrite_markdown(text: str, source_root: str, source_rel: str,
                      included: dict[str, str], dest: str,
                      provenance: list[dict[str, str]], public_url_hosts: set[str]) -> str:
    included_destinations = set(included.values())

    def sub(match: re.Match[str]) -> str:
        whole_prefix, label, target, suffix = match.groups()
        # Keep fragment-only links because they refer within the same document.
        if target.startswith("#"):
            return match.group(0)
        if target == "<PRIVATE_URL_REDACTED>":
            return f"{label} (`<PRIVATE_URL_REDACTED>`)"
        resolved = _link_target(source_rel, target)
        key = _source_key(source_root, resolved) if resolved else ""
        archive_target = included.get(key)
        # Some curated summary files are assembled from multiple source roots;
        # an existing archive-relative sibling is authoritative in that case.
        destination_relative = _link_target(dest, target)
        if destination_relative in included_destinations or destination_relative == MANIFEST_NAME:
            archive_target = destination_relative
        if archive_target:
            rel_target = os.path.relpath(archive_target, os.path.dirname(dest) or ".").replace("\\", "/")
            if target.endswith("#"):
                rel_target += "#"
            frag = "#" + target.split("#", 1)[1] if "#" in target else ""
            query = "?" + target.split("?", 1)[1].split("#", 1)[0] if "?" in target else ""
            return f"{whole_prefix}{rel_target}{query}{frag}{suffix}"
        kind = "external" if URI_RE.match(target) else "nonincluded"
        public_url = False
        if kind == "external":
            parsed = urlsplit(target)
            host = (parsed.hostname or "").casefold()
            public_url = parsed.scheme.casefold() in ("http", "https") and not parsed.username and not parsed.password and host in public_url_hosts
        if kind == "nonincluded" and resolved and not target.startswith(("/", "\\")):
            logical_target = _source_key(source_root, resolved)
            safe_ref = quote(logical_target, safe="/_-.")
            ref = f"provenance:nonincluded/{safe_ref}"
            provenance.append({"ref": ref, "source": _source_key(source_root, source_rel), "target_ref": logical_target, "label": label})
        elif public_url:
            ref = target
            provenance.append({"ref": ref, "source": _source_key(source_root, source_rel), "label": label, "public_url": target})
        else:
            ref = f"provenance:{kind}/{sha256(target.encode('utf-8'))[:16]}"
            provenance.append({"ref": ref, "source": _source_key(source_root, source_rel), "label": label})
        # A code reference communicates that evidence existed without emitting
        # a potentially private URL or a broken local destination.
        if public_url:
            return f"{whole_prefix}{ref}{suffix}"
        return f"{label} (`{ref}`)"

    return LINK_RE.sub(sub, text)


def load_spec(path: str) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ArchiveError("spec could not be read as JSON") from None
    if not isinstance(obj, dict) or not isinstance(obj.get("roots"), dict) or not isinstance(obj.get("entries"), list):
        raise ArchiveError("spec must contain roots and entries")
    for name, root in obj["roots"].items():
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", name) or not isinstance(root, str) or not os.path.isabs(root):
            raise ArchiveError("invalid source root mapping")
    return obj


def build(spec_path: str, output_dir: str) -> dict[str, Any]:
    spec = load_spec(spec_path)
    roots: dict[str, str] = spec["roots"]
    hosts_raw = spec.get("public_url_hosts", [])
    if not isinstance(hosts_raw, list) or any(not isinstance(host, str) or not re.fullmatch(r"[A-Za-z0-9.-]+", host) for host in hosts_raw):
        raise ArchiveError("public_url_hosts must be a list of hostnames")
    public_url_hosts = {host.casefold().rstrip(".") for host in hosts_raw}
    entries = spec["entries"]
    prepared = []
    seen_src: set[str] = set()
    seen_dest: set[str] = set()
    for item in entries:
        if not isinstance(item, dict) or item.get("source_root") not in roots:
            raise ArchiveError("entry has an unknown source root")
        src = _safe_rel(item.get("source"), "source")
        include = item.get("include")
        reason = item.get("reason")
        if not isinstance(include, bool) or not isinstance(reason, str) or not reason.strip():
            raise ArchiveError("entry needs an include flag and reason")
        key = _source_key(item["source_root"], src)
        if key in seen_src:
            raise ArchiveError("duplicate source entry")
        seen_src.add(key)
        dest = None
        if include:
            dest = _safe_rel(item.get("destination"), "destination")
            if dest == MANIFEST_NAME or dest in seen_dest:
                raise ArchiveError("duplicate or reserved destination")
            seen_dest.add(dest)
            if os.path.splitext(src)[1].casefold() not in ALLOWED_SUFFIXES:
                raise ArchiveError("source type is not allowed")
            if os.path.splitext(dest)[1].casefold() not in ALLOWED_SUFFIXES:
                raise ArchiveError("destination type is not allowed")
        prepared.append({**item, "source": src, "destination": dest, "key": key})

    included_dest = {e["key"]: e["destination"] for e in prepared if e["include"]}
    redactor = _path_redactor(roots)
    files: list[dict[str, Any]] = []
    writes: list[tuple[str, bytes]] = []
    provenance: list[dict[str, str]] = []
    for entry in prepared:
        record: dict[str, Any] = {
            "source_ref": entry["key"], "include": entry["include"],
            "reason": redactor(entry["reason"]),
        }
        if not entry["include"]:
            files.append(record)
            continue
        raw = _read_explicit(roots[entry["source_root"]], entry["source"])
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise ArchiveError("included file is not UTF-8 text") from None
        content, entry_redactions = redact_exact_rules(content, entry.get("redactions", []), entry["key"], redactor)
        content = redactor(content)
        content = PRIVATE_URL_RE.sub("<PRIVATE_URL_REDACTED>", content)
        if entry["destination"].casefold().endswith(".md"):
            content = _rewrite_markdown(content, entry["source_root"], entry["source"], included_dest,
                                        entry["destination"], provenance, public_url_hosts)
        if entry["destination"].casefold().endswith(".json"):
            try:
                json.loads(content)
            except json.JSONDecodeError:
                raise ArchiveError(f"redaction produced invalid JSON at {entry['key']}") from None
        # Validate before writing; report only location and category, never values.
        for line_no, line in enumerate(content.splitlines(), 1):
            category = sensitive_category(line)
            if category:
                raise ArchiveError(f"sensitive content at {entry['key']}:{line_no} ({category})")
        if entry["destination"].casefold().endswith(".md"):
            content = MARKDOWN_BANNER + content
        exported = content.encode("utf-8")
        record.update({"destination": entry["destination"], "original_sha256": sha256(raw),
                       "export_sha256": sha256(exported), "bytes": len(exported), "redactions": entry_redactions})
        files.append(record)
        writes.append((entry["destination"], exported))

    manifest = {
        "schema_version": 1,
        "public_url_hosts": sorted(public_url_hosts),
        "redaction_banner": "Sanitized archive. Historical values are preserved; only private paths and link targets may be redacted or rewritten.",
        "files": sorted(files, key=lambda x: x["source_ref"]),
        "provenance": sorted(provenance, key=lambda x: (x["source"], x["ref"], x["label"])),
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    # The output tree is an archive target. Refuse overwrite to avoid stale files
    # and avoid walking it to inspect or remove anything.
    if os.path.exists(output_dir):
        raise ArchiveError("output directory already exists")
    os.makedirs(output_dir)
    try:
        for rel, data in writes:
            target = os.path.join(output_dir, *rel.split("/"))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "xb") as f:
                f.write(data)
        with open(os.path.join(output_dir, MANIFEST_NAME), "xb") as f:
            f.write(manifest_bytes)
    except Exception:
        shutil.rmtree(output_dir, ignore_errors=True)
        raise
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, help="explicit JSON allowlist spec")
    parser.add_argument("--output", required=True, help="new output directory; must not exist")
    args = parser.parse_args(argv)
    try:
        manifest = build(args.spec, args.output)
    except ArchiveError as e:
        print(f"archive build failed: {e}", file=sys.stderr)
        return 2
    print(f"archive built: {len(manifest['files'])} manifest entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
