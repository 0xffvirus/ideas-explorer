"""Concrete research adapters."""

from app.research.adapters.base import AdapterDeps, HttpAdapter
from app.research.adapters.hn import HackerNewsSignals
from app.research.adapters.leads import LeadFinder, LeadProvider
from app.research.adapters.reddit import RedditSignals
from app.research.adapters.web import WebSearch

__all__ = [
    "AdapterDeps",
    "HackerNewsSignals",
    "HttpAdapter",
    "LeadFinder",
    "LeadProvider",
    "RedditSignals",
    "WebSearch",
]
