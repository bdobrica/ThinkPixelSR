"""Offline makeover gate: frozen inherited bytes and limited secret patterns.

Only Git's tracked plus nonignored candidate files are read, never operator
configuration or ignored credentials. No network, staging or generated output.
This is not an entropy scanner, credential validity check or historical audit.
"""
import hashlib
from pathlib import Path
import re
import subprocess
import sys

from config import ConfigError, FILES

BASELINE = "9e5fc87495832d3a2554965341cbeb43911ff5f5"
EDITABLE = {"README.md", "cluster/README.md", ".gitignore", "cluster/live/dev/terragrunt.hcl"}
ADDITIONS = {".env.example", "Makefile", "AGENTS.md", "PLAN.md", "TODO.md",
             "clients/README.md", "clients/PLAN.md", "clients/TODO.md",
             "clients/contracts/README.md",
             "clients/typescript/.gitignore", "clients/typescript/.bumpversion.cfg",
             "clients/typescript/package.json", "clients/typescript/package-lock.json",
             "clients/typescript/tsconfig.json", "clients/typescript/tsconfig.examples.json",
             "clients/typescript/README.md", "clients/typescript/CHANGELOG.md", "clients/typescript/LICENSE",
             "clients/python/.gitignore", "clients/python/.bumpversion.cfg",
             "clients/python/pyproject.toml", "clients/python/README.md",
             "clients/python/CHANGELOG.md", "clients/python/LICENSE", "clients/python/src/thinkpixel_sr/py.typed"}
PATTERNS = (
    rb"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----",
    rb"\bgh[pousr]_[A-Za-z0-9]{36,}\b",
    rb"\bgithub_pat_[A-Za-z0-9_]{60,}\b",
    rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b",
    rb"(?m)^S[UAONCX][A-Z2-7]{56}\s*$",
)


def git(repo, *args):
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, timeout=30)
    if result.returncode:
        raise ConfigError("audit: Git/frozen baseline unavailable; use a full history checkout")
    return result.stdout


def blob_id(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def normalized_hcl(data):
    text = data.decode("utf-8")
    text = text.replace("  # Optional local path overrides; unset variables retain the original contract.\n", "")
    for key, fallback in FILES.items():
        text = text.replace(f'get_env("TPSR_{key}", "{fallback}")', f'"{fallback}"')
    # Remove formatting whitespace, preserving every literal string byte.
    return re.sub(r'"(?:\\.|[^"\\])*"|\s+', lambda m: m[0] if m[0].startswith('"') else "", text)


def sensitive_path(name):
    path = Path(name)
    if name.endswith((".example", ".pub", ".terraform.lock.hcl")):
        return False
    return (path.name == ".env" or path.name.startswith(".env.")
            or "secrets.hcl" in path.name or path.name.startswith("id_")
            or path.suffix in {".key", ".pem", ".tfstate", ".tfplan", ".tfvars"}
            or "kubeconfig" in path.name or ".tfstate." in path.name
            or path.name.endswith(".tfvars.json")
            or any(p in {".ssh", ".kube", ".terraform", ".terragrunt-cache", "secrets.local"} for p in path.parts))


def secret_check(name, data):
    if sensitive_path(name) or any(re.search(pattern, data) for pattern in PATTERNS):
        # Never include matched values, arbitrary paths, lines or subprocess text.
        raise ConfigError("audit: potential sensitive candidate detected; review privately before publication")


def audit(repo):
    repo = Path(repo)
    baseline = {}
    for record in git(repo, "ls-tree", "-rz", BASELINE).split(b"\0"):
        if record:
            metadata, name = record.split(b"\t", 1)
            mode, kind, digest = metadata.decode().split()
            if kind != "blob" or mode not in {"100644", "100755"}:
                raise ConfigError("audit: unexpected baseline object type")
            baseline[name.decode()] = (mode, digest)
    index = {}
    for record in git(repo, "ls-files", "--stage", "-z").split(b"\0"):
        if record:
            metadata, name = record.split(b"\t", 1)
            mode, _, stage = metadata.decode().split()
            if stage != "0":
                raise ConfigError("audit: resolve index conflicts before validation")
            index[name.decode()] = mode
    rows = []
    for name, (mode, digest) in sorted(baseline.items()):
        path = repo / name
        if path.is_symlink() or not path.is_file() or index.get(name) != mode:
            raise ConfigError("audit: inherited path/type/index mode changed")
        data = path.read_bytes()
        same = blob_id(data) == digest
        if not same and name not in EDITABLE:
            raise ConfigError("audit: inherited runtime/source bytes differ from frozen baseline")
        if name == "cluster/live/dev/terragrunt.hcl":
            frozen = git(repo, "show", BASELINE + ":" + name)
            if normalized_hcl(data) != normalized_hcl(frozen):
                raise ConfigError("audit: dev HCL differs beyond reviewed path hooks/formatting")
        rows.append((name, "unchanged" if same else "reviewed-makeover", digest, blob_id(data)))
    candidates = set(index)
    candidates.update(p.decode() for p in git(repo, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0") if p)
    for name in sorted(candidates):
        contract_fixture = name.startswith("clients/contracts/fixtures/") and name.endswith(".json")
        python_sdk = name.endswith(".py") and name.startswith((
            "clients/python/src/thinkpixel_sr/", "clients/python/tests/", "clients/python/examples/"))
        typescript_sdk = (name.endswith(".ts") and name.startswith((
            "clients/typescript/src/", "clients/typescript/examples/"))) or (
            name.endswith(".test.mjs") and name.startswith("clients/typescript/tests/"))
        if name not in baseline and name not in ADDITIONS and not contract_fixture and not python_sdk and not typescript_sdk and not name.startswith(("docs/", "scripts/", "tests/")):
            raise ConfigError("audit: new candidate outside the reviewed makeover paths")
        path = repo / name
        if path.is_symlink() or not path.is_file():
            raise ConfigError("audit: candidate must be an existing regular file")
        secret_check(name, path.read_bytes())
    return {"rows": rows, "inherited": len(rows), "unchanged": sum(r[1] == "unchanged" for r in rows), "scanned": len(candidates)}


def main():
    try:
        result = audit(Path(__file__).resolve().parents[1])
        print(f"Frozen baseline: {result['inherited']} inherited files, {result['unchanged']} byte-identical; reviewed documentation/ignore/dev-path exceptions only.")
        print(f"Limited secret-pattern/path scan: {result['scanned']} tracked/nonignored candidate files passed; ignored files and history excluded.")
        return 0
    except (ConfigError, OSError, ValueError, UnicodeError, subprocess.SubprocessError):
        error = sys.exc_info()[1]
        print(str(error) if isinstance(error, ConfigError) else "audit: offline validation failed; details suppressed", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
