"""Safety boundaries tested with private synthetic inputs and fake tool output."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import ops
import test_config


class OperatorTests(unittest.TestCase):
    def setUp(self):
        # Reuse fixture setup, without inheriting and repeating its test methods.
        test_config.ConfigurationTests.setUp(self)
        shutil.copyfile(REPO / "cluster/live/dev/.terraform.lock.hcl", self.dev / ".terraform.lock.hcl")
        self.directory = self.repo / "private-artifacts"
        self.directory.mkdir(mode=0o700)
        self.env = {"ENV": "dev", "OPERATOR_DIR": str(self.directory), "STATE_REVIEWED": "1"}
        self.calls = []
        self.before = {p: p.read_bytes() for p in self.repo.rglob("*") if p.is_file()}

    def write_secrets(self, extra="", **kwargs):
        test_config.ConfigurationTests.write_secrets(self, extra, **kwargs)

    def run_target(self, target, **values):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            ops.dispatch(target, self.repo, {**self.env, **values})
        return output.getvalue()

    def assert_blocked(self, target, message, **values):
        with self.assertRaisesRegex(ops.ConfigError, message):
            self.run_target(target, **values)

    def fake_operation(self, command, cwd, env, log):
        self.calls.append(command)
        with ops.create_private(log) as stream:
            stream.write(b"synthetic private log")
        for item in command:
            if item.startswith("-out="):
                with ops.create_private(Path(item[5:])) as stream:
                    stream.write(b"synthetic saved plan")

    def plan(self, **values):
        with patch.object(ops, "terraform_tools"), patch.object(ops, "capture", return_value=b'{"resource_changes": []}'), patch.object(ops, "run_private", side_effect=self.fake_operation):
            self.run_target("cluster-plan", **values)
        return hashlib.sha256((self.directory / "dev.tfplan").read_bytes()).hexdigest()

    def test_make_default_help_and_dry_listing_do_not_expose_values(self):
        canary = "sensitive-canary-must-not-appear"
        for args in ([], ["-n", *ops.TARGETS]):
            result = subprocess.run(["make", "--no-print-directory", *args, "SECRETS_FILE=" + canary], cwd=REPO, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            self.assertNotIn(canary, result.stdout + result.stderr)
            self.assertNotIn("-auto-approve", result.stdout)
        self.assertIn("help", result.stdout)

    def test_make_exports_data_without_shell_interpolation(self):
        file = self.repo / "marker"
        # Shell substitutions and backticks stay in an environment value. The
        # missing literal path is reported generically, and no shell is invoked.
        for value in (f"$(touch {file})", f"`touch {file}`", f"x; touch {file}"):
            result = subprocess.run(["make", "--no-print-directory", "config-check", "ENV=dev", "SECRETS_FILE=" + value], cwd=REPO, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(file.exists())
            self.assertNotIn(str(file).encode(), result.stdout + result.stderr)

    def test_config_check_dotenv_and_blank_override_preserve_precedence(self):
        (self.repo / ".env").write_text("ENV=dev\nSECRETS_FILE=absent\n")
        with contextlib.redirect_stdout(io.StringIO()):
            ops.dispatch("config-check", self.repo, {"SECRETS_FILE": ""})
        self.assert_blocked("config-check", "select dev or prod", ENV="")

    def test_all_previews_are_readonly_and_no_tools_launch(self):
        with patch.object(subprocess, "run", side_effect=AssertionError("must not launch tools")):
            for target in ("cluster-init", "cluster-plan", "cluster-up", "flux-check", "flux-bootstrap", "status"):
                out = self.run_target(target, DRY_RUN="1", KUBE_CONTEXT="fixture-dev")
                self.assertIn("DRY_RUN", out)
                self.assertNotIn(str(self.repo), out)
        after = {p: p.read_bytes() for p in self.repo.rglob("*") if p.is_file()}
        self.assertEqual(self.before, after)

    def test_missing_invalid_and_prod_env_never_fallback(self):
        for target in ("config-check", "cluster-init", "cluster-plan", "cluster-up", "cluster-scale", "flux-check", "flux-bootstrap", "status"):
            for env in ("", "bad", "prod"):
                with self.subTest(target=target, env=env):
                    self.assert_blocked(target, "ENV", ENV=env, DRY_RUN="1")

    def test_tool_override_bypasses_are_blocked_before_execution(self):
        for key in ("TG_CONFIG", "TERRAGRUNT_SOURCE", "TF_CLI_ARGS_apply", "TF_DATA_DIR", "TF_CLI_CONFIG_FILE", "TF_LOG", "TF_VAR_worker_pools", "TPSR_SECRETS_FILE"):
            with self.subTest(key=key), patch.object(subprocess, "run", side_effect=AssertionError("no subprocess")):
                self.assert_blocked("cluster-plan", "unset ambient", **{key: "unsafe"})
        (self.dev / "unsafe.auto.tfvars").write_text('worker_pools = {}')
        with patch.object(subprocess, "run", side_effect=AssertionError("no subprocess")):
            self.assert_blocked("cluster-plan", "unvalidated tfvars")

    def test_init_requires_state_review_and_never_plans_or_applies(self):
        with patch.object(ops, "terraform_tools"), patch.object(ops, "run_private", side_effect=self.fake_operation):
            self.assert_blocked("cluster-init", "STATE_REVIEWED", STATE_REVIEWED="0")
            self.run_target("cluster-init")
        self.assertEqual(self.calls[0], ops.tg(["init", "-input=false", "-lockfile=readonly"]))
        self.assertFalse((self.directory / "dev.tfplan").exists())

    def test_plan_matches_direct_command_and_never_applies(self):
        output = self.plan()
        command = self.calls[0]
        self.assertEqual(command, ops.tg(["plan", "-input=false", "-no-color", "-out=" + str(self.directory / "dev.tfplan")]))
        receipt = json.loads((self.directory / "dev.receipt.json").read_bytes())
        self.assertEqual(receipt["sha256"], output)
        self.assertNotIn("offline-cloud-fixture", json.dumps(receipt))
        self.assertEqual((self.directory / "plan.log").stat().st_mode & 0o777, 0o600)
        with patch.object(ops, "terraform_tools"):
            self.assert_blocked("cluster-plan", "fresh private directory")

    def test_apply_requires_exact_review_hash_confirmation_and_single_attempt(self):
        digest = self.plan()
        with patch.object(ops, "terraform_tools"), patch.object(ops, "run_private", side_effect=self.fake_operation):
            self.assert_blocked("cluster-up", "REVIEWED_SHA")
            self.assert_blocked("cluster-up", "CONFIRM", REVIEWED_SHA=digest)
            self.run_target("cluster-up", REVIEWED_SHA=digest, CONFIRM="apply-dev")
            self.assertEqual(self.calls[-1], ops.tg(["apply", "-input=false", "-no-color", str(self.directory / "dev.tfplan")]))
            with self.assertRaises(FileExistsError):
                self.run_target("cluster-up", REVIEWED_SHA=digest, CONFIRM="apply-dev")

    def test_apply_rejects_plan_tampering_changed_keys_input_and_workspace(self):
        digest = self.plan()
        with patch.object(ops, "terraform_tools"):
            self.assert_blocked("cluster-up", "stale or mismatched", TF_WORKSPACE="other", REVIEWED_SHA=digest, CONFIRM="apply-dev")
            key = self.dev / ".master.key"
            old = key.read_bytes()
            key.write_bytes(b"changed key")
            self.assert_blocked("cluster-up", "stale or mismatched", REVIEWED_SHA=digest, CONFIRM="apply-dev")
            key.write_bytes(old)
            (self.directory / "dev.tfplan").write_bytes(b"changed plan")
            self.assert_blocked("cluster-up", "stale or mismatched", REVIEWED_SHA=digest, CONFIRM="apply-dev")

    def test_private_storage_files_and_symlinks_fail_closed(self):
        self.directory.chmod(0o755)
        with patch.object(ops, "terraform_tools"):
            self.assert_blocked("cluster-plan", "mode 700")
        self.directory.chmod(0o700)
        symlink = self.directory / "linked"
        symlink.symlink_to(self.secrets)
        with self.assertRaisesRegex(ops.ConfigError, "no symlinks"):
            ops.private_bytes(symlink)
        with self.assertRaises(FileExistsError):
            ops.create_private(symlink)

    def test_scaling_only_persisted_existing_workers_and_reduction_ack(self):
        self.assert_blocked("cluster-scale", "POOL", POOL="master", COUNT="2", CURRENT_COUNT="1", DRY_RUN="1")
        self.assert_blocked("cluster-scale", "persist", POOL="api", COUNT="4", CURRENT_COUNT="3", DRY_RUN="1")
        self.write_secrets('worker_pools = { api = { count = 2 server_type = "cax21" } monitor = { count = 1 server_type = "cax21" } }')
        self.assert_blocked("cluster-scale", "REDUCTION_REVIEWED", POOL="api", COUNT="2", CURRENT_COUNT="3", DRY_RUN="1")
        out = self.run_target("cluster-scale", POOL="api", COUNT="2", CURRENT_COUNT="3", REDUCTION_REVIEWED="1", DRY_RUN="1")
        self.assertIn("downtime", out)
        self.assertIn("plan", out)
        for count in ("0", "-1", "1.2", "four"):
            self.assert_blocked("cluster-scale", "positive integer", POOL="api", COUNT=count, CURRENT_COUNT="3", DRY_RUN="1")
        self.write_secrets('master_pool = { count = 3 server_type = "cax21" }')
        self.assert_blocked("cluster-scale", "control-plane", POOL="api", COUNT="3", CURRENT_COUNT="2", DRY_RUN="1")

    def test_scaling_json_counts_control_plane_and_cross_pool_replacements(self):
        scale = {"pool": "api", "current": 1, "count": 2}
        plan = {"resource_changes": [
            {"address": "module.k8s.module.worker.hcloud_server.this[0]", "type": "hcloud_server", "change": {"actions": ["no-op"], "before": {"labels": {"pool": "api"}}, "after": {"labels": {"pool": "api"}}}},
            {"address": "module.k8s.module.worker.hcloud_server.this[1]", "type": "hcloud_server", "change": {"actions": ["delete", "create"], "before": {"labels": {"pool": "monitor"}}, "after": {"labels": {"pool": "api"}}}}]}
        self.assertTrue(ops.check_scale_plan(plan, scale))
        with self.assertRaisesRegex(ops.ConfigError, "counts"):
            ops.check_scale_plan(plan, {**scale, "current": 2})
        plan["resource_changes"].append({"address": "module.k8s.module.master.hcloud_server.this[0]", "change": {"actions": ["update"]}})
        with self.assertRaisesRegex(ops.ConfigError, "control-plane"):
            ops.check_scale_plan(plan, scale)

    def test_ordinary_plan_deletions_need_apply_acks_and_master_changes_blocked(self):
        changes = {"resource_changes": [{"address": "module.k8s.module.worker.hcloud_server.this[0]", "type": "hcloud_server", "change": {"actions": ["delete"], "before": {"labels": {"pool": "monitor"}}}}]}
        with patch.object(ops, "terraform_tools"), patch.object(ops, "capture", return_value=json.dumps(changes).encode()), patch.object(ops, "run_private", side_effect=self.fake_operation):
            self.run_target("cluster-plan")
            digest = hashlib.sha256((self.directory / "dev.tfplan").read_bytes()).hexdigest()
            self.assert_blocked("cluster-up", "worker deletions", REVIEWED_SHA=digest, CONFIRM="apply-dev")
            self.run_target("cluster-up", REVIEWED_SHA=digest, CONFIRM="apply-dev", REPLACEMENTS_REVIEWED="1", REDUCTION_REVIEWED="1")
        master = {"address": "module.k8s.module.master.hcloud_server.this[0]", "type": "hcloud_server", "change": {"actions": ["update"], "before": {"name": "fixture"}}}
        with self.assertRaisesRegex(ops.ConfigError, "control-plane"):
            ops.worker_deletions({"resource_changes": [master]})
        master["change"]["actions"] = ["no-op"]
        extra = {**master, "change": {"actions": ["create"]}}
        with self.assertRaisesRegex(ops.ConfigError, "adding control-plane"):
            ops.worker_deletions({"resource_changes": [master, extra]})

    def test_image_previews_match_workflow_without_latest_or_push_from_build(self):
        for image, context in ops.IMAGES.items():
            source = REPO / context
            destination = self.repo / context
            destination.mkdir(parents=True)
            for name in ("Dockerfile", ".bumpversion.cfg"):
                shutil.copyfile(source / name, destination / name)
            version = ops.configparser.ConfigParser()
            version.read(source / ".bumpversion.cfg")
            values = {"IMAGE": image, "REGISTRY": "quay.io/bdobrica", "TAG": version["bumpversion"]["current_version"], "DRY_RUN": "1"}
            with patch.object(subprocess, "run", side_effect=AssertionError("no subprocess")):
                output = self.run_target("images-build", **values)
                self.assertIn("linux/amd64,linux/arm64", output)
                self.assertIn(context + "/Dockerfile", output)
                self.assertNotIn("--push", output)
                output = self.run_target("images-push", **values)
                self.assertIn("--push", output)
                self.assertNotIn(":latest", output)
            self.assert_blocked("images-build", "TAG", **{**values, "TAG": "latest"})
            self.assert_blocked("images-build", "REGISTRY", **{**values, "REGISTRY": "other.invalid"})
            self.assert_blocked("images-push", "CONFIRM", **{**values, "DRY_RUN": "0"})

    def test_flux_requires_explicit_context_and_prepared_operator(self):
        self.assert_blocked("flux-check", "KUBE_CONTEXT")
        self.assert_blocked("flux-bootstrap", "GITOPS_REVIEWED", KUBE_CONTEXT="fixture-dev")
        with patch.object(ops, "tool"), patch.object(ops, "capture", side_effect=ops.ConfigError("missing operator")), patch.object(ops, "run_private", side_effect=AssertionError("must not attach")):
            self.assert_blocked("flux-bootstrap", "missing operator", KUBE_CONTEXT="fixture-dev", GITOPS_REVIEWED="1", CONFIRM="bootstrap-dev")

    def test_flux_check_only_metadata_and_no_apply(self):
        calls = []
        def fake(command, *args, **kwargs):
            calls.append(command)
            return b"fixture"
        with patch.object(ops, "tool"), patch.object(ops, "capture", side_effect=fake):
            self.run_target("flux-check", KUBE_CONTEXT="fixture-dev")
        self.assertFalse(any("apply" in x or "bootstrap" in x for x in calls))
        secret = next(x for x in calls if "secret" in x)
        self.assertEqual(secret[-2:], ["-o", "name"])
        self.assertTrue(all("fixture-dev" in x for x in calls if x[:1] == ["kubectl"] and "kustomize" not in x))

    def test_error_output_never_prints_exception_details_or_untrusted_target(self):
        canary = "sensitive-canary-must-not-appear"
        for exception in (OSError(canary), ValueError(canary), TypeError(canary), AttributeError(canary), subprocess.TimeoutExpired(canary, 1)):
            out = io.StringIO()
            with contextlib.redirect_stderr(out), patch.object(ops, "dispatch", side_effect=exception):
                self.assertEqual(ops.main(["cluster-plan"]), 2)
            self.assertNotIn(canary, out.getvalue())
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ops.main([canary]), 2)

    def test_live_health_is_explicitly_gated_no_redirects_and_asserts_database(self):
        self.assert_blocked("verify-live", "LIVE_REVIEWED")
        for url in ("http://example.invalid", "https://user:token@example.invalid", "https://example.invalid/path", "https://example.invalid?token=x"):
            self.assert_blocked("verify-live", "API_URL", LIVE_REVIEWED="1", API_URL=url)
        with patch.object(ops.urllib.request, "build_opener", side_effect=AssertionError("no request")):
            self.run_target("verify-live", LIVE_REVIEWED="1", API_URL="https://example.invalid", DRY_RUN="1")
        from unittest.mock import MagicMock
        opener = MagicMock()
        responses = []
        for data in ({"status": "ok"}, {"status": "ready", "checks": {"database": "healthy"}}):
            response = MagicMock()
            response.__enter__.return_value.status = 200
            response.__enter__.return_value.read.return_value = json.dumps(data).encode()
            responses.append(response)
        opener.open.side_effect = responses
        with patch.object(ops.urllib.request, "build_opener", return_value=opener):
            out = self.run_target("verify-live", LIVE_REVIEWED="1", API_URL="https://example.invalid")
        self.assertIn("WordPress remain unverified", out)
        self.assertEqual([x.args[0] for x in opener.open.call_args_list], ["https://example.invalid/ping", "https://example.invalid/ready"])
        self.assertIsNone(ops.NoRedirect().redirect_request(None, None, None, None, None, None))

    @unittest.skipUnless(shutil.which("terragrunt"), "optional real Terragrunt forwarding check")
    def test_real_terragrunt_forwards_wrapper_commands_to_offline_terraform_stub(self):
        # Keep older operator installations intact; doctor still rejects them
        # for real wrapper operations. This optional test needs the run flags.
        version = subprocess.run(["terragrunt", "--version"], capture_output=True,
                                 text=True, timeout=15)
        import re
        match = re.search(r"v?(\d+)\.(\d+)\.(\d+)", version.stdout)
        if version.returncode or not match or tuple(map(int, match.groups())) < (0, 96, 1):
            self.skipTest("real forwarding requires Terragrunt >= 0.96.1; operator tool unchanged")
        binaries = self.repo / "bin"
        binaries.mkdir()
        records = self.repo / "commands.jsonl"
        stub = binaries / "terraform"
        stub.write_text("#!/usr/bin/env python3\n" +
                        "import json,pathlib,sys\n" +
                        "args=sys.argv[1:]\n" +
                        "if args and args[0] in ('version','-version'):\n" +
                        " print(json.dumps({'terraform_version':'1.14.3'}) if '-json' in args else 'Terraform v1.14.3')\n" +
                        "else:\n" +
                        " with pathlib.Path(" + repr(str(records)) + ").open('a') as out: out.write(json.dumps(args)+'\\n')\n" +
                        " if args[0]=='plan':\n" +
                        "  path=pathlib.Path(next(x[5:] for x in args if x.startswith('-out='))); path.write_bytes(b'offline plan'); path.chmod(0o600)\n" +
                        " elif args[0]=='show': print(json.dumps({'resource_changes':[]}))\n" +
                        " elif args[0] not in ('init','apply'): sys.exit(99)\n")
        stub.chmod(0o700)
        self.env.update({"PATH": str(binaries) + os.pathsep + os.environ["PATH"],
                         "HOME": os.environ.get("HOME", "/tmp"), "LANG": "C.UTF-8"})
        # This is a fake backend/provider-free Terraform binary. All side effects
        # remain inside the synthetic fixture, never the operator checkout/cache.
        self.run_target("cluster-init")
        self.run_target("cluster-plan")
        digest = hashlib.sha256((self.directory / "dev.tfplan").read_bytes()).hexdigest()
        self.run_target("cluster-up", REVIEWED_SHA=digest, CONFIRM="apply-dev")
        commands = [json.loads(line) for line in records.read_text().splitlines()]
        self.assertEqual([x[0] for x in commands], ["init", "plan", "show", "apply"])
        self.assertIn("-lockfile=readonly", commands[0])
        self.assertIn("-out=" + str(self.directory / "dev.tfplan"), commands[1])
        self.assertEqual(commands[-1], ["apply", "-input=false", "-no-color", str(self.directory / "dev.tfplan")])
        self.assertFalse(list(self.repo.rglob("*.tfstate")))


if __name__ == "__main__":
    unittest.main()
