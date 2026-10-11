# Python SDK — CL-027–CL-029, CL-031–CL-032

Operator authorized a direct jump to Phase 4A with existing keys and
`THINKPIXEL_API_KEY`, deferring key assignment/CL-030. Gateway API is authoritative;
no server/plugin/schema/deployment changes. Gates 0–3 and live parity stay open.

In an isolated temporary virtual environment on CPython 3.13.5, with HTTPX 0.28.1,
pytest 8.4.2, Ruff 0.17.0, mypy 1.20.2, build 1.6.1 and bump2version 1.0.1:

- Editable install with `pip install --no-build-isolation --no-deps -e .` passed.
- `python -m pytest -q`: 80 tests passed against source-audited shared fixtures
  and synthetic HTTP adapters, including partial/all-failed store, auth expiry,
  exact request shapes, 401 replay, no retries after uncertain outcomes,
  malformed JSON/schema, redaction, URL safety, rate limits and shared budgets.
- `ruff check .`, `ruff format --check .`, `mypy src`: passed.
- `bump2version --allow-dirty minor` assigned 0.1.0 from initial 0.0.0 in
  pyproject/module/config; commit and tag creation disabled.
- `python -m build --no-isolation`: built sdist and wheel from sdist.

Python 3.11+ is the declared support target; only installed CPython 3.13 was
executed. Lowest-runtime execution remains unverified. HTTPX phase timeouts
cannot enforce hard wall-clock interruption during streaming/DNS; late responses
are rejected and no replay occurs after budget exhaustion. See the
[package guide](../../../clients/python/README.md) for that explicit limitation.

No live key, gateway requests, store/index/search smoke, registration, migration,
deployment, publishing or push occurred. Mock success is not live integration
or durable indexing evidence. Package name availability is unverified.

Repository checks: `make verify` passed (42 tests, one skipped; inherited baseline,
limited secret/path scan, links, syntax, HCL formatting and six Kustomize renders).
`make help` passed. `make doctor` returned expected exit 2 for unsupported installed
Terragrunt 0.81.0. `make config-check` returned expected exit 2 for missing dev
secret file, unsupported prod, and absent/invalid ENV. No real credentials used.

Installed-wheel smoke passed from a separate temporary target: import, 0.1.0
module version, `py.typed` and bundled Apache-2.0 license confirmed.
