"""Regression gates for accidental runtime drift and secret publication."""
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import audit


class AuditTests(unittest.TestCase):
    def test_current_checkout_preserves_all_inherited_paths(self):
        result = audit.audit(REPO)
        self.assertEqual(result["inherited"], 405)
        self.assertEqual(result["unchanged"], 401)

    def test_runtime_change_or_removal_is_rejected(self):
        real = Path.read_bytes
        # Select an actual frozen schema path without changing the working tree.
        target = next(REPO.joinpath("database").glob("*.sql"))
        with patch.object(Path, "read_bytes", lambda p: b"unexpected schema change" if p == target else real(p)):
            with self.assertRaisesRegex(audit.ConfigError, "runtime/source"):
                audit.audit(REPO)
        original = Path.is_file
        with patch.object(Path, "is_file", lambda p: False if p == target else original(p)):
            with self.assertRaisesRegex(audit.ConfigError, "path/type"):
                audit.audit(REPO)

    def test_hcl_identity_change_is_rejected_but_path_hooks_match(self):
        source = audit.git(REPO, "show", audit.BASELINE + ":cluster/live/dev/terragrunt.hcl")
        current = (REPO / "cluster/live/dev/terragrunt.hcl").read_bytes()
        self.assertEqual(audit.normalized_hcl(source), audit.normalized_hcl(current))
        real = Path.read_bytes
        target = REPO / "cluster/live/dev/terragrunt.hcl"
        with patch.object(Path, "read_bytes", lambda p: current.replace(b'"k8s"', b'"new-cluster"') if p == target else real(p)):
            with self.assertRaisesRegex(audit.ConfigError, "dev HCL"):
                audit.audit(REPO)

    def test_secret_findings_never_echo_values_or_paths(self):
        samples = [b"-----BEGIN " + b"OPENSSH PRIVATE KEY-----", b"ghp_" + b"x" * 36,
                   b"github_pat_" + b"x" * 70, b"AKIA" + b"X" * 16, b"SU" + b"A" * 56]
        for data in samples:
            with self.assertRaises(audit.ConfigError) as raised:
                audit.secret_check("docs/private-canary-value.txt", data)
            self.assertNotIn("private-canary-value", str(raised.exception))
            self.assertNotIn(data.decode(), str(raised.exception))
        for name in (".env", "docs/.worker.key", "docs/a.tfstate.backup", "docs/kubeconfig.dev", "docs/.secrets.hcl"):
            with self.assertRaises(audit.ConfigError):
                audit.secret_check(name, b"arbitrary data")
        audit.secret_check(".env.example", b"ENV=dev\nSECRETS_FILE=\n")
        audit.secret_check("cluster/live/dev/.worker.key.pub", b"ssh-ed25519 public data")

    def test_ignored_credentials_are_not_read_and_new_runtime_is_blocked(self):
        original = audit.git
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            ignored = fixture / ".env"
            ignored.write_bytes(b"ghp_" + b"x" * 36)
            (fixture / "LICENSE").write_bytes(b"retained license")
            digest = audit.blob_id(b"retained license")
            def selected(repo, *args):
                if args == ("ls-tree", "-rz", audit.BASELINE):
                    return f"100644 blob {digest}\tLICENSE\0".encode()
                if args == ("ls-files", "--stage", "-z"):
                    return f"100644 {digest} 0\tLICENSE\0".encode()
                if args == ("ls-files", "--others", "--exclude-standard", "-z"):
                    return b""
                self.fail("unexpected Git invocation")
            real = Path.read_bytes
            def read(path):
                if path == ignored:
                    self.fail("ignored operator credentials were read")
                return real(path)
            with patch.object(audit, "git", selected), patch.object(Path, "read_bytes", read):
                self.assertEqual(audit.audit(fixture)["scanned"], 1)
        for candidate in (b"k8s/unreviewed-workload.yaml\0",
                          b"clients/python/client.py\0",
                          b"clients/contracts/fixtures/client.py\0"):
            def extra(repo, *args):
                data = original(repo, *args)
                if args == ("ls-files", "--others", "--exclude-standard", "-z"):
                    data += candidate
                return data
            with patch.object(audit, "git", extra):
                with self.assertRaisesRegex(audit.ConfigError, "outside"):
                    audit.audit(REPO)

    def test_missing_baseline_fails_with_sanitized_diagnostics(self):
        with patch.object(audit.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, b"private-canary", b"private-canary")):
            output = io.StringIO()
            with contextlib.redirect_stderr(output):
                self.assertEqual(audit.main(), 2)
            self.assertNotIn("private-canary", output.getvalue())
            self.assertIn("full history checkout", output.getvalue())
