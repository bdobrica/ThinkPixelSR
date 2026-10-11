"""Offline security/compatibility checks; all credentials and paths are fixtures."""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("operator_config", REPO / "scripts/config.py")
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)
SENTINEL = "private-canary-must-not-appear"


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="thinkpixelsr-config-")
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.dev = self.repo / "cluster/live/dev"
        self.dev.mkdir(parents=True)
        (self.repo / "cluster/live/prod").mkdir()
        (self.repo / "cluster/live/prod/terragrunt.hcl").touch()
        shutil.copyfile(REPO / "cluster/live/dev/terragrunt.hcl", self.dev / "terragrunt.hcl")
        (self.repo / "cluster/infra").mkdir()
        shutil.copyfile(REPO / "cluster/infra/variables.tf", self.repo / "cluster/infra/variables.tf")
        self.secrets = self.dev / ".secrets.hcl"
        self.write_secrets()
        for name in config.FILES.values():
            if name != ".secrets.hcl":
                file = self.dev / name
                file.write_text("offline synthetic key fixture\n")
                file.chmod(0o600)

    def write_secrets(self, extra="", cloud='"offline-cloud-fixture"', dns='"offline-dns-fixture"'):
        self.secrets.write_text(f"inputs = {{ hcloud_token = {cloud}\n hetznerdns_token = {dns}\n {extra} }}\n")
        self.secrets.chmod(0o600)

    def load(self, **kwargs):
        kwargs.setdefault("environ", {})
        kwargs.setdefault("overrides", {"ENV": "dev"})
        return config.load_config(repo=self.repo, **kwargs)

    def fails(self, message, **kwargs):
        with self.assertRaisesRegex(config.ConfigError, message) as raised:
            self.load(**kwargs)
        self.assertNotIn(str(self.repo), str(raised.exception))
        self.assertNotIn(SENTINEL, str(raised.exception))

    def test_defaults_and_translation(self):
        selected = self.load()
        self.assertEqual(selected.environment, "dev")
        self.assertEqual(selected.root, self.dev)
        translated = selected.child_environment({"PATH": "/offline"})
        for key, name in config.FILES.items():
            self.assertEqual(translated["TPSR_" + key], str(self.dev / name))
        self.assertEqual(translated["PATH"], "/offline")
        self.assertNotIn("hcloud_token", repr(translated))
        self.assertNotIn(str(self.repo), repr(selected))
        with self.assertRaises(config.ConfigError):
            selected.child_environment({"TF_VAR_hcloud_token": SENTINEL})

    def test_explicit_environment_and_no_prod_fallback(self):
        for value in ("", "qa", SENTINEL, "DEV", " dev "):
            with self.subTest(value=value):
                self.fails("select dev or prod explicitly", overrides={"ENV": value})
        self.fails("select dev or prod explicitly", overrides={})
        self.fails("production configuration is not implemented", overrides={"ENV": "prod"})

    def test_precedence_cli_then_process_then_dotenv_then_path_defaults(self):
        (self.repo / ".env").write_text("ENV=prod\nSECRETS_FILE=absent\n")
        selected = self.load(environ={"ENV": "prod", "SECRETS_FILE": str(self.secrets)}, overrides={"ENV": "dev"})
        self.assertEqual(selected.files["SECRETS_FILE"], self.secrets)
        (self.repo / ".env").write_text("ENV=dev\n")
        self.assertEqual(self.load(overrides={}).environment, "dev")
        self.fails("production configuration", environ={"ENV": "prod"}, overrides={})

    def test_quoted_paths_spaces_comments_and_literal_metacharacters(self):
        file = self.repo / "private files" / "dollar$(ignored)`literal`#name.hcl"
        file.parent.mkdir()
        shutil.copyfile(self.secrets, file)
        file.chmod(0o600)
        (self.repo / ".env").write_text(f" # comment\nENV = 'dev' # selected\nSECRETS_FILE = \"{file.relative_to(self.repo)}\" # path\n")
        with patch.object(config.os, "system", side_effect=AssertionError("no shell")), patch.object(subprocess, "run", side_effect=AssertionError("no subprocess")):
            self.assertEqual(self.load().files["SECRETS_FILE"], file)

    def test_env_parser_rejects_unsafe_or_ambiguous_lines(self):
        cases = ["export ENV=dev", "ENV: dev", "ENV=dev\nENV=prod", "ENV=dev dev", "ENV='dev", 'ENV="dev" tail', "ENV=dev\t", "ENV=dev\x00", f"{SENTINEL}=value", f"HCLOUD_TOKEN={SENTINEL}", "COUNT=1.2", "POOL=master", "REGISTRY=quay.io"]
        for text in cases:
            with self.subTest(text=text):
                with self.assertRaises(config.ConfigError) as raised:
                    config.parse_env(text)
                self.assertNotIn(SENTINEL, str(raised.exception))
        self.assertEqual(config.parse_env('ENV="dev"\r\nSECRETS_FILE=\r\n'), {"ENV": "dev", "SECRETS_FILE": ""})
        self.assertEqual(config.parse_env("SECRETS_FILE='$HOME/keys'"), {"SECRETS_FILE": "$HOME/keys"})

    def test_missing_unreadable_empty_or_directory_inputs(self):
        with patch.object(Path, "read_text", side_effect=PermissionError(SENTINEL)):
            self.fails("Terragrunt configuration: file is missing, unreadable")
        self.secrets.unlink()
        self.fails("SECRETS_FILE: file is missing")
        self.secrets.mkdir()
        self.fails("SECRETS_FILE: expected a nonempty regular file")
        self.secrets.rmdir()
        self.write_secrets()
        file = self.dev / ".worker.key"
        file.write_text("")
        self.fails("WORKER_PRIVATE_KEY_FILE: expected a nonempty regular file")
        file.unlink()
        self.fails("WORKER_PRIVATE_KEY_FILE: file is missing")

    def test_limits_and_malformed_utf8(self):
        self.secrets.write_bytes(b"\xff")
        self.fails("SECRETS_FILE: file is missing, unreadable or not UTF-8")
        self.secrets.write_bytes(b" " * (config.LIMIT + 1))
        self.fails("at most 1 MiB")
        with self.assertRaisesRegex(config.ConfigError, "nesting limit"):
            config.secret_inputs("inputs = " + "{ x = " * 22 + '"x"' + "}" * 22)

    @unittest.skipUnless(os.name == "posix", "POSIX permission validation")
    def test_private_permissions_and_symlink_target(self):
        self.secrets.chmod(0o644)
        self.fails("SECRETS_FILE: remove group/other permissions")
        self.secrets.chmod(0o600)
        key = self.dev / ".master.key"
        target = self.repo / "external-private-key"
        key.rename(target)
        key.symlink_to(target)
        self.assertEqual(self.load().files["MASTER_PRIVATE_KEY_FILE"], target)
        target.chmod(0o644)
        self.fails("MASTER_PRIVATE_KEY_FILE: remove group/other permissions")

    def test_missing_placeholder_and_malformed_tokens(self):
        for cloud, dns in [('""', '"ok"'), ('"dummy"', '"ok"'), ('null', '"ok"'), ('"ok"', '""'), ('"ok"', 'false'), ('"space token"', '"ok"')]:
            with self.subTest(cloud=cloud, dns=dns):
                self.write_secrets(cloud=cloud, dns=dns)
                self.fails("must be a nonempty, non-placeholder")
        self.secrets.write_text('inputs = { hcloud_token = "ok" }')
        self.fails("hetznerdns_token must be")

    def test_literal_hcl_comments_overrides_and_rejections(self):
        self.write_secrets('/* existing override */ cluster_prefix = "local-fixture"\n cluster_domain_aliases = ["example.invalid",]')
        self.load()
        for extra in ['typo_token = "unused"', 'hcloud_token = "duplicate"', 'cluster_prefix = get_env("TOKEN")', 'cluster_prefix = "${run_cmd(\"sh\")}"', 'worker_pools = { master = { count = 1 server_type = "fixture" } }']:
            with self.subTest(extra=extra):
                self.write_secrets(extra)
                self.fails("unknown Terraform input|duplicate|unsupported|retain exactly")
        self.secrets.write_text('locals { dangerous = run_cmd("sh") }\ninputs = {}')
        self.fails("expected literal input data")

    def test_worker_counts_and_control_plane_pool_rejected(self):
        for count in ('"4"', "1.2", "true", "-1", "0", "null"):
            with self.subTest(count=count):
                self.write_secrets(f'worker_pools = {{ api = {{ server_type = "fixture" count = {count} }} monitor = {{ server_type = "fixture" count = 1 }} }}')
                self.fails("count must be a positive integer")
        self.write_secrets('worker_pools = { api = { server_type = "fixture" count = 4 } monitor = { server_type = "fixture" count = 1 } }')
        self.load()  # Data validation only; does not approve or perform scaling.

    def test_ambient_bypasses_unknown_overrides_and_explicit_missing_env_file(self):
        for key in ("TF_VAR_hcloud_token", "TF_VAR_worker_pools", "TPSR_SECRETS_FILE"):
            self.fails("unset ambient", environ={key: SENTINEL})
        self.fails("unknown override key", overrides={"ENV": "dev", "HCLOUD_TOKEN": SENTINEL})
        self.fails(".env: file is missing", env_file=SENTINEL)

    def test_check_is_read_only(self):
        def snapshot():
            return {p.relative_to(self.repo): p.read_bytes() for p in self.repo.rglob("*") if p.is_file()}
        before = snapshot()
        with patch.object(subprocess, "run", side_effect=AssertionError("no subprocess")), patch.object(config.os, "system", side_effect=AssertionError("no shell")):
            self.load()
        self.assertEqual(snapshot(), before)

    def test_cli_redacts_values_paths_and_argparse_failures(self):
        def run(argv):
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), patch.dict(os.environ, {}, clear=True), patch.object(config, "ROOT", self.repo):
                # load_config's default root is bound at definition time.
                original = config.load_config
                def fixture_load(**kwargs):
                    return original(repo=self.repo, **kwargs)
                with patch.object(config, "load_config", side_effect=fixture_load):
                    try:
                        code = config.main(argv)
                    except SystemExit as ex:
                        code = ex.code
            return code, out.getvalue() + err.getvalue()
        code, output = run(["--env", "dev"])
        self.assertEqual(code, 0)
        self.assertIn("Configuration OK", output)
        for args in [["--env", SENTINEL], ["--set", "HCLOUD_TOKEN=" + SENTINEL], ["--env-file", SENTINEL], ["--unexpected-" + SENTINEL]]:
            code, output = run(args)
            self.assertEqual(code, 2)
            self.assertNotIn(SENTINEL, output)
            self.assertNotIn(str(self.repo), output)
        with patch.object(Path, "resolve", side_effect=RuntimeError(SENTINEL)):
            code, output = run(["--env", "dev"])
            self.assertEqual(code, 2)
            self.assertNotIn(SENTINEL, output)

    @unittest.skipUnless(shutil.which("terragrunt") and shutil.which("git"), "optional real Terragrunt compatibility check")
    def test_terragrunt_default_and_translated_inputs_equal_frozen_baseline(self):
        source = subprocess.run(["git", "show", "9e5fc87495832d3a2554965341cbeb43911ff5f5:cluster/live/dev/terragrunt.hcl"], cwd=REPO, capture_output=True)
        if source.returncode:
            self.skipTest("frozen source object unavailable (for example, a shallow checkout)")
        baseline = source.stdout
        changed = (self.dev / "terragrunt.hcl").read_bytes()
        self.load()
        # Block Terraform actions: the stub only answers version detection.
        stub = self.repo / "terraform-fixture"
        marker = self.repo / "unexpected-terraform-action"
        stub.write_text('#!/bin/sh\nif [ "$1" = "-version" ] || [ "$1" = "version" ]; then\n echo "Terraform v1.14.3"\nelse\n touch "' + str(marker) + '"\n exit 99\nfi\n')
        stub.chmod(0o700)
        # Exclude credentials and all TG_* controls inherited from the operator.
        clean = {k: v for k, v in os.environ.items() if k in {"PATH", "HOME", "LANG", "SYSTEMROOT"}}

        def render(environment):
            result = subprocess.run(["terragrunt", "render", "--json", "--disable-dependent-modules", "--no-auto-init", "--tf-path", str(stub), "--log-disable"], cwd=self.dev, env=environment, capture_output=True, timeout=30)
            # Never print subprocess diagnostics or rendered synthetic secrets.
            self.assertEqual(result.returncode, 0, "offline Terragrunt render failed (diagnostics suppressed)")
            return json.loads(result.stdout)["inputs"]

        (self.dev / "terragrunt.hcl").write_bytes(baseline)
        original = render(clean)
        (self.dev / "terragrunt.hcl").write_bytes(changed)
        self.assertEqual(render(clean), original)
        external = self.repo / "private files"
        external.mkdir()
        overrides = {"ENV": "dev"}
        for key, name in config.FILES.items():
            destination = external / name
            shutil.move(self.dev / name, destination)
            destination.chmod(0o600)
            overrides[key] = str(destination)
        translated = self.load(overrides=overrides)
        self.assertEqual(render(translated.child_environment(clean)), original)
        self.assertFalse(marker.exists(), "Terraform was invoked beyond version detection")
        self.assertFalse((self.dev / ".terragrunt-cache").exists())
        self.assertFalse(list(self.repo.rglob("*.tfstate*")))


class IgnoreTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("git"), "git required for ignore checks")
    def test_nested_sensitive_paths_ignored_and_examples_public_files_retained(self):
        hidden = [".env", "nested/.env", "nested/.env.dev", "nested/.secrets.hcl", "nested/dev.secrets.hcl", "nested/dev.secrets.hcl.json", "nested/.master.key", "nested/.worker.key.backup", "nested/id_ed25519", "nested/.ssh/custom", "nested/tls.pem", "nested/kubeconfig", "nested/kubeconfig.dev", "nested/dev.kubeconfig", "nested/.kube/config", "nested/main.tfstate", "nested/main.tfstate.backup", "nested/dev.tfplan", "nested/tfplan", "nested/credentials.tfvars", "nested/credentials.tfvars.json", "nested/terragrunt-debug.tfvars.json", "nested/secrets.local/custom", "nested/.terraform/file", "nested/.terragrunt-cache/file"]
        visible = [".env.example", "nested/.env.example", "nested/.secrets.hcl.example", "nested/dev.secrets.hcl.example", "nested/config.tfvars.example", "nested/config.tfvars.json.example", "cluster/live/dev/.master.key.pub", "cluster/live/dev/.worker.key.pub", "cluster/live/dev/.management.key.pub", "cluster/live/dev/.terraform.lock.hcl", "nested/sealed-secret.yaml", "nested/gateway-sealed-secret.yaml", "nested/gateway-sealed-secrets.yaml", "scripts/config.py", "tests/test_config.py"]
        def ignored(paths):
            result = subprocess.run(["git", "check-ignore", "--no-index", "--stdin"], cwd=REPO, input="\n".join(paths) + "\n", text=True, capture_output=True)
            self.assertIn(result.returncode, (0, 1))
            return set(result.stdout.splitlines())
        self.assertEqual(ignored(hidden), set(hidden))
        self.assertEqual(ignored(visible), set())


if __name__ == "__main__":
    unittest.main()
