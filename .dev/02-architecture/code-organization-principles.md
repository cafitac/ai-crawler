# Code Organization Principles

This document defines how implementation code should be structured for maintainability.

## Goals

- Maintainable OOP where state and lifecycle matter.
- Functional programming style for pure transformations and deterministic analysis.
- Explicit optionality; avoid nullable-by-accident design.
- Small focused files.
- Clear package boundaries.
- Testable modules with minimal hidden global state.

## Package boundaries

Initial package shape:

```text
src/ai_crawler/
  __init__.py
  cli/
    __init__.py
    main.py
    commands/
      doctor.py
      inspect.py
      probe.py
      recipe.py
      run.py
  core/
    __init__.py
    models/
      request.py
      response.py
      evidence.py
      recipe.py
      challenge.py
    safety/
      redaction.py
      url_policy.py
    traces/
      normalize.py
      classify.py
    inference/
      endpoint_score.py
      dependency_graph.py
    runner/
      engine.py
      result.py
      pagination.py
  adapters/
    __init__.py
    http/
      curl_cffi_fetcher.py
    browser/
      playwright_probe.py
    llm/
      client.py
      mock_client.py
    mcp/
      server.py
  testing/
    fixture_site/
      app.py
      scenarios.py
```

Rules:

- `core/` must not import `adapters/`.
- `core/` must not depend on Playwright, MCP, or real LLM providers.
- `adapters/` may depend on `core/`.
- CLI and MCP call application services; they do not own business logic.
- Test fixtures live under `testing/` or `tests/`, not mixed into runtime core.

## OOP usage

Use classes for:

- stateful workflows,
- lifecycle management,
- dependency-injected services,
- protocol implementations,
- long-lived runners/controllers.

Examples:

- `HttpFetcher`
- `BrowserProbe`
- `RecipeRunner`
- `AgentController`
- `ChallengeDetector`
- `SessionImporter`
- `EvidenceStore`

Class rules:

- One primary responsibility per class.
- Constructor takes explicit dependencies.
- Avoid hidden global state.
- Prefer immutable config objects.
- Keep methods short and behavior-focused.

## FP usage

Use pure functions for:

- trace normalization,
- endpoint scoring,
- header/cookie redaction,
- recipe validation helpers,
- pagination token extraction,
- challenge marker classification,
- deterministic transformations from input model to output model.

Function rules:

- Same input returns same output.
- No network, filesystem, clock, environment, or random access inside pure functions.
- Return typed result objects rather than mutating inputs.
- Keep side effects at adapter/service boundaries.

## Nullability policy

Avoid implicit nullable flows.

Rules:

- Do not return `None` to mean failure.
- Use explicit result types for success/failure.
- Use `Optional[T]` only when absence is a valid domain concept.
- Check optional values at the boundary and convert them into explicit domain states.
- Avoid dictionaries with maybe-missing keys for core models; use dataclasses/Pydantic models.

Preferred patterns:

```python
@dataclass(frozen=True)
class DetectionResult:
    detected: bool
    challenge: Challenge | None
    reason: str
```

When `None` appears, it must be documented as a real domain state.

For operations that can fail:

```python
@dataclass(frozen=True)
class Ok[T]:
    value: T

@dataclass(frozen=True)
class Err:
    code: str
    message: str
```

If Python version/tooling makes generic result classes awkward early on, use simple typed dataclasses such as `FetchResult`, `ValidationReport`, `RunResult`, and `DetectionReport` instead of returning `None`.

## File size and file responsibility

Guidelines:

- One major class per file by default.
- A file may contain a small dataclass family if they form one domain concept.
- Avoid files over roughly 250-350 lines unless there is a strong reason.
- Avoid “utils.py” dumping grounds.
- Prefer named modules such as `redaction.py`, `endpoint_score.py`, `dependency_graph.py`.
- If a module accumulates unrelated helpers, split it immediately.

## Dependency direction

Allowed:

```text
cli -> application/core
mcp -> application/core
adapters -> core
core.models -> no side-effect dependencies
core.runner -> core.models, core.safety, adapters interfaces only
```

Not allowed:

```text
core -> cli
core -> mcp
core -> playwright
core -> concrete LLM provider
core -> test fixture server
```

## Testing implication

Each package gets focused tests:

```text
tests/unit/core/models/
tests/unit/core/safety/
tests/unit/core/inference/
tests/component/adapters/http/
tests/integration/fixture_site/
tests/e2e/
```

Test style:

- pure functions: direct unit tests with table cases,
- OOP services: dependency injection with fake adapters,
- CLI/MCP: thin contract tests,
- LLM: `MockLLMClient` by default,
- browser: optional integration tests only.

## Review checklist

Before merging code:

- Is the module name specific?
- Is each class responsible for one workflow or concept?
- Could any method be a pure function?
- Are side effects isolated?
- Are absent values explicit?
- Would a new contributor know where to add related functionality?
- Can the feature be tested without real network/browser/LLM?
