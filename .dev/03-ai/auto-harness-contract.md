# AI Harness Contract

`ai-crawler auto` is the minimal machine entrypoint for agent/harness use.

## Command

```bash
ai-crawler auto evidence.json --json
```

## Local verification

```bash
bash scripts/verify-ai-harness.sh
```

Default artifacts:

- `recipe.yaml`: initial deterministic baseline recipe
- `repaired.recipe.yaml`: repaired recipe after test diagnostics
- `test.jsonl`: initial test crawl output
- `crawl.jsonl`: final crawl output
- `auto.report.json`: same payload printed to stdout in `--json` mode

## Exit codes

- `0`: final recipe test completed and extracted items successfully.
- `2`: deterministic compile/test completed, but final classification is not `success`.

Even on exit code `2`, `--json` mode prints the report payload to stdout and writes `auto.report.json` so the caller can inspect the failure category.

## Stdout JSON schema

`--json` prints one compact JSON object:

```json
{
  "ok": true,
  "summary": "auto compiled recipe: generated-recipe items_written=1",
  "recipe_path": "/abs/path/recipe.yaml",
  "repaired_recipe_path": "/abs/path/repaired.recipe.yaml",
  "output_path": "/abs/path/crawl.jsonl",
  "initial_crawl_result": {
    "recipe_name": "generated-recipe",
    "items_written": 0,
    "output_path": "/abs/path/test.jsonl"
  },
  "final_crawl_result": {
    "recipe_name": "generated-recipe",
    "items_written": 1,
    "output_path": "/abs/path/crawl.jsonl"
  },
  "initial_test_report": {
    "first_response_status": 200,
    "content_type": "application/json",
    "body_sample": "{...redacted sample...}",
    "failure_reason": "no_items_extracted",
    "failure_classification": {
      "category": "extraction_failed",
      "retryable": false,
      "requires_human": false,
      "summary": "response succeeded but recipe extracted no items"
    }
  },
  "final_test_report": {
    "first_response_status": 200,
    "content_type": "application/json",
    "body_sample": "{...redacted sample...}",
    "failure_reason": "",
    "failure_classification": {
      "category": "success",
      "retryable": false,
      "requires_human": false,
      "summary": "test request completed successfully"
    }
  },
  "initial_failure_classification": {
    "category": "extraction_failed",
    "retryable": false,
    "requires_human": false,
    "summary": "response succeeded but recipe extracted no items"
  },
  "final_failure_classification": {
    "category": "success",
    "retryable": false,
    "requires_human": false,
    "summary": "test request completed successfully"
  }
}
```

## Failure categories

- `success`: final request completed and items were extracted.
- `extraction_failed`: HTTP response succeeded but recipe extracted no items.
- `http_error`: non-2xx response without a detected challenge boundary.
- `no_response`: no test response was captured.
- `challenge_detected`: challenge/login/bot-boundary style response detected. The crawler does not bypass this; callers should use manual handoff or an authorized session path.

## Redaction boundary

`body_sample` is capped and passed through common secret redaction before it is written to reports or stdout. Authorization bearer values, cookie session/token values, and common token/API-key assignments are replaced with `[REDACTED]`.
