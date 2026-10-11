"""Thin, guarded operator interface. All external commands use argument arrays.

Raw tool output can contain SSH keys, state, cluster addresses or credentials.
Keep it in operator-owned private storage, or capture it without printing it.
"""
import configparser
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

from config import (ROOT, FILES, KEYS, ConfigError, load_config, parse_env,
                    read_text, cluster_inputs, secret_inputs)

TARGETS = ("help", "doctor", "config-check", "cluster-init", "cluster-plan",
           "cluster-up", "cluster-scale", "flux-check", "flux-bootstrap",
           "images-build", "images-push", "status", "verify", "verify-live")
IMAGES = {name: "docker/models/" + name for name in
          ("mpnetv2", "snowflake-arctic", "e5-instruct", "jina-v5", "external")}
IMAGES["api-gateway"] = "docker/api_gateway"


def require(condition, message):
    if not condition:
        raise ConfigError(message)


def flag(env, key):
    value = env.get(key, "")
    require(value in ("", "0", "1"), key + ": expected 0 or 1")
    return value == "1"


def selected_env(repo, env):
    values = parse_env(read_text(repo / ".env", ".env")) if (repo / ".env").exists() else {}
    value = env.get("ENV", values.get("ENV", ""))
    require(value in ("dev", "prod"), "ENV: select dev or prod explicitly")
    require(value == "dev", "ENV=prod: production configuration is not implemented; no dev fallback")
    return value


def clean_config_env(env):
    return dict(env)


def tool(name):
    require(shutil.which(name) is not None, name + ": required tool is missing; run make doctor")
    return name


def capture(command, cwd, env, timeout=60):
    result = subprocess.run(command, cwd=cwd, env={**env, "CHECKPOINT_DISABLE": "1"}, capture_output=True, timeout=timeout)
    require(result.returncode == 0, "tool check failed (raw diagnostics suppressed); consult the operator guide")
    return result.stdout


def private_dir(env):
    value = env.get("OPERATOR_DIR", "")
    require(bool(value) and not any(ord(c) < 32 for c in value), "OPERATOR_DIR: set an existing private absolute directory outside the checkout")
    path = Path(value)
    require(path.is_absolute(), "OPERATOR_DIR: absolute path required")
    path = path.resolve()
    require(path != ROOT and ROOT not in path.parents, "OPERATOR_DIR: keep generated sensitive output outside the checkout")
    info = path.stat()
    require(stat.S_ISDIR(info.st_mode), "OPERATOR_DIR: expected a directory")
    if os.name == "posix":
        require(not info.st_mode & 0o077 and info.st_uid == os.getuid(), "OPERATOR_DIR: directory must be owned by you with mode 700")
    return path


def create_private(path):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    return os.fdopen(descriptor, "wb")


def private_bytes(path):
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode), "artifact: expected a regular file, no symlinks")
    if os.name == "posix":
        require(not info.st_mode & 0o077 and info.st_uid == os.getuid(), "artifact: expected private owner-only permissions")
    return path.read_bytes()


def run_private(command, cwd, env, path):
    with create_private(path) as log:
        result = subprocess.run(command, cwd=cwd, env=env, stdout=log, stderr=log)
    require(result.returncode == 0, "operation failed; inspect the private operation log, repair, then create a fresh plan/run directory")


def preview(command, cwd, label):
    # Only validated choices/static arguments are visible; all operator paths redacted.
    shown = [str(x) if not Path(str(x).split("=", 1)[-1]).is_absolute() else "<private-path>" for x in command]
    if "--context" in shown:
        shown[shown.index("--context") + 1] = "<reviewed-context>"
    print(label)
    print("  cwd: " + cwd)
    print("  " + shlex.join(shown))


def tg(command):
    return ["terragrunt", "run", "--no-auto-init", "--no-auto-retry",
            "--non-interactive", "--tf-path", "terraform", "--log-disable",
            "--tf-forward-stdout", "--", *command]


def guarded_terraform_env(env):
    require(not any(k.startswith(("TG_", "TERRAGRUNT_", "TF_CLI_ARGS", "TF_LOG")) or
                    k in {"TF_DATA_DIR", "TF_CLI_CONFIG_FILE"}
                    for k in env),
            "infrastructure: unset ambient tool argument/config/log overrides before using wrappers")


def check_extra_inputs(repo, config):
    for root in (repo / "cluster/infra", config.root):
        require(not any(root.rglob("*.tfvars")) and not any(root.rglob("*.tfvars.json")),
                "infrastructure: unvalidated tfvars files found in source/root/cache; review them separately before using wrappers")


def worker_deletions(plan):
    changes = plan.get("resource_changes", [])
    # Quorum changes are outside this makeover. Initial master creation is part
    # of the inherited deployment, but changing existing masters needs review.
    for item in changes:
        if ".master." in item["address"]:
            require(item["change"]["actions"] in (["no-op"], ["create"]),
                    "plan: existing control-plane changes require a separately reviewed decision")
    masters = [item for item in changes if ".master." in item["address"] and item.get("type") == "hcloud_server"]
    require(not (any(item["change"].get("before") for item in masters)
                 and any(item["change"]["actions"] == ["create"] for item in masters)),
            "plan: adding control-plane nodes to an existing cluster requires a separately reviewed decision")
    return any(".worker." in item["address"] and item.get("type") == "hcloud_server"
               and "delete" in item["change"]["actions"] for item in changes)


def terraform_tools(env, root):
    tool("terraform")
    tool("terragrunt")
    version = json.loads(capture(["terraform", "version", "-json"], root, env))["terraform_version"]
    require(tuple(map(int, version.split(".")[:2])) >= (1, 10), "Terraform >= 1.10 is required")
    output = capture(["terragrunt", "--version"], root, env).decode()
    match = re.search(r"v(\d+)\.(\d+)\.(\d+)", output)
    require(match is not None and tuple(map(int, match.groups())) >= (0, 96, 1),
            "Terragrunt >= 0.96.1 is required for the inspected run flags")


def fingerprint(repo, config, env):
    digest = hashlib.sha256()
    paths = sorted({*repo.glob("cluster/infra/**/*.tf"), *repo.glob("cluster/infra/**/.terraform.lock.hcl"),
                    config.root / "terragrunt.hcl", config.root / ".terraform.lock.hcl", *config.files.values()})
    for path in paths:
        digest.update(str(path.resolve()).encode())
        digest.update(path.read_bytes())
    digest.update(env.get("TF_WORKSPACE", "default").encode())
    return digest.hexdigest()


def effective_inputs(config):
    base = cluster_inputs(read_text(config.root / "terragrunt.hcl", "Terragrunt"))
    overrides = secret_inputs(read_text(config.files["SECRETS_FILE"], "SECRETS_FILE", private=True))
    return base, {**base, **overrides}


def scaling(config, env):
    base, effective = effective_inputs(config)
    pool = env.get("POOL", "")
    require(pool in base["worker_pools"], "POOL: select an existing worker pool (api or monitor); control-plane changes are blocked")
    counts = []
    for key in ("COUNT", "CURRENT_COUNT"):
        value = env.get(key, "")
        require(re.fullmatch(r"[1-9][0-9]{0,5}", value) is not None, key + ": set a positive integer (CURRENT_COUNT must come from reviewed state)")
        counts.append(int(value))
    count, current = counts
    require(effective["worker_pools"][pool]["count"] == count,
            "COUNT: persist this value in the existing worker_pools input before planning; wrapper never edits configuration")
    require(effective["master_pool"] == base["master_pool"], "scaling: control-plane overrides are blocked")
    require(count != current, "scaling: requested and current counts are equal")
    reduction = count < current
    print("Worker scaling plan: ENV=dev, POOL=" + pool + ", COUNT=" + str(current) + " -> " + str(count))
    print("Count-based indices can replace workers in other pools. Review workloads, PV/data placement, PDBs and draining; downtime is possible.")
    if reduction:
        require(flag(env, "REDUCTION_REVIEWED"), "scaling: reduction requires REDUCTION_REVIEWED=1 after workload/storage/PDB/drain review")
    return {"pool": pool, "count": count, "current": current, "reduction": reduction}


def check_scale_plan(plan, scale):
    before_count = after_count = 0
    replacements = False
    for item in plan.get("resource_changes", []):
        address = item["address"]
        change = item["change"]
        actions = change["actions"]
        if ".master." in address:
            require(actions == ["no-op"], "scaling: plan changes control-plane resources; stop for separate review")
        if ".worker." in address and item.get("type") == "hcloud_server":
            before, after = change.get("before") or {}, change.get("after") or {}
            before_count += int(before.get("labels", {}).get("pool") == scale["pool"])
            after_count += int(after.get("labels", {}).get("pool") == scale["pool"])
            replacements |= "delete" in actions
    require(before_count == scale["current"] and after_count == scale["count"],
            "scaling: plan counts do not match reviewed CURRENT_COUNT and requested COUNT")
    return replacements


def infrastructure(target, repo, env):
    guarded_terraform_env(env)
    config = load_config(repo=repo, environ=clean_config_env(env))
    check_extra_inputs(repo, config)
    child = config.child_environment(clean_config_env(env))
    child["TF_IN_AUTOMATION"] = "1"
    scale = scaling(config, env) if target == "cluster-scale" else None
    dry = flag(env, "DRY_RUN")
    if target == "cluster-init":
        command = tg(["init", "-input=false", "-lockfile=readonly"])
    elif target in ("cluster-plan", "cluster-scale"):
        command = tg(["plan", "-input=false", "-no-color", "-out=<private-plan>"])
    else:
        command = tg(["apply", "-input=false", "-no-color", "<reviewed-private-plan>"])
    preview(command, "cluster/live/" + config.environment,
            "Target ENV=" + config.environment + ": " + ("apply changes cloud resources" if target == "cluster-up" else "init/plan may access providers, lock/read state and write local metadata; no apply"))
    if dry:
        print("DRY_RUN: command preview only; no tool execution or artifacts, no live validation.")
        return
    require(flag(env, "STATE_REVIEWED"), "STATE_REVIEWED=1 required: locate authoritative backend/cache/workspace and preserve recovery state first")
    directory = private_dir(env)
    plan_path = directory / "dev.tfplan"
    receipt_path = directory / "dev.receipt.json"
    terraform_tools(child, config.root)
    if target == "cluster-init":
        run_private(command, config.root, child, directory / "init.log")
        print("Init completed; inspect private init.log. No plan or apply ran.")
        return
    if target in ("cluster-plan", "cluster-scale"):
        require(not plan_path.exists() and not receipt_path.exists(), "plan: use a fresh private directory; existing artifacts are never overwritten")
        signature = fingerprint(repo, config, env)
        command[-1] = "-out=" + str(plan_path)
        run_private(command, config.root, child, directory / "plan.log")
        # Terraform writes the plan itself; umask 077 is set by main.
        plan_hash = hashlib.sha256(private_bytes(plan_path)).hexdigest()
        plan_json = json.loads(capture(tg(["show", "-json", str(plan_path)]), config.root, child))
        replacements = worker_deletions(plan_json)
        if scale:
            replacements |= check_scale_plan(plan_json, scale)
        require(signature == fingerprint(repo, config, env), "plan: inputs changed during planning; create a fresh plan")
        receipt = {"environment": config.environment, "root": str(config.root), "sha256": plan_hash,
                   "inputs": signature, "scale": scale, "replacements": replacements}
        with create_private(receipt_path) as stream:
            stream.write(json.dumps(receipt).encode())
        print("Plan saved privately as dev.tfplan; inspect plan.log in a private viewer.")
        print("Review this exact plan before apply. SHA256=" + plan_hash)
        if replacements:
            print("Worker deletions/replacements detected: apply also requires REPLACEMENTS_REVIEWED=1 and REDUCTION_REVIEWED=1.")
        return
    receipt = json.loads(private_bytes(receipt_path))
    digest = hashlib.sha256(private_bytes(plan_path)).hexdigest()
    require(receipt["environment"] == config.environment and receipt["root"] == str(config.root)
            and receipt["inputs"] == fingerprint(repo, config, env) and receipt["sha256"] == digest,
            "apply: stale or mismatched plan/inputs/environment; create and review a fresh plan")
    require(env.get("REVIEWED_SHA") == digest, "apply: REVIEWED_SHA must match the exact inspected saved plan")
    require(env.get("CONFIRM") == "apply-" + config.environment, "apply: explicit CONFIRM=apply-dev required; saved-plan apply has no Terraform prompt")
    if (receipt.get("scale") or {}).get("reduction"):
        require(flag(env, "REDUCTION_REVIEWED"), "apply: renewed REDUCTION_REVIEWED=1 required")
    if receipt.get("replacements"):
        require(flag(env, "REPLACEMENTS_REVIEWED") and flag(env, "REDUCTION_REVIEWED"),
                "apply: worker deletions require REPLACEMENTS_REVIEWED=1 and REDUCTION_REVIEWED=1")
    # Single attempt, including partial failures. A retry requires a fresh plan.
    with create_private(directory / "apply.attempted") as stream:
        stream.write(b"Re-plan before any further apply attempt.\n")
    command[-1] = str(plan_path)
    run_private(command, config.root, child, directory / "apply.log")
    print("Saved plan applied; inspect private apply.log and perform explicit live health checks.")


def kube_command(context, *args):
    return ["kubectl", "--context", context, "--request-timeout=30s", *args]


def context_value(env):
    value = env.get("KUBE_CONTEXT", "")
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,199}", value) is not None,
            "KUBE_CONTEXT: explicitly name the reviewed cluster context")
    return value


def flux_prerequisites(repo, env, context):
    # Read only metadata/status; never request Secret contents.
    checks = [("get", "namespace", "flux-system", "-o", "name"),
              ("get", "crd", "fluxinstances.fluxcd.controlplane.io", "resourcesets.fluxcd.controlplane.io", "sealedsecrets.bitnami.com", "-o", "name"),
              ("wait", "--for=condition=Available", "deployment/flux-operator", "-n", "flux-system", "--timeout=30s"),
              ("get", "secret", "github-token", "-n", "flux-system", "-o", "name")]
    for check in checks:
        capture(kube_command(context, *check), repo, env)
    capture(["kubectl", "kustomize", "k8s/flux-system/dev"], repo, env)


def gitops(target, repo, env):
    selected_env(repo, env)
    context = context_value(env)
    if target == "flux-bootstrap":
        preview(kube_command(context, "apply", "-k", "k8s/flux-system/dev"), ".",
                "ENV=dev: attach checked-in operator-managed Flux declarations; reconciliation can change workloads. Source remains ThinkPixelInfra.")
    else:
        print("ENV=dev: read-only cluster/Flux checks using the explicitly selected context; resource contents suppressed.")
    if flag(env, "DRY_RUN"):
        print("DRY_RUN: no cluster requests, installation or runtime validation.")
        return
    tool("kubectl")
    if target == "flux-bootstrap":
        require(flag(env, "GITOPS_REVIEWED") and env.get("CONFIRM") == "bootstrap-dev",
                "Flux attach: GITOPS_REVIEWED=1 and CONFIRM=bootstrap-dev required after ownership/source/decryption-key review")
        directory = private_dir(env)
        flux_prerequisites(repo, env, context)
        # Dry-run invokes admission/validation only, then attach the exact overlay.
        capture(kube_command(context, "apply", "--dry-run=server", "-k", "k8s/flux-system/dev"), repo, env)
        run_private(kube_command(context, "apply", "-k", "k8s/flux-system/dev"), repo, env, directory / "flux-attach.log")
        print("Manifests attached; run flux-check/status. Reconciliation success remains a separate live check.")
    elif target == "flux-check":
        flux_prerequisites(repo, env, context)
        capture(kube_command(context, "wait", "--for=condition=Ready", "fluxinstance/flux", "-n", "flux-system", "--timeout=30s"), repo, env)
        for kind in ("gitrepository/flux-system", "kustomization/flux-system"):
            capture(kube_command(context, "wait", "--for=condition=Ready", kind, "-n", "flux-system", "--timeout=30s"), repo, env)
        print("Operator prerequisites and root Flux readiness passed; application health is not covered.")
    else:
        for namespace, kind in (("flux-system", "fluxinstances.fluxcd.controlplane.io"),
                                ("flux-system", "gitrepositories.source.toolkit.fluxcd.io"),
                                ("flux-system", "kustomizations.kustomize.toolkit.fluxcd.io"),
                                ("thinkpixel", "pods"), ("nats", "pods"), ("monitoring", "pods")):
            data = json.loads(capture(kube_command(context, "get", kind, "-n", namespace, "-o", "json"), repo, env))
            items = data.get("items", [])
            ready = sum(any(c.get("type") == "Ready" and c.get("status") == "True" for c in x.get("status", {}).get("conditions", [])) for x in items)
            print(namespace + " " + kind + ": " + str(ready) + "/" + str(len(items)) + " Ready")
        print("Status is diagnostic only; it does not certify API, ingestion, storage or plugin behavior.")


def images(target, repo, env):
    image, registry, tag = (env.get(k, "") for k in ("IMAGE", "REGISTRY", "TAG"))
    require(image in IMAGES, "IMAGE: select api-gateway, mpnetv2, snowflake-arctic, e5-instruct, jina-v5 or external")
    require(registry == "quay.io/bdobrica", "REGISTRY: explicitly use the checked-in namespace quay.io/bdobrica")
    version = configparser.ConfigParser()
    version.read(repo / IMAGES[image] / ".bumpversion.cfg")
    require(tag == version["bumpversion"]["current_version"] and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", tag) is not None,
            "TAG: explicitly use the checked-in current_version; latest and version drift are blocked")
    context = IMAGES[image]
    require((repo / context / "Dockerfile").is_file(), "image: checked-in Dockerfile is missing")
    command = ["docker", "buildx", "build", "--platform", "linux/amd64,linux/arm64",
               "--build-arg", "TARGETPLATFORM", "--file", context + "/Dockerfile",
               "--tag", registry + "/thinkpixel-" + image + "-multi:" + tag,
               context]
    command += ["--push"] if target == "images-push" else ["--output", "type=oci,dest=<private-archive>"]
    preview(command, ".", "Image target " + image + ": downloads/builds on both architectures; " + ("publishes versioned registry artifacts (may replace an existing version tag)" if target == "images-push" else "writes a local OCI archive, no registry push"))
    if flag(env, "DRY_RUN"):
        print("DRY_RUN: no Docker/registry access or artifacts; image build/pull success is unverified.")
        return
    if target == "images-push":
        require(env.get("CONFIRM") == "push", "images-push: explicit CONFIRM=push required; authenticate with docker login quay.io separately")
    directory = private_dir(env)
    tool("docker")
    capture(["docker", "buildx", "version"], repo, env)
    capture(["docker", "buildx", "inspect"], repo, env)
    if target == "images-build":
        archive = directory / (image + ".oci.tar")
        require(not archive.exists(), "image: use a fresh private directory; never overwrite an existing archive")
        # CSV encoding is Docker's output syntax, not a shell string.
        require(not any(c in str(directory) for c in ',"'), "OPERATOR_DIR: image export directory cannot contain CSV separators/quotes")
        command[-1] = "type=oci,dest=" + str(archive)
    run_private(command, repo, env, directory / (target + ".log"))
    print("Image operation completed; inspect private log. Manifests and pull references were not changed.")


def help_text():
    print("ThinkPixelSR operator commands (default: help)")
    for line in (ROOT / "Makefile").read_text().splitlines():
        if ": ## " in line:
            name, description = line.split(": ## ", 1)
            print("  " + name.ljust(18) + description)
    print("Examples: make config-check ENV=dev; make cluster-plan ENV=dev DRY_RUN=1")
    print("  make images-build IMAGE=mpnetv2 REGISTRY=quay.io/bdobrica TAG=0.3.5 DRY_RUN=1")
    print("See docs/operations/commands.md for state, approval and private artifact requirements.")
    print("Prod and fresh Flux operator installation are unsupported. Live workflow acceptance is pending.")


def doctor(repo, env):
    env = {k: v for k, v in env.items() if not k.startswith(("TF_", "TG_", "TERRAGRUNT_"))}
    missing = False
    for name, args, pattern in (
        ("make", ["--version"], r"GNU Make ([0-9.]+)"),
        ("python3", ["--version"], r"Python ([0-9.]+)"),
        ("terraform", ["version"], r"Terraform v([0-9.]+)"),
        ("terragrunt", ["--version"], r"version v([0-9.]+)"),
        ("kubectl", ["version", "--client", "-o", "json"], r'"gitVersion":\s*"v([0-9.]+)"'),
        ("docker", ["buildx", "version"], r"v([0-9.]+)")):
        if not shutil.which(name):
            print(name + ": MISSING")
            missing = True
            continue
        try:
            raw = capture([name, *args], repo, env, timeout=10).decode()
            match = re.search(pattern, raw)
            require(match is not None, "version unavailable")
            version = match[1]
            supported = (name != "terraform" or tuple(map(int, version.split(".")[:2])) >= (1, 10)) and (name != "terragrunt" or tuple(map(int, version.split("."))) >= (0, 96, 1))
            print(name + ": " + version + ("" if supported else " UNSUPPORTED"))
            missing |= not supported
        except (ConfigError, subprocess.TimeoutExpired):
            print(name + ": version check FAILED (diagnostics suppressed)")
            missing = True
    print("No credentials or services checked. Review state/workspace, cloud/DNS access, matching SSH keys, explicit kube context, Flux operator/decryption prerequisites and Quay login before live commands.")
    require(not missing, "doctor: install the missing/supported local tools; no packages were installed")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def live_health(repo, env):
    selected_env(repo, env)
    require(flag(env, "LIVE_REVIEWED"), "verify-live: LIVE_REVIEWED=1 required after approving the dev endpoint")
    url = env.get("API_URL", "")
    require(not any(ord(c) < 33 for c in url), "API_URL: expected an explicit HTTPS dev gateway URL")
    parsed = urllib.parse.urlsplit(url)
    require(parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password
            and not parsed.query and not parsed.fragment and parsed.path in ("", "/"),
            "API_URL: expected HTTPS origin only; no credentials, query, fragment or path")
    print("ENV=dev: GET /ping and /ready at the explicitly reviewed endpoint; no auth, ingestion or plugin requests.")
    if flag(env, "DRY_RUN"):
        print("DRY_RUN: no HTTP requests or live validation.")
        return
    opener = urllib.request.build_opener(NoRedirect())
    try:
        for endpoint, expected in (("ping", "ok"), ("ready", "ready")):
            with opener.open(url.rstrip("/") + "/" + endpoint, timeout=30) as response:
                data = response.read(65537)
                require(response.status == 200 and len(data) <= 65536, "verify-live: health response failed status/size checks")
            value = json.loads(data)
            require(value.get("status") == expected, "verify-live: health status assertion failed")
            if endpoint == "ready":
                require(value.get("checks", {}).get("database") == "healthy", "verify-live: database readiness assertion failed")
            print("/" + endpoint + ": passed")
    except (urllib.error.URLError, OSError, ValueError, AttributeError):
        raise ConfigError("verify-live: request/TLS/JSON check failed (endpoint and raw diagnostics suppressed)") from None
    print("Gateway liveness/database readiness passed; NATS, embeddings, retrieval and WordPress remain unverified.")


def dispatch(target, repo, env):
    if target == "help":
        help_text()
    elif target == "doctor":
        doctor(repo, env)
    elif target == "config-check":
        config = load_config(repo=repo, environ=clean_config_env(env))
        print("Configuration OK: ENV=" + config.environment + "; local input files validated (no live checks).")
    elif target == "verify-live":
        live_health(repo, env)
    elif target.startswith("cluster-"):
        infrastructure(target, repo, env)
    elif target.startswith("flux-") or target == "status":
        gitops(target, repo, env)
    elif target.startswith("images-"):
        images(target, repo, env)
    else:
        from verify import verify
        verify(repo, env)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        require(len(argv) == 1 and argv[0] in TARGETS, "operator: select a documented Make target; run make help")
        # Applies to logs, Terraform plans, caches and exported image artifacts.
        os.umask(0o077)
        dispatch(argv[0], ROOT, dict(os.environ))
        return 0
    except (ConfigError, OSError, ValueError, KeyError, RuntimeError, TypeError, AttributeError, IndexError, SyntaxError, subprocess.SubprocessError):
        error = sys.exc_info()[1]
        print(str(error) if isinstance(error, ConfigError) else "operator: invalid/unavailable input or tool result (details suppressed); consult the operator guide", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("operator: interrupted; inspect private logs/state before preparing a fresh plan", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
