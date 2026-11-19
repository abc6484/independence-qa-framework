# Regression model: features rated by risk

Rating combines **impact** (what breaks for the business if this fails) and **change
surface** (how likely this area is to break). Levels:

- **High** — blocks a release. Authentication/identity, object-level access to private
  data, contract shape, core create-read flows. Runs on every PR.
- **Medium** — blocks a scheduled release train, not an emergency fix. Validation and
  negative paths, search, duplicate handling. Runs on PR for the owning API, nightly for all.
- **Shallow/explicit** — areas deliberately not covered, listed at the bottom so the gap
  is a decision, not an accident.

## Team A — VAmPI (REST, token auth) — DEEP

| Feature | Risk | What is tested | Why |
|---|---|---|---|
| Register + login + `/me` identity | High | Round-trip with exact JSON schema on `/me` | Every other check needs a trustworthy identity |
| Book create/read lifecycle | High | Create, owner read with exact body, duplicate rejected | Core resource flow; pins response shape |
| Anonymous access to books | High | 401 without token | Cheapest auth regression to write, worst to miss |
| Cross-user secret read (BOLA) | High (security) | Owner positive control, then second user must get 403/404 | OWASP API #1; lab ships it broken, gate stays green only after fix |
| Mass assignment on register | High (security) | `admin:true` in payload must not yield admin | Privilege escalation via one extra field |
| Debug endpoint data exposure | High (security) | Response must contain no passwords (any status) | Exposed in *both* VAmPI modes; status alone is not proof of safety |
| Invalid create body | Medium | 400 on missing fields | Input-validation drift |
| OpenAPI contract | High | Served spec vs reviewed baseline, servers URL normalized | First thing consumers break on |

## Team B — DVGA (GraphQL, own login) — DEEP

| Feature | Risk | What is tested | Why |
|---|---|---|---|
| createUser + login + `me` | High | Token issued, `me(token)` returns the same username | Identity again; GraphQL passes token as an argument here |
| Paste create/read/delete round-trip | High | Public paste lifecycle with cleanup in `finally` | Core resource flow, leaves no state |
| Private paste readable anonymously | High (security) | Create private paste, anonymous read must return nothing | Object-level authorization, the GraphQL twin of BOLA |
| Token signature verification | High (security) | Valid control, then identity-tampered token must be rejected | `me` decodes without verifying; forgery must fail |
| Unknown field / missing variable | Medium | GraphQL `errors[]` returned, not a 500 or silent null | Error-channel shape is the GraphQL contract too |
| Schema (SDL from introspection) | High | Introspected schema vs reviewed SDL baseline | GraphQL's contract is the schema itself |

## Team C — Online Boutique product catalog (gRPC, no auth) — SHALLOW

| Feature | Risk | What is tested | Why |
|---|---|---|---|
| List/Get/Search products | High | Non-empty list, exact Get-by-id equality with list entry, case-insensitive search hit | Read path every other boutique service depends on |
| Get unknown/empty id | Medium | `NOT_FOUND` status | Error mapping through the adapter |
| Search no-match | Medium | Empty results, still `OK` | Distinguish "none found" from failure |
| Anonymous read | Medium (security) | Documented as intended: no inter-service auth is the lab's stated architecture, asserted green so it reads as a decision | Avoids inventing a bug the design accepts |
| protobuf contract | High | Descriptor of running source vs reviewed `demo.proto` | No reflection on this server; descriptor + live responses pin the shape |

**Left shallow and why:** other boutique services (cart, checkout, currency, shipping) —
each is a new adapter of an already-proven pattern, and catalog covers the gRPC seam;
DVGA subscriptions/upload/SSRF/command surfaces — not exercised deliberately (see
DESIGN.md); VAmPI SQLi/ReDoS/rate-limit surfaces — the five access-control findings
already demonstrate the security pack without adding slow or state-corrupting probes.
