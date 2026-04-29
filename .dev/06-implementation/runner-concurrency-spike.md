# RecipeRunner Concurrency Spike

> Draft note for the post-checkpoint hardening slice. Concurrency stays out of the current sequential runner PR stream until the execution contract is stable and explicitly documented.

## Goal

Decide whether `execution.concurrency > 1` still belongs in Milestone 4, and if so, define the safest first implementation slice.

## Current baseline

Verified from the current codebase and hardening work landed so far:
- `RecipeRunner` is still a synchronous request loop.
- JSONL output ordering is naturally request order today because writes happen inline after each fetch/extract step.
- checkpoint/resume persists `next_request_index`, `items_written`, `output_path`, and `stop_reason`.
- retry/backoff, `delay_ms`, `max_items`, and `max_seconds` all assume one active request at a time.
- `ExecutionSpec` already exposes `concurrency`, but there is no runtime implementation behind values greater than `1`.
- the broader product docs mention async execution, per-domain concurrency, and token-bucket rate limiting as Milestone 4 goals.

Implication: the main risk is not "making fetches parallel" but preserving deterministic stop semantics, ordered output, and resumable progress once more than one request can be in flight.

## Questions answered

### 1. Threaded/sync first, or move directly to async?

Decision: do not retrofit threads into the existing runner as the first concurrency step. If concurrency is implemented, move to an explicit async execution layer instead of mixing `time.sleep`, sync fetch calls, and ad-hoc worker threads inside `RecipeRunner`.

Why:
- the roadmap and architecture notes already point toward an async scheduler.
- threaded concurrency would duplicate future migration cost while still forcing new locking around checkpoint writes, output ordering, and counters.
- the current runner now has several time-sensitive policies (`delay_ms`, retry backoff, `max_seconds`) that become harder to reason about if each worker owns its own clock/sleep behavior.
- `curl-cffi` capability notes already assume async support is available later.

Practical reading: keep the current sequential runner as the stable reference implementation. Build any concurrent path as a new scheduler boundary, not as conditionals sprinkled through the existing loop.

### 2. How should ordered JSONL output work?

Decision: preserve deterministic request-order JSONL as the default contract even under concurrency.

Recommended mechanism:
- execution workers may fetch/extract out of order.
- each completed unit publishes `(request_index, extracted_items, stop_metadata)` into an in-memory completion map.
- a single writer stage flushes only the next contiguous `request_index` to the JSONL sink.
- checkpoint advancement happens only when the writer flushes a contiguous prefix.

Why this contract is safer:
- existing sequential output stays reproducible.
- checkpoint state continues to mean "everything before `next_request_index` is durably written".
- downstream tests and fixture expectations stay readable.

Rejected first-slice alternative:
- letting workers append JSONL directly with a file lock. That increases throughput but weakens ordering, complicates checkpoint semantics, and makes deterministic component tests harder.

### 3. What should checkpoint state track under concurrency?

Decision: keep `next_request_index` as the durable checkpoint cursor for the first concurrency design, but allow the runtime to maintain a transient in-memory set of in-flight/completed-not-yet-flushed requests.

Durable checkpoint should continue to represent only flushed contiguous progress:
- `next_request_index`
- `items_written`
- `output_path`
- `stop_reason`

Do not persist a durable work queue in the first concurrency slice.

Why:
- request-index checkpoints already work for the sequential runner and match ordered-writer semantics.
- persisting partial out-of-order worker state would enlarge the failure surface immediately.
- a durable work queue may become necessary later only if recipes gain branching/cursor-derived request graphs instead of the current finite expanded request list.

### 4. Do global and per-domain concurrency need separate config fields?

Decision: yes, but not in the same PR as the first runtime scheduler spike.

Recommended model progression:
1. Keep current `execution.concurrency` meaning "global max in-flight requests".
2. Add `execution.per_domain_concurrency` only when the scheduler exists to honor it.
3. Add a separate rate-limit model afterward if token-bucket semantics are needed (`delay_ms` alone is not enough for concurrent execution).

Why:
- current recipes and loader tests already understand `execution.concurrency`.
- per-domain concurrency without a scheduler would be dead config.
- token-bucket policy likely deserves its own explicit fields rather than overloading `delay_ms`.

## Recommended next implementation slice

Concurrency still belongs in Milestone 4, but only as a separate follow-up stream after this spike.

Recommended PR order:
1. docs-only spike (this PR)
2. model contract PR for concurrent execution fields if needed (`per_domain_concurrency`, maybe explicit rate-limit config)
3. async scheduler prototype behind deterministic component fixtures
4. ordered-writer + checkpoint advancement integration
5. follow-up operational polish (`metrics`, richer progress reporting, maybe streaming sinks)

## Proposed implementation boundaries

When the code work starts, keep these boundaries explicit:
- `RecipeRunner` remains the simple sequential reference path and/or delegates to a scheduler abstraction.
- new scheduler owns in-flight concurrency, worker lifecycle, and fairness.
- one writer owns JSONL flush ordering and checkpoint advancement.
- stop reasons remain centralized so `test_report`, CLI summaries, and failure classification do not fork by execution mode.

## Risks to design around

1. `max_seconds` under concurrency
   - wall-clock timeout can fire with multiple requests already in flight.
   - define whether in-flight work is cancelled immediately or allowed to finish but not flush.

2. `max_items` under concurrency
   - several workers may produce enough items to overshoot the cap.
   - the writer must own the final cap and truncation semantics, not the workers.

3. retry/backoff amplification
   - concurrent retries can create traffic spikes.
   - per-domain fairness and retry budgets should be scheduler-owned.

4. challenge boundary handling
   - a challenge/ban signal from one worker may need to halt remaining in-flight work for that domain or whole run.

5. deterministic tests
   - fixture coverage must avoid timing flakes.
   - injectable clock/sleep hooks were a good prerequisite and should be preserved in the scheduler design.

## Recommendation

Do not implement `execution.concurrency > 1` on top of the current loop in the next PR.

Instead:
- treat this spike as the decision gate,
- keep the sequential runner as the correctness oracle,
- and start concurrency with an async scheduler + ordered writer design once the config surface for global/per-domain limits is explicit.

## Ready follow-up question for the next PR

"Should the first concurrency PR be docs+models only (`per_domain_concurrency` / rate-limit contract), or should it include the minimal async scheduler for a fixed request list?"
