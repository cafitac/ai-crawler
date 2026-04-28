"""Crawl run result model."""

from pydantic import Field

from ai_crawler.core.models.base import DomainModel


class CrawlResult(DomainModel):
    """Summary of a deterministic crawl run."""

    recipe_name: str = Field(min_length=1)
    items_written: int = Field(ge=0)
    output_path: str = Field(min_length=1)
