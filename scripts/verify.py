"""Offline checks only: no provider init, cluster access, daemon or API smoke."""
import ast
import re
import shutil
import subprocess
from urllib.parse import unquote

from config import ConfigError


def documentation_links(repo):
    count = 0
    for path in [*(repo.glob("*.md")), *(repo / "docs").rglob("*.md"), *(repo / "clients").rglob("*.md")]:
        content = re.sub(r"```[\s\S]*?```", "", path.read_text())
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", content):
            target = target.strip("<>").split(" \"", 1)[0]
            if re.match(r"[a-z]+:", target):
                continue
            relative, _, fragment = unquote(target).partition("#")
            destination = (path.parent / relative).resolve() if relative else path
            if not destination.exists():
                raise ConfigError("verify: broken relative documentation link")
            if fragment and destination.suffix == ".md":
                headings = re.findall(r"(?m)^#+\s+(.+)$", destination.read_text())
                anchors = [re.sub(r"[^\w\- ]", "", h.lower().replace("`", "")).replace(" ", "-") for h in headings]
                if fragment not in anchors:
                    raise ConfigError("verify: broken documentation heading link")
            count += 1
    return count


def verify(repo, env):
    from ops import TARGETS, capture, require
    env = {k: v for k, v in env.items() if not k.startswith(("TF_", "TG_", "TERRAGRUNT_"))}
    print("Offline verification: no live init/plan/apply, cluster, Docker daemon or API requests. Tool-forwarding tests use a synthetic Terraform stub.")
    for path in [*(repo / "scripts").glob("*.py"), *(repo / "tests").glob("test_*.py")]:
        ast.parse(path.read_text())
    print("Python syntax: passed")
    # Test subprocesses use synthetic inputs. Version/render helpers never init.
    result = subprocess.run(["python3", "-B", "-m", "unittest", "discover", "-s", "tests", "-v"],
                            cwd=repo, env=env, capture_output=True, timeout=120)
    require(result.returncode == 0, "verify: offline tests failed (raw assertion details suppressed); run unittest with synthetic fixtures for diagnostics")
    summary = re.search(rb"Ran (\d+) tests", result.stderr)
    skipped = re.search(rb"skipped=(\d+)", result.stderr)
    print("Offline tests: " + (summary[1].decode() if summary else "suite") + " run, passed" + ("; " + skipped[1].decode() + " skipped" if skipped else ""))
    from audit import audit
    baseline = audit(repo)
    print(f"Frozen baseline: {baseline['unchanged']}/{baseline['inherited']} inherited files byte-identical; reviewed docs/ignore/dev-path exceptions only")
    print(f"Limited secret-pattern/path scan: {baseline['scanned']} tracked/nonignored candidate files passed (no history/ignored credentials scanned)")
    print("Documentation links: " + str(documentation_links(repo)) + " passed")
    capture(["make", "--no-print-directory", "-n", *TARGETS], repo, env)
    print("Make recipe parsing: passed")
    checks = [
        ("bash", [["bash", "-n", str(p)] for p in [*(repo / "docker").rglob("*.sh"), *(repo / "local").rglob("*.sh"), *(repo / "database").glob("*.sh")]], "Shell syntax"),
        ("terraform", [["terraform", "-chdir=cluster", "fmt", "-check", "-recursive"]], "Terraform formatting"),
        ("terragrunt", [["terragrunt", "hcl", "fmt", "--check", "--file", "cluster/live/dev/terragrunt.hcl"]], "Edited dev HCL formatting"),
        ("kubectl", [["kubectl", "kustomize", "k8s/flux-system/dev"], *[["kubectl", "kustomize", "k8s/apps/" + name + "/dev"] for name in ("monitoring", "thinkpixel")], *[["kubectl", "kustomize", "k8s/apps/" + name + "/dev", "--load-restrictor=LoadRestrictionsNone"] for name in ("cert-manager", "reflector", "nats")]], "Six dev YAML/Kustomize roots (three inherited cross-directory overlays use LoadRestrictionsNone; not proof of live Flux behavior)"),
    ]
    for binary, commands, label in checks:
        if not shutil.which(binary):
            print(label + ": SKIPPED (" + binary + " missing)")
            continue
        for command in commands:
            capture(command, repo, env)
        print(label + ": passed")
    print("Live smoke: SKIPPED; follow docs/operations/verification.md with explicit operator authorization and disposable fixtures.")
    print("Offline checks complete; tool skips and pending live acceptance remain limitations.")
