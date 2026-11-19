# Bug reports

Every finding below was reproduced by this suite against the pinned lab revisions on
2026-11-19 (run: 34 tests, 5 failures, no errors/skips; JUnit in `artifacts/all-apis.xml`).
All data synthetic. Severity is judged as if these were production services: the labs are
intentionally vulnerable, and the tests are the regression gate for the fixes.

---

## BUG-001 — Any logged-in user can read any user's book secret (BOLA)

- **API:** VAmPI REST (`GET /books/v1/{title}`)
- **Severity:** High — cross-account data exposure, OWASP API #1
- **Steps:** register two synthetic users; user A creates a book with a secret; user B
  (valid token) requests the same title.
- **Expected:** 403 or 404 for user B. **Actual:** 200 with the secret and owner name.
- **Regression test:** `test_security.py::test_rest_cross_user_book_secret_denied`
  (positive control: owner read succeeds first).
- **Verified fixed in VAmPI secure mode** (`vulnerable=0`): the same test passes.

## BUG-002 — Self-registration grants admin via mass assignment

- **API:** VAmPI REST (`POST /users/v1/register`)
- **Severity:** High — privilege escalation
- **Steps:** register with the documented fields plus `"admin": true`; log in; call `/me`.
- **Expected:** `admin` is false / ignored. **Actual:** `admin: true`.
- **Regression test:** `test_security.py::test_rest_registration_cannot_grant_admin`.
- **Verified fixed in secure mode.**

## BUG-003 — Anonymous debug endpoint exposes every user's password

- **API:** VAmPI REST (`GET /users/v1/_debug`)
- **Severity:** Critical — full credential disclosure, no auth required
- **Steps:** `GET /users/v1/_debug` with no token.
- **Expected:** 401/403/404, or at minimum no password fields. **Actual:** 200 with every
  user's username, email, admin flag **and plaintext password**.
- **Regression test:** `test_security.py::test_rest_debug_does_not_expose_passwords`.
- **NOT fixed by the secure switch** — matches VAmPI's own documentation that the debug
  endpoint is exposed in both modes. Test asserts on response *content*, not just status,
  so a future 200-without-passwords also passes review.

## BUG-004 — Anonymous caller can read private pastes

- **API:** DVGA GraphQL (`query { paste(id) }`)
- **Severity:** High — cross-account data exposure
- **Steps:** create a paste with `public:false`; query it by id with no token.
- **Expected:** error or null. **Actual:** full content returned.
- **Regression test:** `test_security.py::test_graphql_private_paste_not_anonymous`
  (paste is deleted in `finally`; no lab state left behind).

## BUG-005 — `me` accepts an identity-tampered token (no signature verification)

- **API:** DVGA GraphQL (`query { me(token) }`)
- **Severity:** Critical — impersonation of any user, including the seeded admin
- **Steps:** log in as a synthetic user and verify `me` works (control); decode the token
  payload, change only the `identity` claim to the seeded lab admin, keep the original
  signature, resubmit.
- **Expected:** invalid-token error. **Actual:** `me` returns the admin's record —
  the server decodes without verifying the signature.
- **Regression test:** `test_security.py::test_graphql_tampered_identity_token_rejected`.
- Only a synthetic account's own token is tampered with; no real credentials exist in the lab.
