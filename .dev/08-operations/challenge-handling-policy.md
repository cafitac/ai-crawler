# Challenge Handling Policy

This document defines how `ai-crawler` handles CAPTCHA, MFA, Cloudflare-style challenges, bot challenges, access-control failures, and other protective boundaries.

## Position

`ai-crawler` does not bypass access controls.

It supports authorized network-flow analysis and replay. When a protection boundary appears, the system detects it, explains it, pauses for explicit user action, imports only authorized session state when allowed, or stops safely.

## Allowed capabilities

`ai-crawler` may implement:

- challenge detection,
- challenge classification,
- failure explanation,
- manual handoff to the user,
- authorized session import,
- secure local session storage,
- redacted evidence bundles,
- authenticated request replay after legitimate user completion,
- fixture-based challenge simulation,
- session expiry detection,
- CSRF/session dependency graph modeling.

## Disallowed capabilities

`ai-crawler` must not implement:

- CAPTCHA solving or CAPTCHA-solver service integration,
- MFA bypass,
- Cloudflare or bot-protection bypass logic,
- stealth fingerprint evasion,
- undetectable scraping claims,
- proxy rotation for block evasion,
- account protection circumvention,
- credential harvesting,
- unauthorized access automation.

## Product language

Use:

```text
challenge detection
manual handoff
authorized session replay
network-flow analysis
session dependency modeling
failure diagnosis
```

Avoid:

```text
bypass Cloudflare
solve CAPTCHA
avoid bot detection
undetectable scraping
stealth login automation
break into protected sites
```

## Core components

### ChallengeDetector

Detects protection boundaries from HTTP responses, redirects, headers, HTML markers, and browser probe observations.

Inputs:

- normalized response metadata,
- redirect chain,
- response body snippets after redaction,
- browser probe event summary,
- request context.

Outputs:

```yaml
challenge:
  detected: true
  type: cloudflare | captcha | mfa | device_verification | csrf_failure | auth_required | rate_limit | forbidden | unknown
  confidence: 0.0-1.0
  evidence:
    - status: 403
    - header: server
    - marker: challenge-form
  recommended_action: manual_handoff | refresh_session | stop | reduce_rate | inspect_browser
```

### ManualHandoff

Pauses automation and asks the authorized user to complete a step manually in the browser.

Rules:

- The user must perform the challenge themselves.
- The system must not automate the protected step.
- The system may resume only after user confirmation and successful authorized session capture.
- Handoff state must be auditable.

### SessionImporter

Imports authorized session state after the user completes login/challenge manually.

Rules:

- Do not store raw cookies/tokens in repo files.
- Do not print secrets in logs.
- Store local session material only in explicitly configured local secret/session storage.
- Recipes reference session handles, not raw secret values.

### FailureExplainer

Explains why a recipe or replay failed.

Examples:

```text
Replay stopped because a Cloudflare-style challenge page was detected.
This run requires manual handoff; ai-crawler will not bypass the challenge.
```

```text
Replay failed because the CSRF token dependency was stale.
Refresh session or re-run browser probe to capture a new token source.
```

## Recipe fields

Recipes may include challenge policy:

```yaml
auth:
  mode: none | manual_handoff | session_import
  session_ref: local://sessions/example

challenge_policy:
  on_captcha: pause
  on_mfa: pause
  on_cloudflare_challenge: pause
  on_rate_limit: slow_down
  on_forbidden: stop
  on_unknown_challenge: stop

execution:
  stop_on_challenge: true
  explain_failure: true
```

Raw secrets must never be embedded in the recipe.

## Test strategy

Default tests use local fixture challenges only.

Fixture scenarios:

- `/challenge/cloudflare-like` returns challenge-shaped HTML.
- `/challenge/captcha-like` returns a CAPTCHA placeholder.
- `/challenge/mfa-like` returns a mock MFA page.
- `/challenge/rate-limit` returns HTTP 429.
- `/auth/login` issues CSRF and session cookies.
- `/auth/protected-api` requires valid fixture session.

Required tests:

- detector classifies fixture challenge pages,
- runner pauses/stops according to policy,
- logs redact cookies/tokens,
- recipe never stores raw session values,
- manual handoff state is represented without bypass automation,
- authenticated replay works only for fixture-authorized sessions.

## Real-world opt-in tests

Real websites are excluded from default CI.

A real-world test must require explicit local opt-in and must satisfy:

- user is authorized to access the account/system,
- no credentials are committed,
- no CAPTCHA/MFA/bot challenge bypass is attempted,
- raw session material is local-only,
- output is redacted before storing evidence.

## Implementation guardrails

Before merging challenge-related code, verify:

- no solver integrations,
- no stealth/evasion module,
- no proxy-rotation evasion feature,
- no raw cookie/token logging,
- no hardcoded real-site credentials,
- local fixture coverage exists,
- manual handoff is explicit and auditable.
