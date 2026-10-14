"""research-tools: uniform, cached, rate-limited access to real-world evidence.

Public surface consumed by the agent pipeline:

- :class:`Evidence`, :class:`CompanyLead`: the data contract.
- :class:`ResearchTool`: the adapter protocol.
- :class:`ToolDisabled`: raised when a disabled adapter is used.
- :class:`Cache`, :class:`PostgresCache`, :class:`InMemoryCache`, :class:`NullCache`.
- :class:`ResearchTools`, :func:`build_research_tools`: the wired bundle.
"""

from app.research.adapters import (
    AdapterDeps,
    HackerNewsSignals,
    HttpAdapter,
    LeadFinder,
    LeadProvider,
    RedditSignals,
    WebSearch,
)
from app.research.cache import InMemoryCache, NullCache, PostgresCache
from app.research.contract import (
    SNIPPET_MAX_CHARS,
    Cache,
    CompanyLead,
    Evidence,
    ResearchTool,
    ToolDisabled,
)
from app.research.ratelimit import RateLimiter, TokenBucket
from app.research.toolkit import ResearchTools, build_research_tools

__all__ = [
    "SNIPPET_MAX_CHARS",
    "AdapterDeps",
    "Cache",
    "CompanyLead",
    "Evidence",
    "HackerNewsSignals",
    "HttpAdapter",
    "InMemoryCache",
    "LeadFinder",
    "LeadProvider",
    "NullCache",
    "PostgresCache",
    "RateLimiter",
    "RedditSignals",
    "ResearchTool",
    "ResearchTools",
    "TokenBucket",
    "ToolDisabled",
    "WebSearch",
    "build_research_tools",
]
