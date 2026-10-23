import json
import os
import tempfile
import unittest
from pathlib import Path

import archive_builder
import archive_validator


class ArchiveToolTests(unittest.TestCase):
    def test_redacts_plain_and_json_escaped_windows_paths(self):
        sep = chr(92)
        redact = archive_builder._path_redactor({"report": "C:" + sep + "Users" + sep + "person" + sep + "research"})
        plain = redact("See C:" + sep + "Users" + sep + "someone" + sep + "Documents" + sep + "draft.md")
        escaped_input = '{"path":"C:' + sep * 2 + "Users" + sep * 2 + "someone" + sep * 2 + "Documents" + sep * 2 + 'draft.md"}'
        escaped = redact(escaped_input)
        self.assertNotIn("C:" + sep + "Users", plain)
        self.assertNotIn("C:" + sep * 2 + "Users", escaped)
        self.assertIn("<REDACTED_PRIVATE_PATH>", plain)
        self.assertIn("<REDACTED_PRIVATE_PATH>", escaped)

    def test_redacts_any_drive_path_and_preserves_logical_tail_in_json(self):
        sep = chr(92)
        redact = archive_builder._path_redactor({"dataset": "D:" + sep + "external" + sep + "data"})
        self.assertIn("<REDACTED_PRIVATE_PATH>", redact("D:" + sep + "other" + sep + "private" + sep + "market.csv"))
        source = '{"path":"D:' + sep * 2 + "external" + sep * 2 + "data" + sep * 2 + "tables" + sep * 2 + 'x.csv","n":1.00}'
        result = redact(source)
        self.assertIn(r"<SOURCE_ROOT:dataset>/tables/x.csv", result)
        self.assertEqual(json.loads(result)["n"], 1.0)
        self.assertTrue(result.endswith("1.00}"), "redaction must preserve numeric token spelling")
        unc = redact(sep * 2 + "server" + sep + "share" + sep + "private" + sep + "x.csv")
        self.assertIn("<REDACTED_PRIVATE_PATH>", unc)

    def test_sensitive_categories_do_not_return_values(self):
        sep = chr(92)
        self.assertEqual(archive_builder.sensitive_category("contact a.person" + "@" + "example.org"), "email")
        self.assertEqual(archive_builder.sensitive_category("key=" + "AKIA" + "1234567890ABCDEF"), "possible_token")
        self.assertEqual(archive_builder.sensitive_category("C:" + sep + "Users" + sep + "person" + sep + "private.txt"), "private_path")

    def test_build_rewrites_included_links_and_external_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "source"
            root.mkdir()
            (root / "index.md").write_text(
                "# Archive\n[table](tables/values.csv) [paper](https://example.org/paper) [old](missing.png)\n",
                encoding="utf-8")
            (root / "tables").mkdir()
            (root / "tables" / "values.csv").write_text("year,value\n2024,1\n", encoding="utf-8")
            spec = {
                "roots": {"research": str(root)},
                "public_url_hosts": ["example.org"],
                "entries": [
                    {"source_root": "research", "source": "index.md", "destination": "README.md",
                     "include": True, "reason": "archive landing page"},
                    {"source_root": "research", "source": "tables/values.csv", "destination": "tables/values.csv",
                     "include": True, "reason": "included data table"},
                    {"source_root": "research", "source": "missing.png", "include": False,
                     "reason": "outside allowed report types"},
                ],
            }
            spec_path = Path(temp) / "spec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            out = Path(temp) / "archive"
            manifest = archive_builder.build(str(spec_path), str(out))
            readme = (out / "README.md").read_text(encoding="utf-8")
            self.assertIn("tables/values.csv", readme)
            self.assertIn("[paper](https://example.org/paper)", readme)
            self.assertIn("provenance:nonincluded/research/missing.png", readme)
            self.assertTrue(readme.startswith(archive_builder.MARKDOWN_BANNER))
            self.assertEqual(archive_validator.validate(str(out)), [])
            self.assertEqual(len(manifest["provenance"]), 2)

    def test_cross_root_destination_neighbor_link_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            first = Path(temp) / "first"
            second = Path(temp) / "second"
            first.mkdir()
            second.mkdir()
            (first / "summary.md").write_text("[evidence](evidence.json)\n", encoding="utf-8")
            (second / "evidence.json").write_text('{"kept":true}\n', encoding="utf-8")
            spec = {"roots": {"public": str(first), "evidence": str(second)}, "entries": [
                {"source_root": "public", "source": "summary.md", "destination": "bundle/summary.md",
                 "include": True, "reason": "curated summary"},
                {"source_root": "evidence", "source": "evidence.json", "destination": "bundle/evidence.json",
                 "include": True, "reason": "curated evidence"},
            ]}
            spec_path = Path(temp) / "spec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            out = Path(temp) / "out"
            archive_builder.build(str(spec_path), str(out))
            summary = (out / "bundle" / "summary.md").read_text(encoding="utf-8")
            self.assertIn("[evidence](evidence.json)", summary)
            self.assertEqual(archive_validator.validate(str(out)), [])

    def test_builder_fails_closed_for_email_and_token(self):
        for bad in (("owner" + "@" + "example.org\n"), ("api_key=" + "abcdef0123456789abcdef\n")):
            with self.subTest(bad=bad[:8]), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / "source"
                root.mkdir()
                (root / "report.md").write_text(bad, encoding="utf-8")
                spec = {"roots": {"r": str(root)}, "entries": [{"source_root": "r", "source": "report.md",
                    "destination": "report.md", "include": True, "reason": "test fixture"}]}
                spec_path = Path(temp) / "spec.json"
                spec_path.write_text(json.dumps(spec), encoding="utf-8")
                out = Path(temp) / "out"
                with self.assertRaisesRegex(archive_builder.ArchiveError, r"r/report\.md:\d+ \(") as err:
                    archive_builder.build(str(spec_path), str(out))
                self.assertNotIn(str(root), str(err.exception))
                self.assertFalse(out.exists())

    def test_builder_preserves_only_allowlisted_public_urls_and_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "source"
            root.mkdir()
            (root / "report.md").write_text(
                "[safe](https://docs.example.org/paper) [blocked](https://evil.example/paper) [escape](../../private.csv)\n",
                encoding="utf-8")
            spec = {"roots": {"r": str(root)}, "public_url_hosts": ["docs.example.org"], "entries": [
                {"source_root": "r", "source": "report.md", "destination": "report.md", "include": True, "reason": "test fixture"}]}
            spec_path = Path(temp) / "spec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            out = Path(temp) / "out"
            archive_builder.build(str(spec_path), str(out))
            report = (out / "report.md").read_text(encoding="utf-8")
            self.assertIn("[safe](https://docs.example.org/paper)", report)
            self.assertIn("blocked (`provenance:external/", report)
            self.assertIn("escape (`provenance:nonincluded/", report)
            self.assertEqual(archive_validator.validate(str(out)), [])

    def test_exact_redactions_and_private_urls_are_sanitized_without_manifest_values(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "source"
            root.mkdir()
            private_doc = "https://" + "docs.google.com/" + "document/d/" + "private-id"
            raw_ip = "http://" + "192.0.2.10/" + "private/path"
            old_sentence = "A private internal note must be removed."
            (root / "report.txt").write_text(f"{old_sentence}\n{private_doc}\n{raw_ip}\n", encoding="utf-8")
            spec = {"roots": {"r": str(root)}, "entries": [{
                "source_root": "r", "source": "report.txt", "destination": "report.txt",
                "include": True, "reason": "test fixture", "redactions": [{
                    "old": old_sentence, "new": "[private note removed]", "reason": "remove private narrative"}] }]}
            spec_path = Path(temp) / "spec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            out = Path(temp) / "out"
            manifest = archive_builder.build(str(spec_path), str(out))
            exported = (out / "report.txt").read_text(encoding="utf-8")
            self.assertIn("[private note removed]", exported)
            self.assertEqual(exported.count("<PRIVATE_URL_REDACTED>"), 2)
            manifest_text = (out / archive_builder.MANIFEST_NAME).read_text(encoding="utf-8")
            self.assertNotIn(private_doc, manifest_text)
            self.assertNotIn(old_sentence, manifest_text)
            included_record = next(record for record in manifest["files"] if record.get("include"))
            self.assertEqual(included_record["redactions"], [{"count": 1, "reason": "remove private narrative"}])
            self.assertEqual(archive_validator.validate(str(out)), [])

    def test_missing_exact_redaction_fails_before_output_creation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "source"
            root.mkdir()
            (root / "report.txt").write_text("available text\n", encoding="utf-8")
            spec = {"roots": {"r": str(root)}, "entries": [{
                "source_root": "r", "source": "report.txt", "destination": "report.txt", "include": True,
                "reason": "test fixture", "redactions": [{"old": "absent", "new": "removed", "reason": "private"}]}]}
            spec_path = Path(temp) / "spec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            out = Path(temp) / "out"
            with self.assertRaisesRegex(archive_builder.ArchiveError, "redaction rule not found for r/report.txt"):
                archive_builder.build(str(spec_path), str(out))
            self.assertFalse(out.exists())

    def test_destination_traversal_fails_before_output_creation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "source"
            root.mkdir()
            (root / "ok.md").write_text("safe\n", encoding="utf-8")
            spec = {"roots": {"r": str(root)}, "entries": [{"source_root": "r", "source": "ok.md",
                "destination": "../outside.md", "include": True, "reason": "bad fixture"}]}
            spec_path = Path(temp) / "spec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            out = Path(temp) / "out"
            with self.assertRaises(archive_builder.ArchiveError):
                archive_builder.build(str(spec_path), str(out))
            self.assertFalse(out.exists())

    def test_validator_detects_hash_tampering_and_broken_link(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "source"
            root.mkdir()
            (root / "a.md").write_text("[missing](nope.md)\n", encoding="utf-8")
            spec = {"roots": {"r": str(root)}, "entries": [{"source_root": "r", "source": "a.md",
                "destination": "a.md", "include": True, "reason": "test fixture"}]}
            spec_path = Path(temp) / "spec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            out = Path(temp) / "out"
            archive_builder.build(str(spec_path), str(out))
            (out / "a.md").write_text("tampered\n", encoding="utf-8")
            errors = archive_validator.validate(str(out))
            self.assertTrue(any("hash mismatch" in e for e in errors))
            # This link was externalized as provenance by the builder, so add a
            # deliberately broken relative link to verify Markdown checking.
            (out / "a.md").write_text("[missing](nope.md)\n", encoding="utf-8")
            errors = archive_validator.validate(str(out))
            self.assertTrue(any("broken relative Markdown link" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
