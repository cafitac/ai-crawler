"""Crawl run result model."""

from pydantic import Field

from ai_crawler.core.models.base import DomainModel
from ai_crawler.core.models.recipe import RunnerStopReason


class CrawlResult(DomainModel):
    """Summary of a deterministic crawl run."""

    recipe_name: str = Field(min_length=1)
    items_written: int = Field(ge=0)
    output_path: str = Field(min_length=1)
    pages_scheduled: int = Field(default=0, ge=0)
    pages_attempted: int = Field(default=0, ge=0)
    requests_attempted: int = Field(default=0, ge=0)
    stop_reason: RunnerStopReason = "completed"
    checkpoint_path: str = ""
