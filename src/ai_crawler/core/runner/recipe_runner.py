"""Deterministic recipe runner."""

import asyncio
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pydantic import Field

from ai_crawler.core.models import CrawlResult, FetchResponse, Recipe, RequestSpec
from ai_crawler.core.models.base import DomainModel
from ai_crawler.core.models.recipe import RunnerStopReason
from ai_crawler.core.runner.extraction import extract_items


class RunnerConfig(DomainModel):
    """Configuration for a deterministic recipe run."""

    output_path: str = Field(min_length=1)


class RunnerCheckpoint(DomainModel):
    """Persisted runner resume state."""

    recipe_name: str = Field(min_length=1)
    next_request_index: int = Field(ge=0)
    items_written: int = Field(ge=0)
    output_path: str = Field(min_length=1)
    stop_reason: RunnerStopReason


@dataclass(slots=True)
class RunState:
    items_written: int
    pages_scheduled: int
    pages_attempted: int
    requests_attempted: int
    stop_reason: RunnerStopReason
    current_request_index: int


class RecipeFetcher(Protocol):
    """Minimal fetcher interface required by RecipeRunner."""

    def fetch(self, request: RequestSpec) -> FetchResponse:
        """Fetch one normalized request."""


class TextWriter(Protocol):
    def write(self, text: str) -> object:
        """Write text to the output sink."""


class RecipeRunner:
    """Run a validated recipe with a deterministic HTTP fetcher."""

    def __init__(self, fetcher: RecipeFetcher, config: RunnerConfig) -> None:
        self._fetcher = fetcher
        self._config = config
        self._clock = time.monotonic
        self._sleep = time.sleep

    def run(self, recipe: Recipe) -> CrawlResult:
        """Execute a recipe and write extracted items as JSON Lines."""
        _validate_execution_mode(recipe)
        output_path = Path(self._config.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        requests = _expand_requests(recipe)
        checkpoint_path = _checkpoint_path(recipe)
        checkpoint = _load_checkpoint(
            checkpoint_path=checkpoint_path,
            recipe=recipe,
            output_path=output_path,
            request_count=len(requests),
        )
        next_request_index = checkpoint.next_request_index if checkpoint else 0
        items_written = checkpoint.items_written if checkpoint else 0
        started_at = self._clock()
        file_mode = "a" if next_request_index > 0 and output_path.exists() else "w"
        with output_path.open(file_mode, encoding="utf-8") as output_file:
            if recipe.execution.concurrency == 1:
                state = self._run_sequential(
                    recipe=recipe,
                    requests=requests,
                    output_file=output_file,
                    output_path=output_path,
                    checkpoint_path=checkpoint_path,
                    next_request_index=next_request_index,
                    items_written=items_written,
                    started_at=started_at,
                )
            else:
                state = self._run_concurrent(
                    recipe=recipe,
                    requests=requests,
                    output_file=output_file,
                    output_path=output_path,
                    checkpoint_path=checkpoint_path,
                    next_request_index=next_request_index,
                    items_written=items_written,
                    started_at=started_at,
                )

        final_checkpoint_path = _finalize_checkpoint(
            checkpoint_path=checkpoint_path,
            recipe=recipe,
            output_path=output_path,
            next_request_index=_resume_request_index(
                stop_reason=state.stop_reason,
                current_request_index=state.current_request_index,
                next_request_index=next_request_index,
                pages_attempted=state.pages_attempted,
            ),
            items_written=state.items_written,
            stop_reason=state.stop_reason,
        )
        return CrawlResult(
            recipe_name=recipe.name,
            items_written=state.items_written,
            output_path=str(output_path),
            pages_scheduled=state.pages_scheduled,
            pages_attempted=state.pages_attempted,
            requests_attempted=state.requests_attempted,
            stop_reason=state.stop_reason,
            checkpoint_path=final_checkpoint_path,
        )

    def _run_sequential(
        self,
        recipe: Recipe,
        requests: tuple[RequestSpec, ...],
        output_file: TextWriter,
        output_path: Path,
        checkpoint_path: Path | None,
        next_request_index: int,
        items_written: int,
        started_at: float,
    ) -> RunState:
        current_request_index = next_request_index
        pages_scheduled = 0
        pages_attempted = 0
        requests_attempted = 0
        stop_reason: RunnerStopReason = "completed"
        max_items = recipe.execution.max_items
        max_seconds = recipe.execution.max_seconds
        delay_ms = recipe.execution.delay_ms
        for request_index in range(next_request_index, len(requests)):
            request = requests[request_index]
            if _max_seconds_reached(self._clock, started_at, max_seconds, pages_attempted):
                stop_reason = "max_seconds_reached"
                break
            _sleep_between_requests(self._sleep, delay_ms, pages_attempted)
            if _max_seconds_reached(self._clock, started_at, max_seconds, pages_attempted):
                stop_reason = "max_seconds_reached"
                break
            current_request_index = request_index
            pages_scheduled += 1
            pages_attempted += 1
            response, request_attempts, stop_reason = self._fetch_with_retries(
                request=request,
                recipe=recipe,
                started_at=started_at,
            )
            requests_attempted += request_attempts
            if response is None or stop_reason == "non_success_status":
                break
            extracted_items = _extract_response_items(response, recipe)
            items_written, stop_reason = _write_items(
                output_file=output_file,
                items=extracted_items,
                items_written=items_written,
                max_items=max_items,
            )
            if stop_reason == "max_items_reached":
                break
            if not extracted_items:
                stop_reason = "empty_page"
                break
            _write_checkpoint(
                checkpoint_path=checkpoint_path,
                recipe=recipe,
                output_path=output_path,
                next_request_index=request_index + 1,
                items_written=items_written,
                stop_reason="completed",
            )
        return RunState(
            items_written=items_written,
            pages_scheduled=pages_scheduled,
            pages_attempted=pages_attempted,
            requests_attempted=requests_attempted,
            stop_reason=stop_reason,
            current_request_index=current_request_index,
        )

    def _run_concurrent(
        self,
        recipe: Recipe,
        requests: tuple[RequestSpec, ...],
        output_file: TextWriter,
        output_path: Path,
        checkpoint_path: Path | None,
        next_request_index: int,
        items_written: int,
        started_at: float,
    ) -> RunState:
        requests_to_fetch = tuple(
            enumerate(requests[next_request_index:], start=next_request_index)
        )
        return asyncio.run(
            self._run_concurrent_async(
                recipe=recipe,
                requests_to_fetch=requests_to_fetch,
                output_file=output_file,
                output_path=output_path,
                checkpoint_path=checkpoint_path,
                next_request_index=next_request_index,
                items_written=items_written,
                started_at=started_at,
            )
        )

    async def _run_concurrent_async(
        self,
        recipe: Recipe,
        requests_to_fetch: tuple[tuple[int, RequestSpec], ...],
        output_file: TextWriter,
        output_path: Path,
        checkpoint_path: Path | None,
        next_request_index: int,
        items_written: int,
        started_at: float,
    ) -> RunState:
        semaphore = asyncio.Semaphore(recipe.execution.concurrency)
        pending_results: dict[int, tuple[FetchResponse | None, int, RunnerStopReason]] = {}
        pending_tasks: set[
            asyncio.Task[tuple[int, tuple[FetchResponse | None, int, RunnerStopReason]]]
        ] = set()
        next_schedule_offset = 0
        max_items = recipe.execution.max_items
        max_seconds = recipe.execution.max_seconds
        delay_ms = recipe.execution.delay_ms
        terminal_state: RunState | None = None

        while (
            len(pending_tasks) < recipe.execution.concurrency
            and next_schedule_offset < len(requests_to_fetch)
        ):
            await _sleep_before_concurrent_launch(self._sleep, delay_ms, next_schedule_offset)
            request_index, request = requests_to_fetch[next_schedule_offset]
            pending_tasks.add(
                asyncio.create_task(
                    self._fetch_one_concurrent_request(
                        recipe=recipe,
                        request_index=request_index,
                        request=request,
                        semaphore=semaphore,
                        started_at=started_at,
                    )
                )
            )
            next_schedule_offset += 1
        current_request_index = next_request_index
        next_flush_index = next_request_index
        pages_scheduled = next_schedule_offset
        pages_attempted = 0
        requests_attempted = 0
        stop_reason: RunnerStopReason = "completed"

        while pending_tasks:
            remaining_timeout = _remaining_timeout_seconds(
                clock=self._clock,
                started_at=started_at,
                max_seconds=max_seconds,
                pages_attempted=pages_attempted,
            )
            if remaining_timeout == 0:
                terminal_state = RunState(
                    items_written=items_written,
                    pages_scheduled=pages_scheduled,
                    pages_attempted=pages_attempted,
                    requests_attempted=requests_attempted,
                    stop_reason="max_seconds_reached",
                    current_request_index=next_flush_index,
                )
                break
            done, pending_tasks = await asyncio.wait(
                pending_tasks,
                timeout=remaining_timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done:
                terminal_state = RunState(
                    items_written=items_written,
                    pages_scheduled=pages_scheduled,
                    pages_attempted=pages_attempted,
                    requests_attempted=requests_attempted,
                    stop_reason="max_seconds_reached",
                    current_request_index=next_flush_index,
                )
                break
            for task in done:
                request_index, result = task.result()
                pending_results[request_index] = result
            if terminal_state is not None:
                continue
            flushed_any = False
            while next_flush_index in pending_results:
                flushed_any = True
                current_request_index = next_flush_index
                pages_attempted += 1
                response, request_attempts, stop_reason = pending_results.pop(next_flush_index)
                requests_attempted += request_attempts
                if response is None or stop_reason == "non_success_status":
                    terminal_state = RunState(
                        items_written=items_written,
                        pages_scheduled=pages_scheduled,
                        pages_attempted=pages_attempted,
                        requests_attempted=requests_attempted,
                        stop_reason=stop_reason,
                        current_request_index=current_request_index,
                    )
                    break
                extracted_items = _extract_response_items(response, recipe)
                items_written, stop_reason = _write_items(
                    output_file=output_file,
                    items=extracted_items,
                    items_written=items_written,
                    max_items=max_items,
                )
                if stop_reason == "max_items_reached":
                    terminal_state = RunState(
                        items_written=items_written,
                        pages_scheduled=pages_scheduled,
                        pages_attempted=pages_attempted,
                        requests_attempted=requests_attempted,
                        stop_reason=stop_reason,
                        current_request_index=current_request_index,
                    )
                    break
                if not extracted_items:
                    stop_reason = "empty_page"
                    terminal_state = RunState(
                        items_written=items_written,
                        pages_scheduled=pages_scheduled,
                        pages_attempted=pages_attempted,
                        requests_attempted=requests_attempted,
                        stop_reason=stop_reason,
                        current_request_index=current_request_index,
                    )
                    break
                _write_checkpoint(
                    checkpoint_path=checkpoint_path,
                    recipe=recipe,
                    output_path=output_path,
                    next_request_index=next_flush_index + 1,
                    items_written=items_written,
                    stop_reason="completed",
                )
                next_flush_index += 1
            if terminal_state is not None or not flushed_any:
                continue
            while (
                len(pending_tasks) < recipe.execution.concurrency
                and next_schedule_offset < len(requests_to_fetch)
            ):
                await _sleep_before_concurrent_launch(
                    self._sleep,
                    delay_ms,
                    next_schedule_offset,
                )
                request_index, request = requests_to_fetch[next_schedule_offset]
                pending_tasks.add(
                    asyncio.create_task(
                        self._fetch_one_concurrent_request(
                            recipe=recipe,
                            request_index=request_index,
                            request=request,
                            semaphore=semaphore,
                            started_at=started_at,
                        )
                    )
                )
                next_schedule_offset += 1
                pages_scheduled = next_schedule_offset

        if pending_tasks:
            for task in pending_tasks:
                task.cancel()
            await asyncio.gather(*pending_tasks, return_exceptions=True)

        if terminal_state is not None:
            return terminal_state

        return RunState(
            items_written=items_written,
            pages_scheduled=pages_scheduled,
            pages_attempted=pages_attempted,
            requests_attempted=requests_attempted,
            stop_reason=stop_reason,
            current_request_index=current_request_index,
        )

    async def _fetch_one_concurrent_request(
        self,
        recipe: Recipe,
        request_index: int,
        request: RequestSpec,
        semaphore: asyncio.Semaphore,
        started_at: float,
    ) -> tuple[int, tuple[FetchResponse | None, int, RunnerStopReason]]:
        async with semaphore:
            result = await asyncio.to_thread(
                self._fetch_with_retries,
                request=request,
                recipe=recipe,
                started_at=started_at,
            )
        return request_index, result

    def _fetch_with_retries(
        self,
        request: RequestSpec,
        recipe: Recipe,
        started_at: float,
    ) -> tuple[FetchResponse | None, int, RunnerStopReason]:
        attempts = 0
        retry_attempts = recipe.execution.retry_attempts
        retry_backoff_ms = recipe.execution.retry_backoff_ms
        retry_statuses = set(recipe.execution.retry_statuses)
        while True:
            attempts += 1
            try:
                response = self._fetcher.fetch(request)
            except Exception:
                if attempts > retry_attempts or _max_seconds_reached_during_retry(
                    self._clock,
                    started_at,
                    recipe,
                ):
                    return None, attempts, "retry_exhausted"
                _sleep_before_retry(self._sleep, retry_backoff_ms, attempts)
                continue
            if _is_success(response):
                return response, attempts, "completed"
            if response.status_code not in retry_statuses:
                return response, attempts, "non_success_status"
            if attempts > retry_attempts or _max_seconds_reached_during_retry(
                self._clock,
                started_at,
                recipe,
            ):
                return None, attempts, "retry_exhausted"
            _sleep_before_retry(self._sleep, retry_backoff_ms, attempts)


def _validate_execution_mode(recipe: Recipe) -> None:
    del recipe


def _expand_requests(recipe: Recipe) -> tuple[RequestSpec, ...]:
    base_request = recipe.requests[0]
    if recipe.pagination.strategy != "query_page":
        return (base_request,)

    query_param = recipe.pagination.query_param
    if not query_param:
        return (base_request,)

    return tuple(
        _request_for_page(base_request, query_param, page)
        for page in range(
            recipe.pagination.start,
            recipe.pagination.start + recipe.pagination.max_pages,
        )
    )


def _request_for_page(request: RequestSpec, query_param: str, page: int) -> RequestSpec:
    query = dict(request.query)
    query[query_param] = str(page)
    return request.model_copy(update={"query": query})


def _checkpoint_path(recipe: Recipe) -> Path | None:
    if not recipe.execution.checkpoint_path:
        return None
    return Path(recipe.execution.checkpoint_path)


def _load_checkpoint(
    checkpoint_path: Path | None,
    recipe: Recipe,
    output_path: Path,
    request_count: int,
) -> RunnerCheckpoint | None:
    if checkpoint_path is None or not checkpoint_path.exists():
        return None
    checkpoint = RunnerCheckpoint.model_validate_json(checkpoint_path.read_text(encoding="utf-8"))
    if checkpoint.recipe_name != recipe.name:
        msg = (
            "Checkpoint recipe mismatch: "
            f"expected {recipe.name!r}, got {checkpoint.recipe_name!r}"
        )
        raise ValueError(msg)
    if checkpoint.output_path != str(output_path):
        msg = (
            "Checkpoint output path mismatch: "
            f"expected {output_path!s}, got {checkpoint.output_path!r}"
        )
        raise ValueError(msg)
    if checkpoint.next_request_index > request_count:
        msg = (
            "Checkpoint request index out of range: "
            f"{checkpoint.next_request_index} > {request_count}"
        )
        raise ValueError(msg)
    return checkpoint


def _write_checkpoint(
    checkpoint_path: Path | None,
    recipe: Recipe,
    output_path: Path,
    next_request_index: int,
    items_written: int,
    stop_reason: RunnerStopReason,
) -> None:
    if checkpoint_path is None:
        return
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint = RunnerCheckpoint(
        recipe_name=recipe.name,
        next_request_index=next_request_index,
        items_written=items_written,
        output_path=str(output_path),
        stop_reason=stop_reason,
    )
    checkpoint_path.write_text(
        json.dumps(checkpoint.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _finalize_checkpoint(
    checkpoint_path: Path | None,
    recipe: Recipe,
    output_path: Path,
    next_request_index: int,
    items_written: int,
    stop_reason: RunnerStopReason,
) -> str:
    if checkpoint_path is None:
        return ""
    if stop_reason in {"completed", "empty_page", "max_items_reached"}:
        if checkpoint_path.exists():
            checkpoint_path.unlink()
        return ""
    _write_checkpoint(
        checkpoint_path=checkpoint_path,
        recipe=recipe,
        output_path=output_path,
        next_request_index=next_request_index,
        items_written=items_written,
        stop_reason=stop_reason,
    )
    return str(checkpoint_path)


def _resume_request_index(
    stop_reason: RunnerStopReason,
    current_request_index: int,
    next_request_index: int,
    pages_attempted: int,
) -> int:
    if stop_reason in {"retry_exhausted", "non_success_status"}:
        return current_request_index
    return next_request_index + pages_attempted


def _is_success(response: FetchResponse) -> bool:
    return 200 <= response.status_code < 300


def _max_seconds_reached(
    clock: Callable[[], float],
    started_at: float,
    max_seconds: int | None,
    pages_attempted: int,
) -> bool:
    return (
        max_seconds is not None
        and pages_attempted > 0
        and clock() - started_at >= max_seconds
    )


def _remaining_timeout_seconds(
    clock: Callable[[], float],
    started_at: float,
    max_seconds: int | None,
    pages_attempted: int,
) -> float | None:
    if max_seconds is None or pages_attempted <= 0:
        return None
    elapsed = clock() - started_at
    remaining = max_seconds - elapsed
    if remaining <= 0:
        return 0
    return remaining


def _max_seconds_reached_during_retry(
    clock: Callable[[], float],
    started_at: float,
    recipe: Recipe,
) -> bool:
    max_seconds = recipe.execution.max_seconds
    return max_seconds is not None and clock() - started_at >= max_seconds


def _sleep_between_requests(
    sleep_fn: Callable[[float], object],
    delay_ms: int,
    pages_attempted: int,
) -> None:
    if delay_ms <= 0 or pages_attempted <= 0:
        return
    sleep_fn(delay_ms / 1000)


async def _sleep_before_concurrent_launch(
    sleep_fn: Callable[[float], object],
    delay_ms: int,
    scheduled_requests: int,
) -> None:
    if delay_ms <= 0 or scheduled_requests <= 0:
        return
    await asyncio.to_thread(sleep_fn, delay_ms / 1000)


def _sleep_before_retry(
    sleep_fn: Callable[[float], object],
    retry_backoff_ms: int,
    attempts: int,
) -> None:
    if retry_backoff_ms <= 0:
        return
    sleep_fn((retry_backoff_ms * attempts) / 1000)



def _write_items(
    output_file: TextWriter,
    items: tuple[dict[str, object], ...],
    items_written: int,
    max_items: int | None,
) -> tuple[int, RunnerStopReason]:
    stop_reason: RunnerStopReason = "completed"
    for item in items:
        output_file.write(json.dumps(item, ensure_ascii=False) + "\n")
        items_written += 1
        if max_items is not None and items_written >= max_items:
            stop_reason = "max_items_reached"
            break
    return items_written, stop_reason



def _extract_response_items(
    response: FetchResponse,
    recipe: Recipe,
) -> tuple[dict[str, object], ...]:
    try:
        payload = json.loads(response.body_text)
    except json.JSONDecodeError:
        return ()
    if not isinstance(payload, dict):
        return ()
    return extract_items(
        payload,
        item_path=recipe.extract.item_path,
        fields=recipe.extract.fields,
    )
