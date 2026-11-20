# Design note: one framework, three API styles

## Core and adapters

The core is intentionally small: a `Result` value (`status`, `data`, `errors`), an
`Adapter` protocol with a single `call(operation, payload, **options)`, and a factory
registry. Everything a test says about a domain ("a user can read only their own book
secret") is protocol-neutral in shape: arrange through calls, act through a call, assert
on the result.

Adapters own everything protocol-specific:

- **Rest** (VAmPI): HTTP verbs, bearer tokens, status codes, JSON bodies. A path guard
  rejects anything that is not a relative lab path.
- **GraphQL** (DVGA): one POST endpoint, query strings as the operation, `errors[]` as a
  first-class failure channel distinct from transport failure.
- **CatalogGrpc** (Online Boutique): reflection-free, so the adapter is generated-stub
  based; protobuf messages are converted to/from plain dicts so test code looks identical
  to the REST/GraphQL tests. gRPC status codes map into `Result.status` as strings.

Two things deliberately live *outside* the seam: authentication (`qa/auth.py` creates
synthetic users per API, because each lab logs in differently) and target safety
(`local_only` refuses non-loopback endpoints at adapter construction, so the suite cannot
be aimed at a real system).

Contract checking is a separate module, not woven into adapters. Each API type pins its
contract differently — OpenAPI JSON, GraphQL introspection-to-SDL, protobuf descriptor
bytes — but all three end in one function, `same_contract`, which fails with a unified
diff. Baselines are reviewed files in `contracts/`; tests never rewrite them.

## When a contract changes, a test fails — on purpose

There are two kinds of contract change and the suite treats them the same way on purpose:
a breaking API change and an intentional schema evolution both fail the contract test with
a diff. The fix for the second is a human reviewing the diff and committing the new
baseline in the same PR as the API change. That makes the contract baseline the
conversation between the API team and its consumers, which is exactly where a shared
framework earns its keep.

## Growing to 50 APIs owned by 10 teams

- **Config, not code, per API.** An API joins by adding a YAML entry
  (`protocol, endpoint, contract baseline path, risk tier`). The factory already resolves
  protocol -> adapter; `test_core.py` proves a new protocol can register without touching
  existing tests.
- **Teams own their baselines and their domain tests; the platform owns the seam.**
  Contract files and feature tests live in each team's directory and run in the same
  one runner session; tags (`risk_high`, `security`, `contract`) let CI slice the run:
  PRs run their API's high-risk tests, nightly runs everything.
- **One report, many suites.** the runner's JUnit/HTML output already aggregates across
  adapters; at 50 APIs the same artifacts fan out per team dashboard without new tooling.
- **Isolation scales the same way.** Each API gets its own process/port/env the way this
  repo already runs two VAmPI variants; `bootstrap.py`'s pinned-commit + clean-checkout
  verification becomes the supply-chain gate for all 50.

## What was chosen not to build

- **A generic HTTP/gRPC fuzzer or mutation engine.** High value later, wrong first spend:
  five deterministic security oracles found five real holes; a fuzzer would have found
  noise first.
- **Docker/Kubernetes orchestration.** venvs + one Go binary are faster, debuggable, and
  identical locally and in CI. Compose becomes worth it only when services with real
  infrastructure dependencies (databases, queues) join.
- **A load gate.** Sketched as the first next step (per-API latency baseline with a
  release threshold) rather than half-built now.
- **Testing the lab's weaponized endpoints** (DVGA `system_diagnostics`, `import_paste`).
  The framework demonstrates access-control failures on ordinary resources; actively
  exercising RCE/SSRF endpoints adds risk to the runner without adding information.
