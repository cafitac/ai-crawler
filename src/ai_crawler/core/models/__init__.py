"""Core domain models shared by ai-crawler components."""

from ai_crawler.core.models.agent import AgentAction, AgentRunResult, ToolResult
from ai_crawler.core.models.crawl import CrawlResult
from ai_crawler.core.models.endpoint import EndpointCandidate
from ai_crawler.core.models.evidence import EvidenceBundle
from ai_crawler.core.models.failure import FailureReport
from ai_crawler.core.models.recipe import (
    ExecutionSpec,
    ExtractSpec,
    PaginationSpec,
    Recipe,
    RunnerStopReason,
    ValidationSpec,
)
from ai_crawler.core.models.request import FetchOptions, RequestSpec
from ai_crawler.core.models.response import FetchResponse
from ai_crawler.core.models.trace import NetworkEvent

__all__ = [
    "AgentAction",
    "AgentRunResult",
    "CrawlResult",
    "EndpointCandidate",
    "EvidenceBundle",
    "FailureReport",
    "ExecutionSpec",
    "ExtractSpec",
    "FetchOptions",
    "FetchResponse",
    "NetworkEvent",
    "PaginationSpec",
    "Recipe",
    "RequestSpec",
    "RunnerStopReason",
    "ToolResult",
    "ValidationSpec",
]
