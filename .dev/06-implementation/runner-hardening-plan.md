# RecipeRunner Production Hardening Implementation Plan

> For Hermes: Use subagent-driven-development skill to implement this plan task-by-task.

Goal: Upgrade the deterministic HTTP execution path from MVP pagination replay into a production-ready runner with explicit execution guards, retry/backoff policy, challenge-aware failure classification, rate control, and resumable progress.

Architecture: Keep the browser probe and AI layers unchanged. Concentrate the hardening work in typed recipe models, the deterministic runner, and the CLI/test-report surfaces that already wrap `RecipeRunner`. Extend the existing sync runner first; only add concurrency after limits, retry semantics, and progress persistence are modeled and covered by deterministic component tests.

Tech Stack: Python 3.13, Pydantic models, pytest, JSONL artifacts, existing `curl-cffi` fetcher adapter.

Repo doc placement: this is a draft engineering plan, so keep it under `.dev/06-implementation/` rather than promoting it to public docs yet.

---

## Current baseline

Verified from the current codebase:
- `src/ai_crawler/core/runner/recipe_runner.py` only loops through expanded `query_page` requests and stops on first non-2xx or empty extraction.
- `src/ai_crawler/core/models/recipe.py` exposes `execution.concurrency` and `execution.delay_ms`, but the runner only uses `output_path` from `RunnerConfig` and ignores execution policy.
- `src/ai_crawler/core/models/crawl.py` only reports `recipe_name`, `items_written`, and `output_path`.
- `src/ai_crawler/core/agent/recipe_testing.py` classifies only `non_success_status`, `no_items_extracted`, and `no_response` from the first response.
- `tests/component/core/runner/test_recipe_runner.py` covers only happy-path pagination and stop-on-403 behavior.
- `bash scripts/verify-ai-harness.sh` is green now, so this plan should preserve current harness behavior while expanding coverage.

Implication: before adding throughput features, we need a richer runner contract that can describe why a run stopped, what was already written, and whether retry/resume is safe.

---

## Design constraints for this stream

- Do not move crawl execution back into the browser.
- Do not add AI calls inside the request loop.
- Preserve deterministic local tests; every behavior change needs unit/component coverage.
- Keep CLI default UX simple; advanced execution settings should still have safe defaults.
- Resume/checkpoint state must be explicit repo artifacts, not hidden process-local memory.
- Failure reports must become more informative without breaking existing `auto.report.json` consumers abruptly.

---

## Task 1: Add runner contract notes before code changes

Objective: lock the target behavior in draft docs so the implementation has one source of truth.

Files:
- Modify: `.dev/06-implementation/roadmap.md`
- Modify: `.dev/07-quality/testing-strategy.md`
- Reference: `.dev/07-quality/engineering-checklist.md`
- Reference: `src/ai_crawler/core/runner/recipe_runner.py`

Step 1: Add a short subsection to `roadmap.md` under Milestone 4 describing the first hardening slice:
- execution guards: `max_items`, `max_seconds`, `checkpoint_path`
- retry/backoff policy for 5xx and transport failures
- rate-control semantics for `delay_ms`
- resumable JSONL + checkpoint artifacts

Step 2: Update `testing-strategy.md` component test section to explicitly require deterministic tests for:
- retry budget exhaustion
- stop on challenge/ban statuses
- checkpoint write/read
- partial JSONL validity after interruption

Step 3: Re-read the engineering checklist and ensure the later implementation tasks explicitly cover:
- status-specific retry/backoff
- safe pagination stop conditions
- valid partial output during interruption

Verification:
- `read_file .dev/06-implementation/roadmap.md`
- `read_file .dev/07-quality/testing-strategy.md`

Commit:
- `git add .dev/06-implementation/roadmap.md .dev/07-quality/testing-strategy.md`
- `git commit -m "docs: define runner hardening slice"`

---

## Task 2: Expand typed execution models for hardening

Objective: model the runner policy in Pydantic before changing runtime behavior.

Files:
- Modify: `src/ai_crawler/core/models/recipe.py`
- Modify: `src/ai_crawler/core/models/crawl.py`
- Modify: `src/ai_crawler/core/models/__init__.py`
- Test: `tests/unit/core/models/test_models.py`

Step 1: Write failing model tests for new fields and defaults.

Add coverage for:
- `ExecutionSpec.max_items: int | None` or bounded int with `0/None` semantics chosen explicitly
- `ExecutionSpec.max_seconds`
- `ExecutionSpec.retry_attempts`
- `ExecutionSpec.retry_backoff_ms`
- `ExecutionSpec.retry_statuses`
- `ExecutionSpec.checkpoint_path`
- `CrawlResult.pages_attempted`
- `CrawlResult.requests_attempted`
- `CrawlResult.stop_reason`
- `CrawlResult.checkpoint_path`

Step 2: Run the focused model test.

Run:
- `pytest tests/unit/core/models/test_models.py -v`

Expected:
- FAIL due to missing fields or validation behavior.

Step 3: Implement the minimal model changes.

Implementation notes:
- keep defaults conservative so existing recipes still validate unchanged
- prefer explicit typed tuples for retry status codes if they must serialize cleanly
- add a bounded set of allowed stop reasons such as `completed`, `non_success_status`, `empty_page`, `max_items_reached`, `max_seconds_reached`, `challenge_detected`, `retry_exhausted`

Step 4: Re-run the focused test until green.

Run:
- `pytest tests/unit/core/models/test_models.py -v`

Step 5: Commit.

- `git add src/ai_crawler/core/models/recipe.py src/ai_crawler/core/models/crawl.py src/ai_crawler/core/models/__init__.py tests/unit/core/models/test_models.py`
- `git commit -m "feat: add runner hardening models"`

---

## Task 3: Add runner state helpers and stop-reason semantics

Objective: separate loop bookkeeping from fetch/extract logic so later retry and resume work stays readable.

Files:
- Modify: `src/ai_crawler/core/runner/recipe_runner.py`
- Test: `tests/component/core/runner/test_recipe_runner.py`

Step 1: Write failing component tests for richer crawl results without changing retry behavior yet.

Add tests asserting:
- successful pagination returns `stop_reason == "empty_page"` or `"completed"` based on the chosen contract
- 403 returns `stop_reason == "non_success_status"`
- `pages_attempted` and `requests_attempted` reflect actual loop progress

Step 2: Run the focused component tests.

Run:
- `pytest tests/component/core/runner/test_recipe_runner.py -v`

Expected:
- FAIL because `CrawlResult` lacks the new shape.

Step 3: Refactor `recipe_runner.py` into small helpers.

Target helper boundaries:
- request expansion / page iteration
- per-request execution result
- stop-decision computation
- item writing / item-count accounting

Keep behavior unchanged except for richer result metadata.

Step 4: Re-run the focused test.

Run:
- `pytest tests/component/core/runner/test_recipe_runner.py -v`

Step 5: Commit.

- `git add src/ai_crawler/core/runner/recipe_runner.py tests/component/core/runner/test_recipe_runner.py`
- `git commit -m "refactor: add runner state and stop reasons"`

---

## Task 4: Implement execution guards (`max_items`, `max_seconds`)

Objective: make long-running recipes stop safely and predictably.

Files:
- Modify: `src/ai_crawler/core/runner/recipe_runner.py`
- Possibly modify: `src/ai_crawler/cli/main.py`
- Test: `tests/component/core/runner/test_recipe_runner.py`
- Test: `tests/unit/cli/test_run_command.py`

Step 1: Write failing tests for guard behavior.

Component coverage:
- run stops after writing `max_items`
- run stops before the next request when `max_seconds` is exceeded
- partial JSONL remains valid after guarded stop

CLI coverage:
- `ai-crawler run` still prints a successful summary with the new stop reason and counts

Step 2: Run the targeted tests.

Run:
- `pytest tests/component/core/runner/test_recipe_runner.py tests/unit/cli/test_run_command.py -v`

Step 3: Implement guard checks.

Implementation notes:
- check `max_items` after each extracted item write so the last line is fully written
- check elapsed wall clock between requests, not mid-response
- choose whether hitting a guard returns exit code `0` or non-zero; document the rule and keep it stable

Step 4: Re-run the targeted tests.

Run:
- `pytest tests/component/core/runner/test_recipe_runner.py tests/unit/cli/test_run_command.py -v`

Step 5: Commit.

- `git add src/ai_crawler/core/runner/recipe_runner.py src/ai_crawler/cli/main.py tests/component/core/runner/test_recipe_runner.py tests/unit/cli/test_run_command.py`
- `git commit -m "feat: add runner execution guards"`

---

## Task 5: Add retry/backoff policy for transport errors and retryable statuses

Objective: make transient failures survivable without turning the runner into an infinite loop.

Files:
- Modify: `src/ai_crawler/core/runner/recipe_runner.py`
- Possibly modify: `src/ai_crawler/adapters/http/curl_cffi_fetcher.py`
- Possibly modify: `src/ai_crawler/core/models/request.py`
- Test: `tests/component/core/runner/test_recipe_runner.py`
- Test: `tests/component/adapters/http/test_curl_cffi_fetcher.py`

Step 1: Write failing tests for retry behavior.

Component coverage:
- retry once on 500 then succeed
- stop with `retry_exhausted` after retry budget ends
- do not retry 401/403 challenge-like responses
- apply deterministic backoff hook without sleeping in real time during tests

Adapter coverage if needed:
- normalize transport exceptions into a runner-observable failure path

Step 2: Run the focused tests.

Run:
- `pytest tests/component/core/runner/test_recipe_runner.py tests/component/adapters/http/test_curl_cffi_fetcher.py -v`

Step 3: Implement retry policy.

Implementation notes:
- keep the fetcher interface simple if possible; let the runner own retry orchestration
- inject a sleep function or clock helper into `RunnerConfig` only if tests need deterministic time control
- retries must be bounded by both attempts and wall-clock guard

Step 4: Re-run the focused tests.

Run:
- `pytest tests/component/core/runner/test_recipe_runner.py tests/component/adapters/http/test_curl_cffi_fetcher.py -v`

Step 5: Commit.

- `git add src/ai_crawler/core/runner/recipe_runner.py src/ai_crawler/adapters/http/curl_cffi_fetcher.py src/ai_crawler/core/models/request.py tests/component/core/runner/test_recipe_runner.py tests/component/adapters/http/test_curl_cffi_fetcher.py`
- `git commit -m "feat: add runner retry and backoff policy"`

---

## Task 6: Upgrade challenge and failure classification from runner metadata

Objective: preserve harness-friendly diagnostics once the runner has richer stop reasons.

Files:
- Modify: `src/ai_crawler/core/agent/recipe_testing.py`
- Modify: `src/ai_crawler/core/diagnostics/failure_classification.py`
- Test: `tests/unit/core/agent/test_recipe_testing.py`
- Test: `tests/unit/core/diagnostics/test_failure_classification.py`
- Possibly modify: `tests/unit/core/agent/test_auto_compiler.py`

Step 1: Write failing tests for richer test-report output.

Cover:
- `test_report` includes runner stop reason and request/page counts
- challenge-like 403/429 response maps to `challenge_detected`
- retry exhaustion maps to a retryable failure category distinct from plain `http_error`
- empty extraction after successful responses still maps to `extraction_failed`

Step 2: Run the focused tests.

Run:
- `pytest tests/unit/core/agent/test_recipe_testing.py tests/unit/core/diagnostics/test_failure_classification.py tests/unit/core/agent/test_auto_compiler.py -v`

Step 3: Implement the report/classification updates.

Implementation notes:
- keep existing keys where possible for report compatibility
- add new keys instead of replacing current ones outright
- prefer stable lowercase enum-like strings

Step 4: Re-run the focused tests.

Run:
- `pytest tests/unit/core/agent/test_recipe_testing.py tests/unit/core/diagnostics/test_failure_classification.py tests/unit/core/agent/test_auto_compiler.py -v`

Step 5: Commit.

- `git add src/ai_crawler/core/agent/recipe_testing.py src/ai_crawler/core/diagnostics/failure_classification.py tests/unit/core/agent/test_recipe_testing.py tests/unit/core/diagnostics/test_failure_classification.py tests/unit/core/agent/test_auto_compiler.py`
- `git commit -m "feat: classify runner hardening failures"`

---

## Task 7: Implement delay-based rate control

Objective: make the existing `execution.delay_ms` field real before attempting concurrent execution.

Files:
- Modify: `src/ai_crawler/core/runner/recipe_runner.py`
- Test: `tests/component/core/runner/test_recipe_runner.py`

Step 1: Write failing tests for deterministic inter-request delay behavior.

Cover:
- no delay before first request
- configured delay before second and later requests
- delay is skipped once a terminal stop condition is reached

Step 2: Run the focused test.

Run:
- `pytest tests/component/core/runner/test_recipe_runner.py -v`

Step 3: Implement rate control using an injected sleeper/clock strategy rather than raw `time.sleep` scattered through the loop.

Step 4: Re-run the focused test.

Run:
- `pytest tests/component/core/runner/test_recipe_runner.py -v`

Step 5: Commit.

- `git add src/ai_crawler/core/runner/recipe_runner.py tests/component/core/runner/test_recipe_runner.py`
- `git commit -m "feat: honor runner delay rate control"`

---

## Task 8: Add checkpoint/resume support for deterministic reruns

Objective: allow interrupted runs to continue without rewriting already completed pages/items.

Files:
- Modify: `src/ai_crawler/core/runner/recipe_runner.py`
- Modify: `src/ai_crawler/cli/main.py`
- Possibly modify: `src/ai_crawler/core/models/crawl.py`
- Test: `tests/component/core/runner/test_recipe_runner.py`
- Test: `tests/unit/cli/test_run_command.py`

Step 1: Write failing tests for checkpoint behavior.

Cover:
- runner writes checkpoint after each successful page
- second run resumes from the next page when checkpoint exists
- checkpoint and JSONL stay consistent when the previous run stopped via `max_seconds` or transient failure
- clean successful completion removes or marks checkpoint as complete by explicit policy

Step 2: Run the targeted tests.

Run:
- `pytest tests/component/core/runner/test_recipe_runner.py tests/unit/cli/test_run_command.py -v`

Step 3: Implement checkpoint semantics.

Checkpoint payload should minimally capture:
- recipe identifier
- next page/request cursor
- items already written
- output path
- last stop reason

Implementation notes:
- use JSON, not pickle
- reject mismatched checkpoint/recipe combinations clearly
- avoid reading the entire JSONL file to resume if the checkpoint already stores counts

Step 4: Re-run the targeted tests.

Run:
- `pytest tests/component/core/runner/test_recipe_runner.py tests/unit/cli/test_run_command.py -v`

Step 5: Commit.

- `git add src/ai_crawler/core/runner/recipe_runner.py src/ai_crawler/cli/main.py src/ai_crawler/core/models/crawl.py tests/component/core/runner/test_recipe_runner.py tests/unit/cli/test_run_command.py`
- `git commit -m "feat: add runner checkpoint resume"`

---

## Task 9: Decide on concurrency only after the sequential contract is stable

Objective: avoid mixing async throughput work with state-model churn.

Files:
- Modify: `.dev/06-implementation/runner-hardening-plan.md`
- Create: `.dev/06-implementation/runner-concurrency-spike.md`
- Reference: `src/ai_crawler/core/models/recipe.py`

Step 1: Do not implement `execution.concurrency > 1` in the same PR as retry/resume.

Step 2: After Tasks 1-8 land, run a short design spike answering:
- will concurrency stay threaded/sync or move to async execution?
- how will ordered JSONL output work under concurrency?
- does checkpoint state track request index, page cursor, or durable work queue?
- do per-domain and global concurrency need separate config fields?

Step 3: Save the spike note as a separate draft if concurrency still belongs in Milestone 4.

Decision outcome:
- Keep the current sequential runner as the correctness oracle.
- Do not add threaded concurrency inside the existing `RecipeRunner` loop.
- If concurrency work proceeds, use a dedicated async scheduler + single ordered writer design.
- Preserve `next_request_index` as the first durable checkpoint cursor.
- Split `per_domain_concurrency` / richer rate-limit config into a follow-up contract PR instead of overloading `delay_ms`.
- See `.dev/06-implementation/runner-concurrency-spike.md` for the full design note.

Verification:
- concurrency decision is documented before code starts

Commit:
- `git add .dev/06-implementation/runner-hardening-plan.md .dev/06-implementation/runner-concurrency-spike.md`
- `git commit -m "docs: scope runner concurrency follow-up"`

---

## Final verification pass

Run the full repo checks after the last code task, not just focused tests.

Commands:
- `pytest tests/unit -q`
- `pytest tests/component -q`
- `bash scripts/verify-ai-harness.sh`

Optional before merging:
- add one fixture-driven smoke covering an interrupted run followed by resume if the fixture site already exposes enough pagination determinism

Success criteria:
- existing auto/compile harness reports still pass
- new runner metadata is present and stable
- partial output remains valid JSONL
- retry and resume behavior is deterministic under tests

---

## Recommended PR slicing

1. PR A: docs + execution models + richer crawl result
2. PR B: guard limits + rate control
3. PR C: retry/backoff + diagnostics upgrades
4. PR D: checkpoint/resume
5. PR E: concurrency design spike or implementation, only if still needed

This keeps report-shape changes reviewable and reduces the chance of shipping a half-designed execution contract.

---

## Ready-to-execute next action

Highest-priority next implementation step: complete Task 2 first and land the typed execution model expansion before touching runtime behavior.

Concrete branch suggestion:
- `feat/runner-hardening-models`

First commands:
- `git checkout -b feat/runner-hardening-models`
- `pytest tests/unit/core/models/test_models.py -v`
- edit `src/ai_crawler/core/models/recipe.py`
- edit `src/ai_crawler/core/models/crawl.py`

If you return later with “이제 뭐해야하지?” the answer for this repo should be:
- "ai-crawler는 runner hardening을 시작하면 돼. 우선 `feat/runner-hardening-models` 브랜치에서 execution model과 CrawlResult를 확장하고, `tests/unit/core/models/test_models.py`부터 RED→GREEN으로 진행해."