# One test framework for three teams' APIs

A single pytest framework that tests a REST API (VAmPI), a GraphQL API (DVGA) and a
gRPC service (Online Boutique product catalog) through one small adapter seam, with
contract-drift detection, a risk-rated regression model, security tests that fail on
the holes they find, and one report across all three APIs.

All targets are the exact pinned revisions, run locally. All test data is synthetic.

## Layout

```
qa/adapters.py      one call() seam; Rest / GraphQL / CatalogGrpc adapters
qa/contracts.py     reviewed-snapshot contract checks (OpenAPI, GraphQL SDL, protobuf)
qa/auth.py          synthetic account creation and login per API
tests/              unit, regression (deep: REST + GraphQL; shallow: gRPC) and security tests
contracts/          reviewed baselines: vampi.openapi.yaml, dvga.graphql, demo.proto
scripts/bootstrap.py  clone pinned revisions, build isolated envs, verify clean checkouts
scripts/run_lab.py    start all services, run both suites, always stop everything
.github/workflows/qa.yml  the same gate in CI
docs/               DESIGN.md, RISK_MODEL.md, BUGS.md
```

## Run it

Prereqs: Python 3.10, Go >= 1.25.8 (only to build the catalog service; the upstream
go.mod asks for `go 1.25.8` with `toolchain go1.27.1`, and Go auto-downloads that
toolchain on first build), git, network access to github.com and pypi.org on first setup.
**No Docker, no root.** Docker is fine to have installed - it is simply not used; this
suite runs the pinned apps natively so there is one path to learn and debug.

Verified here with Python 3.10.12 and `go version go1.26.6 linux/amd64`.

**macOS** (not yet executed - developed and verified on Linux): the suite deliberately
avoids ports 5000/5001 because macOS AirPlay Receiver occupies them; it uses 5101/5102,
5013 and 3550 on loopback. Install prereqs with `brew install python@3.10 go git`, then
the same commands below (`python3.10 -m venv .venv`). If anything behaves differently on
macOS, the first run's `artifacts/*.log` will show it.

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.lock
.venv/bin/python scripts/bootstrap.py          # clones pinned commits, builds services
.venv/bin/python scripts/run_lab.py --isolated-lab
```

Network exposure: the launcher binds VAmPI and DVGA to 127.0.0.1 only. The upstream
catalog gRPC server binds all interfaces (its own code, unmodified); it serves a read-only
demo product catalog with no auth by design, so the exposure is the demo data, not your
machine - but on an untrusted network anyone nearby could also reach the two intentionally
vulnerable apps if you rebind them. Prefer a disposable VM, a CI runner, or a trusted
network. `--isolated-lab` is a deliberate acknowledgment of that choice, not a safety
mechanism by itself. The test adapters separately refuse any non-loopback target, so the
suite cannot be pointed at a remote system.

The runner starts VAmPI twice (`vulnerable=1` on :5102, `vulnerable=0` on :5101), DVGA on
:5013 and the catalog gRPC server on :3550, waits for readiness, then runs:

1. the full suite against the vulnerable stack -> `artifacts/all-apis.html` + JUnit XML
2. the REST security pack against VAmPI's secure mode -> `artifacts/secure-mode.html`

## What a green/red run means

Against the intentionally vulnerable targets, the security tests are **supposed to fail**:
each failure is a real, reproduced hole, written up in `docs/BUGS.md` with the test that
stops it coming back. The suite is the regression gate you run after the fix lands; today
it proves the holes exist. There are no `xfail`s and no inverted assertions.

Verified run (local Linux x86_64, Python 3.10.12, Go 1.26.6 with the go1.27.1
toolchain auto-downloaded for the catalog build). The GitHub Actions workflow in
.github/workflows/ runs the identical commands but has NOT been executed on GitHub yet;
the evidence below is from the local run only:

| Suite | Tests | Passed | Failed | Notes |
|---|---|---|---|---|
| all-apis (vulnerable targets) | 34 | 29 | 5 | 5 failures = BUG-001..005, no errors/skips |
| secure-mode (VAmPI vulnerable=0) | 3 | 2 | 1 | BOLA + mass assignment fixed by the switch; debug password exposure (BUG-003) remains |

The secure/vulnerable comparison is the false-positive control: two of three REST security
tests flip green in secure mode, so the pack is detecting the vulnerability switch, not
just failing everywhere. BUG-003 stays red in both, matching VAmPI's own note that the
debug endpoint is exposed in either mode.

## Choices made

- **One seam, not one client.** Every test calls `adapter.call(operation, payload)` and gets
  back `Result(status, data, errors)`. Auth, retries and protocol quirks live in the
  adapters and `qa/auth.py`; tests only carry domain assertions. Adding a fourth API type
  means adding one entry to `FACTORIES` (unit-tested in `test_core.py`), not rewriting tests.
- **Snapshot contracts with human review.** Baselines in `contracts/` were captured from the
  pinned revisions and reviewed. Tests diff the live contract against them and fail with a
  readable diff. They never self-update; a contract change is a deliberate commit, which is
  exactly when a human should look. Only deployment-specific OpenAPI `servers[].url` values
  are normalized.
- **gRPC contract = descriptor equality + live RPC behavior.** The catalog server has no
  reflection, so the proto descriptor of the running source is compared to the reviewed
  `contracts/demo.proto`, and live RPC tests pin the response shape.
- **Security tests assert safe behavior and fail on holes.** Each one also proves a positive
  control first (e.g. the owner can read their own book) so a failure can't be dismissed as
  a broken test.
- **No Docker dependency.** The pinned apps are small Python/Go programs; venvs plus one Go
  build are faster and easier to debug in CI than compose. The CI workflow runs the identical
  commands as `scripts/bootstrap.py` + `scripts/run_lab.py`, so local and CI cannot drift in
  procedure (the workflow itself is written but not yet executed on GitHub Actions).
- **Upstream seed flakiness contained, not patched.** VAmPI's demo-data seeding uses
  `randrange(100)` for globally unique book titles and randomly collides on setup.
  `launcher.py` fixes the RNG seed for the lab process only; upstream source stays untouched
  and `bootstrap.py` refuses dirty checkouts.

## Left shallow / not built

- gRPC coverage is one service (product catalog): happy path, search, NOT_FOUND, contract.
  The other boutique services, and cross-service flows, are future adapters.
- DVGA subscriptions, file upload and the SSRF/command surfaces are not tested. The framework
  deliberately does not weaponize the lab's own attack endpoints; five access-control and
  token findings were enough to demonstrate the pack.
- No load gate yet. First next step: a 30-second per-API latency baseline with a release
  threshold, wired as another marker in the same suite.
- No mutation/fuzz testing; property-based generators per adapter would be the second next step.

## Where AI was used

AI (an LLM coding assistant) drafted the framework code, tests, scripts and docs in this repo.
The pinned upstream applications were run unmodified and every reported result comes from an
actual executed run of this suite on this machine; nothing is paraphrased from the upstream
projects' READMEs. The bug reports were confirmed by the failing tests quoted in
`docs/BUGS.md`, including the secure-mode control run. The author has reviewed the code and
can walk through every part: start at `qa/adapters.py`, then `qa/contracts.py`, then the
security tests.

## Growing to 50 APIs / 10 teams

See `docs/DESIGN.md` (the 2-page note): adapter-per-protocol with config-per-API, contract
baselines owned by each team, and the same pytest markers as the organization-wide risk model.
