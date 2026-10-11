"""Read-only operator configuration and path translation for Make wrappers.

No shell evaluation, subprocesses, generated credentials or deployment actions.
The deliberately small literal-HCL reader validates input data without invoking
Terragrunt functions or hooks. Direct Terragrunt still supports full HCL.
"""

import argparse
import json
import os
from pathlib import Path
import re
import stat
import sys
from dataclasses import dataclass


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "SECRETS_FILE": ".secrets.hcl",
    "MASTER_PUBLIC_KEY_FILE": ".master.key.pub",
    "MASTER_PRIVATE_KEY_FILE": ".master.key",
    "WORKER_PUBLIC_KEY_FILE": ".worker.key.pub",
    "WORKER_PRIVATE_KEY_FILE": ".worker.key",
    "MANAGEMENT_PUBLIC_KEY_FILE": ".management.key.pub",
}
KEYS = {"ENV", *FILES}
LIMIT = 1024 * 1024


class ConfigError(ValueError):
    """Messages are fixed text: never include input values, paths or secrets."""


def read_text(path, label, private=False):
    try:
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= LIMIT:
            raise ConfigError(f"{label}: expected a nonempty regular file (at most 1 MiB)")
        if private and os.name == "posix" and info.st_mode & 0o077:
            raise ConfigError(f"{label}: remove group/other permissions; use private POSIX storage")
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise ConfigError(f"{label}: file is missing, unreadable or not UTF-8") from None


def parse_env(text):
    """Strict single-line KEY=value syntax, with literal quotes and comments."""
    values = {}
    if len(text.encode("utf-8")) > LIMIT:
        raise ConfigError(".env: file exceeds 1 MiB")
    for number, raw in enumerate(text.splitlines(), 1):
        error = f".env line {number}: expected a known KEY=value with a single-line literal value"
        if any(ord(c) < 32 for c in raw):
            raise ConfigError(error)
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Z][A-Z0-9_]*) *= *(.*)", line)
        if not match or match[1] not in KEYS or match[1] in values:
            raise ConfigError(error)
        key, value = match.groups()
        if value.startswith(("'", '"')):
            quote = value[0]
            end = value.find(quote, 1)
            if end < 0 or (value[end + 1:].strip() and not value[end + 1:].lstrip().startswith("#")):
                raise ConfigError(error)
            value = value[1:end]
        else:
            value = re.split(r" +#", value, maxsplit=1)[0].rstrip()
            if any(c.isspace() for c in value) or "'" in value or '"' in value:
                raise ConfigError(error)
        # No escape decoding, dollar/backtick expansion, or shell/Make evaluation.
        values[key] = value
    return values


class LiteralHCL:
    """Data-only subset: objects, lists, strings, integers, booleans and null.

    Comments and optional commas are accepted; functions, heredocs, expressions,
    interpolation, duplicate keys and blocks are rejected. No partial matching.
    """

    def __init__(self, text):
        self.text = text
        self.pos = 0

    def space(self):
        while True:
            match = re.match(r"(?:\s+|#[^\n]*|//[^\n]*|/\*[\s\S]*?\*/)", self.text[self.pos:])
            if not match:
                return
            self.pos += match.end()

    def take(self, token):
        self.space()
        if self.text.startswith(token, self.pos):
            self.pos += len(token)
            return True
        return False

    def require(self, token):
        if not self.take(token):
            raise ConfigError("HCL: expected literal input data; see docs/configuration.md")

    def name(self):
        self.space()
        match = re.match(r"[A-Za-z_][A-Za-z0-9_-]*", self.text[self.pos:])
        if not match:
            raise ConfigError("HCL: expected a literal attribute name")
        self.pos += match.end()
        return match[0]

    def value(self, depth=0):
        if depth > 20:
            raise ConfigError("HCL: literal nesting limit exceeded")
        self.space()
        if self.take("{"):
            result = {}
            while not self.take("}"):
                self.space()
                key = self.value(depth + 1) if self.text[self.pos:self.pos + 1] == '"' else self.name()
                if not isinstance(key, str) or key in result:
                    raise ConfigError("HCL: duplicate or invalid object key")
                self.require("=")
                result[key] = self.value(depth + 1)
                self.take(",")
            return result
        if self.take("["):
            result = []
            while not self.take("]"):
                result.append(self.value(depth + 1))
                if not self.take(","):
                    self.require("]")
                    break
            return result
        self.space()
        if self.text[self.pos:self.pos + 1] == '"':
            try:
                value, size = json.JSONDecoder().raw_decode(self.text[self.pos:])
            except ValueError:
                raise ConfigError("HCL: invalid literal string") from None
            if "${" in value or "%{" in value:
                raise ConfigError("HCL: expressions are unsupported by offline validation")
            self.pos += size
            return value
        match = re.match(r"(?:-?[0-9]+(?:\.[0-9]+)?|true|false|null)\b", self.text[self.pos:])
        if not match:
            raise ConfigError("HCL: expressions are unsupported by offline validation")
        self.pos += match.end()
        return json.loads(match[0])

    def end(self):
        self.space()
        if self.pos != len(self.text):
            raise ConfigError("HCL: unexpected data; only literal inputs are supported")


def secret_inputs(text):
    parser = LiteralHCL(text)
    parser.require("inputs")
    parser.require("=")
    values = parser.value()
    parser.end()
    if not isinstance(values, dict):
        raise ConfigError("secrets inputs: expected an object")
    for name in ("hcloud_token", "hetznerdns_token"):
        value = values.get(name)
        if (not isinstance(value, str) or not value.strip() or value != value.strip()
                or any(c.isspace() for c in value)
                or value.lower() in {"dummy", "changeme", "your-hetzner-api-token", "your-hetzner-dns-api-token"}):
            raise ConfigError(f"secrets inputs: {name} must be a nonempty, non-placeholder literal string")
    return values


def cluster_inputs(text):
    # The inherited merge is the authority. Only parse its literal base, and
    # insist on its existing precedence rather than silently guessing a new one.
    match = re.search(r"(?m)^inputs\s*=\s*merge\s*\(", text)
    if not match:
        raise ConfigError("Terragrunt: unsupported inputs layout")
    parser = LiteralHCL(text[match.end():])
    values = parser.value()
    parser.require(",")
    parser.require("local.secrets.inputs")
    parser.require(",")
    parser.require("local.ssh_keys")
    parser.require(")")
    parser.end()
    if not isinstance(values, dict):
        raise ConfigError("Terragrunt: expected literal base inputs")
    return values


def validate_pools(base, overrides):
    effective = {**base, **overrides}
    workers = effective.get("worker_pools")
    existing = base.get("worker_pools")
    if not isinstance(workers, dict) or not isinstance(existing, dict) or set(workers) != set(existing):
        raise ConfigError("worker_pools: retain exactly the configured worker pools; no new or control-plane pool")
    for pool in [effective.get("master_pool"), *workers.values()]:
        if not isinstance(pool, dict) or set(pool) != {"count", "server_type"}:
            raise ConfigError("node pools: expected count and server_type")
        if type(pool["count"]) is not int or pool["count"] < 1:
            raise ConfigError("node pools: count must be a positive integer")
        if not isinstance(pool["server_type"], str) or not pool["server_type"].strip():
            raise ConfigError("node pools: server_type must be a nonempty string")


@dataclass(repr=False)
class Configuration:
    environment: str
    root: Path
    files: dict

    def child_environment(self, parent=None):
        """Translate only paths to the dev HCL get_env consumers; never print."""
        result = dict(os.environ if parent is None else parent)
        if any(k.startswith(("TF_VAR_", "TPSR_")) for k in result):
            raise ConfigError("configuration: unset ambient TF_VAR_* and TPSR_* overrides before translation")
        for key in FILES:
            result["TPSR_" + key] = str(self.files[key])
        return result


def load_config(repo=ROOT, env_file=None, overrides=None, environ=None):
    repo = Path(repo).resolve()
    environ = os.environ if environ is None else environ
    overrides = {} if overrides is None else overrides
    if set(overrides) - KEYS:
        raise ConfigError("configuration: unknown override key; see docs/configuration.md")
    # Avoid an ambient TF_VAR bypass of the existing input merge and unvalidated
    # path hooks. Legacy direct Terragrunt remains available to operators.
    if any(k.startswith(("TF_VAR_", "TPSR_")) for k in environ):
        raise ConfigError("configuration: unset ambient TF_VAR_* and TPSR_* overrides before validation")
    path = repo / ".env" if env_file is None else Path(env_file)
    if not path.is_absolute():
        path = repo / path
    values = {}
    if env_file is not None or path.exists():
        values.update(parse_env(read_text(path, ".env")))
    values.update({key: environ[key] for key in KEYS if key in environ})
    values.update(overrides)
    selected = values.get("ENV", "")
    if selected not in ("dev", "prod"):
        raise ConfigError("ENV: select dev or prod explicitly; no default environment")
    root = repo / "cluster" / "live" / selected
    if selected == "prod":
        raise ConfigError("ENV=prod: production configuration is not implemented; no dev fallback")
    base = cluster_inputs(read_text(root / "terragrunt.hcl", "Terragrunt configuration"))
    files = {}
    for key, fallback in FILES.items():
        value = values.get(key, "")
        if not isinstance(value, str) or any(ord(c) < 32 for c in value):
            raise ConfigError("configuration: path values must be single-line strings")
        file = Path(value) if value else root / fallback
        if not file.is_absolute():
            file = repo / file
        # A symlink to private storage is allowed; validate its resolved target.
        files[key] = file.resolve()
        text = read_text(files[key], key, private=key == "SECRETS_FILE" or "PRIVATE" in key)
        if key == "SECRETS_FILE":
            inputs = secret_inputs(text)
            allowed = set(re.findall(r'variable "([a-z_]+)"', read_text(repo / "cluster/infra/variables.tf", "Terraform schema")))
            if set(inputs) - allowed:
                raise ConfigError("secrets inputs: unknown Terraform input")
            validate_pools(base, inputs)
        # Key contents and credentials are not retained or logged. Key pairing,
        # encryption and authentication are later operator/live prerequisites.
    return Configuration(selected, root, files)


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "configuration: invalid command arguments; use --help\n")


def main(argv=None):
    parser = SafeParser(description="Validate ThinkPixelSR configuration offline; no deployment or generated files.")
    parser.add_argument("--env", help="explicit dev or prod selection")
    parser.add_argument("--env-file", help="explicit .env data file (relative to repository root)")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help="override a documented non-secret key")
    args = parser.parse_args(argv)
    try:
        overrides = {}
        for item in args.set:
            key, separator, value = item.partition("=")
            if not separator or key not in KEYS or key in overrides:
                raise ConfigError("configuration: invalid or duplicate --set key")
            overrides[key] = value
        if args.env is not None:
            overrides["ENV"] = args.env
        config = load_config(env_file=args.env_file, overrides=overrides)
        print(f"Configuration OK: ENV={config.environment}; local input files validated (no live checks).")
        return 0
    except (ConfigError, OSError, ValueError, RuntimeError):
        # Only ConfigError carries a safe message. Other exception strings can
        # contain private paths, file data or user values.
        error = sys.exc_info()[1]
        message = str(error) if isinstance(error, ConfigError) else "configuration: invalid local input data"
        print(message, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
